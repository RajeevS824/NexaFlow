# app/services/page_stream_segmentation.py
"""
Page Stream Segmentation — integration into document_service.py pipeline.

Called between STEP 4 and STEP 5 of process_document().
Only activates when len(all_results) > 1.

This module:
  A. Detects which consecutive pages belong to the same source document
     (reusing score_pair / segment_pages from the standalone
      Page_stream _segmentation.py).
  B. For any group of 2+ adjacent pages, builds a **merged view** with
     continuing tables physically combined.
  C. Writes per-group merged content files (C1) and a job-level summary (C2).
  D. Returns group metadata so the caller (document_service.py) can run
     keyvalue/table extraction once per group and fan out to every page's
     response.json.
"""

import copy
import json
import logging
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from app.core.logger import logger, make_buffered_logger, flush_buffered_logger

# ---------------------------------------------------------------------------
# Segmentation heuristics shared by the pipeline and standalone use cases
# ---------------------------------------------------------------------------

INVOICE_NO_PATTERNS = [
    r"invoice\s*number\D{0,3}(\d{5,})",
    r"invoice\s*(?:no\.?|#)\s*[:\-]?\s*(\d{4,})",
    r"\b(INV[\-\s]?\d[A-Za-z0-9\-\/]{2,})",
]

CUSTOMER_LABEL_PATTERN = r"\b(bill\s*to|sold\s*to|customer(?:\s*name)?)\b"
PAGE_NUM_PATTERN = r"page\s*(\d+)\s*(?:of|/)\s*(\d+)"
GRAND_TOTAL_PATTERN = r"\b(grand\s*total|total\s*amount|amount\s*due|net\s*payable|total\s*of\s*items)\b"
CONTINUED_PATTERN = r"\b(continued|contd\.?|cont'd)\b"


def normalize_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


_OCR_CONFUSABLES = {
    "0": "O", "O": "0",
    "1": "IL", "I": "1L", "L": "1I",
    "5": "S", "S": "5",
    "8": "B", "B": "8",
}


def fuzzy_equal(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = normalize_id(a), normalize_id(b)
    if a == b:
        return True
    if len(a) != len(b):
        return False
    for ca, cb in zip(a, b):
        if ca == cb:
            continue
        if cb not in _OCR_CONFUSABLES.get(ca, ""):
            return False
    return True


def extract_invoice_number(text: str):
    for pat in INVOICE_NO_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m and re.search(r"\d", m.group(1)):
            return m.group(1)
    return None


INVOICE_LABEL_TOKEN_PATTERN = r"invoice\s*(?:number|no\.?|#)"
BARE_ID_TOKEN_PATTERN = r"^[A-Za-z]{0,3}\d{4,}$"


def extract_invoice_number_spatial(
    ocr_tokens: list,
    max_distance_frac: float = 0.25,
    page_diag: float = None,
    min_rec_score: float = 0.5,
):
    label_tokens = [t for t in ocr_tokens if re.search(INVOICE_LABEL_TOKEN_PATTERN, t.get("text", ""), re.IGNORECASE)]
    if not label_tokens:
        return None

    candidates = [
        t for t in ocr_tokens
        if re.match(BARE_ID_TOKEN_PATTERN, t.get("text", "").strip())
        and t.get("rec_score", 1.0) >= min_rec_score
    ]
    if not candidates:
        return None

    if page_diag is None:
        xs = [t["coordinates"][0] for t in ocr_tokens] + [t["coordinates"][2] for t in ocr_tokens]
        ys = [t["coordinates"][1] for t in ocr_tokens] + [t["coordinates"][3] for t in ocr_tokens]
        page_diag = ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5
    max_dist = max_distance_frac * page_diag

    best = None
    best_dist = float("inf")
    for label in label_tokens:
        lx0, ly0, lx1, ly1 = label["coordinates"]
        lcx, lcy = (lx0 + lx1) / 2, (ly0 + ly1) / 2
        for cand in candidates:
            cx0, cy0, cx1, cy1 = cand["coordinates"]
            ccx, ccy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
            if ccy < ly0 - 5:
                continue
            dist = ((ccx - lcx) ** 2 + (ccy - lcy) ** 2) ** 0.5
            if dist < best_dist and dist <= max_dist:
                best_dist = dist
                best = cand["text"].strip()
    return best


def extract_customer_block(page: dict, window_chars: int = 90) -> Optional[str]:
    text = page.get("text", "")
    m = re.search(CUSTOMER_LABEL_PATTERN + r"[:\-]?\s*(.{0,%d})" % window_chars, text, re.IGNORECASE)
    return m.group(2).strip() if m else None


def extract_page_numbering(text: str):
    m = re.search(PAGE_NUM_PATTERN, text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def has_grand_total(text: str) -> bool:
    return re.search(GRAND_TOTAL_PATTERN, text, re.IGNORECASE) is not None


def has_continued_marker(text: str) -> bool:
    return re.search(CONTINUED_PATTERN, text, re.IGNORECASE) is not None


def get_blocks_by_type(page: dict, block_type: str):
    return [b for b in page.get("blocks", []) if b.get("type") == block_type]


def header_similarity(page_a: dict, page_b: dict) -> float:
    ha = " ".join(b["text"] for b in get_blocks_by_type(page_a, "header"))
    hb = " ".join(b["text"] for b in get_blocks_by_type(page_b, "header"))
    if not ha or not hb:
        return 0.0
    return SequenceMatcher(None, ha.strip().lower(), hb.strip().lower()).ratio()


def table_width_similarity(page_a: dict, page_b: dict, tolerance: float = 0.06) -> bool:
    tables_a = get_blocks_by_type(page_a, "table")
    tables_b = get_blocks_by_type(page_b, "table")
    if not tables_a or not tables_b:
        return False

    last_a = max(tables_a, key=lambda t: t["bbox"][3])
    first_b = min(tables_b, key=lambda t: t["bbox"][1])

    width_a = last_a["bbox"][2] - last_a["bbox"][0]
    width_b = first_b["bbox"][2] - first_b["bbox"][0]
    if width_a <= 0 or width_b <= 0:
        return False

    diff_ratio = abs(width_a - width_b) / max(width_a, width_b)
    return diff_ratio <= tolerance


def table_column_alignment_similarity(page_a: dict, page_b: dict, tolerance: float = 0.05) -> float:
    tables_a = get_blocks_by_type(page_a, "table")
    tables_b = get_blocks_by_type(page_b, "table")
    if not tables_a or not tables_b:
        return 0.0

    last_a = max(tables_a, key=lambda t: t["bbox"][3])
    first_b = min(tables_b, key=lambda t: t["bbox"][1])

    cols_a = last_a.get("columns")
    cols_b = first_b.get("columns")
    if not cols_a or not cols_b or len(cols_a) != len(cols_b):
        return 0.0

    span = max(cols_a) - min(cols_a)
    if span <= 0:
        return 0.0

    diffs = [abs(x - y) / span for x, y in zip(cols_a, cols_b)]
    matched = sum(1 for d in diffs if d <= tolerance)
    return matched / len(cols_a)


def first_block_is_table(page: dict) -> bool:
    blocks = page.get("blocks", [])
    if not blocks:
        return False
    topmost = min(blocks, key=lambda b: b["bbox"][1])
    return topmost.get("type") == "table"


def next_page_starts_with_letterhead(page: dict) -> bool:
    blocks = page.get("blocks", [])
    if not blocks:
        return False
    topmost = min(blocks, key=lambda b: b["bbox"][1])
    return topmost.get("type") == "header"


def has_single_non_table_block(page: dict) -> bool:
    non_table = [b for b in page.get("blocks", []) if b.get("type") != "table"]
    return len(non_table) == 1


def table_continues(page_a: dict, page_b: dict, margin_frac: float = 0.08) -> bool:
    tables_a = get_blocks_by_type(page_a, "table")
    tables_b = get_blocks_by_type(page_b, "table")
    if not tables_a or not tables_b:
        return False

    ha = page_a.get("page_height", 1000)
    hb = page_b.get("page_height", 1000)

    a_touches_bottom = any(t["bbox"][3] >= ha * (1 - margin_frac) for t in tables_a)
    b_touches_top = any(t["bbox"][1] <= hb * margin_frac for t in tables_b)

    if not (a_touches_bottom and b_touches_top):
        return False

    cols_a = next((t.get("columns") for t in tables_a if t.get("columns")), None)
    cols_b = next((t.get("columns") for t in tables_b if t.get("columns")), None)
    if cols_a and cols_b and len(cols_a) == len(cols_b):
        span = max(cols_a) - min(cols_a)
        if span > 0:
            diffs = [abs(x - y) / span for x, y in zip(cols_a, cols_b)]
            if sum(1 for d in diffs if d <= 0.05) / len(cols_a) < 0.5:
                return False

    return True


def is_near_blank(page: dict, min_chars: int = 20) -> bool:
    return len(page.get("text", "").strip()) < min_chars


DEFAULT_WEIGHTS = {
    "same_invoice_number": 100,
    "new_invoice_number": -100,
    "same_customer": 50,
    "different_customer": -50,
    "page_numbering_sequential": 60,
    "page_numbering_reset": -60,
    "page_numbering_gap": -20,
    "table_continues": 35,
    "table_width_match": 25,
    "table_column_alignment": 25,
    "header_similarity": 25,
    "continued_marker_present": 40,
    "prev_page_has_grand_total": -70,
    "next_table_width_confidence_bonus": 15,
}

DEFAULT_CONTINUATION_THRESHOLD = 50.0


def get_invoice_number(page: dict):
    found = extract_invoice_number(page.get("text", ""))
    if found:
        return found
    return extract_invoice_number_spatial(page.get("ocr_tokens", []))


def score_pair(page_a: dict, page_b: dict, weights: dict = DEFAULT_WEIGHTS) -> dict:
    signals = {}
    score = 0.0

    inv_a = get_invoice_number(page_a)
    inv_b = get_invoice_number(page_b)
    invoice_relation = None
    if inv_a and inv_b:
        signals["invoice_number_values"] = [inv_a, inv_b]
        if fuzzy_equal(inv_a, inv_b):
            invoice_relation = "same"
            score += weights["same_invoice_number"]
            signals["invoice_number"] = "same"
        else:
            invoice_relation = "different"
            score += weights["new_invoice_number"]
            signals["invoice_number"] = "different"

    cust_a = extract_customer_block(page_a)
    cust_b = extract_customer_block(page_b)
    if cust_a and cust_b:
        signals["customer_values"] = [cust_a, cust_b]
        if normalize_id(cust_a) == normalize_id(cust_b):
            score += weights["same_customer"]
            signals["customer"] = "same"
        else:
            score += weights["different_customer"]
            signals["customer"] = "different"

    pn_a = extract_page_numbering(page_a.get("text", ""))
    pn_b = extract_page_numbering(page_b.get("text", ""))
    page_numbering_sequential = False
    if pn_a and pn_b:
        cur_a, total_a = pn_a
        cur_b, total_b = pn_b
        if total_a == total_b and cur_b == cur_a + 1:
            page_numbering_sequential = True
            score += weights["page_numbering_sequential"]
            signals["page_numbering"] = "sequential"
        elif cur_b == 1:
            score += weights["page_numbering_reset"]
            signals["page_numbering"] = "reset"
        else:
            score += weights["page_numbering_gap"]
            signals["page_numbering"] = "gap"

    if table_continues(page_a, page_b):
        score += weights["table_continues"]
        signals["table_continues"] = True

    if table_width_similarity(page_a, page_b):
        score += weights["table_width_match"]
        signals["table_width_match"] = True

    tcol_sim = table_column_alignment_similarity(page_a, page_b)
    score += weights["table_column_alignment"] * tcol_sim
    signals["table_column_alignment"] = round(tcol_sim, 3)

    hsim = header_similarity(page_a, page_b)
    score += weights["header_similarity"] * hsim
    signals["header_similarity"] = round(hsim, 3)

    if has_continued_marker(page_a.get("text", "")) or has_continued_marker(page_b.get("text", "")):
        score += weights["continued_marker_present"]
        signals["continued_marker"] = True

    if has_grand_total(page_a.get("text", "")):
        score += weights["prev_page_has_grand_total"]
        signals["prev_grand_total"] = True

    next_starts_with_letterhead = next_page_starts_with_letterhead(page_b)
    next_starts_with_table = first_block_is_table(page_b)
    next_is_sparse = has_single_non_table_block(page_b)
    if next_starts_with_letterhead:
        signals["next_page_starts_with_letterhead"] = True
    if next_starts_with_table:
        signals["next_page_starts_with_table"] = True
        if table_width_similarity(page_a, page_b):
            score += weights["next_table_width_confidence_bonus"]
            signals["next_page_table_width_match"] = True
        else:
            signals["next_page_table_width_match"] = False
    if next_is_sparse:
        signals["next_page_sparse_single_block"] = True

    override = None
    if invoice_relation == "same":
        override = "invoice_number_same"
    elif invoice_relation == "different":
        override = "invoice_number_different"
    elif page_numbering_sequential:
        override = "page_numbering_sequential"
    elif next_starts_with_letterhead:
        override = "next_page_starts_with_letterhead"
    elif next_starts_with_table:
        override = "next_page_starts_with_table"
    elif next_is_sparse:
        override = "next_page_sparse_single_block"

    result = {"score": round(score, 2), "signals": signals}
    if override:
        new_doc_overrides = {"invoice_number_different", "next_page_starts_with_letterhead"}
        signals["override"] = override
        signals["soft_score_before_override"] = round(score, 2)
        result["decision"] = "new_document" if override in new_doc_overrides else "continuation"
        result["decided_by"] = "override"

    return result


def _page_ref(page: dict) -> dict:
    return {"job_id": page.get("job_id"), "page_num": page["page_num"]}


def segment_pages(pages: list, threshold: float = DEFAULT_CONTINUATION_THRESHOLD, weights: dict = DEFAULT_WEIGHTS):
    if not pages:
        return [], []

    invoices = []
    current_group = [_page_ref(pages[0])]
    debug_scores = []

    for i in range(1, len(pages)):
        if is_near_blank(pages[i]):
            current_group.append(_page_ref(pages[i]))
            debug_scores.append({
                "from_page": _page_ref(pages[i - 1]),
                "to_page": _page_ref(pages[i]),
                "score": None,
                "signals": {"near_blank_page": True, "needs_manual_review": True},
                "decision": "continuation",
            })
            continue

        result = score_pair(pages[i - 1], pages[i], weights)
        debug_scores.append({
            "from_page": _page_ref(pages[i - 1]),
            "to_page": _page_ref(pages[i]),
            **result,
        })

        if "decision" in result:
            is_continuation = result["decision"] == "continuation"
        else:
            is_continuation = result["score"] > threshold
            debug_scores[-1]["decision"] = "continuation" if is_continuation else "new_document"
            debug_scores[-1]["decided_by"] = "threshold_fallback"
            debug_scores[-1]["threshold_used"] = threshold

        if is_continuation:
            current_group.append(_page_ref(pages[i]))
        else:
            invoices.append(current_group)
            current_group = [_page_ref(pages[i])]

    invoices.append(current_group)

    output = [
        {"invoice_id": idx + 1, "pages": group}
        for idx, group in enumerate(invoices)
    ]
    return output, debug_scores


# ---------------------------------------------------------------------------
# Helpers: convert all_results entries → score_pair page dict
# ---------------------------------------------------------------------------

# Maps docling_layout semantic labels from the existing module.
DOCLING_LABEL_MAP = {
    "page-header": "header",
    "title": "header",
    "page-footer": "footer",
    "table": "table",
    "section-header": "label",
    "list-item": "list_item",
    "key-value region": "key_value",
}


def _page_bounds(page_entry: dict):
    """Returns (x0, y0, x1, y1) for a page entry from all_results."""
    for b in page_entry.get("layout", {}).get("block_layout", []):
        if b.get("label", "").lower() == "region":
            return tuple(b["coordinate"])
    coords = [b["coordinate"] for b in page_entry.get("layout", {}).get("region_layout", [])]
    if not coords:
        return (0, 0, 1000, 1000)
    x0 = min(c[0] for c in coords)
    y0 = min(c[1] for c in coords)
    x1 = max(c[2] for c in coords)
    y1 = max(c[3] for c in coords)
    return (x0, y0, x1, y1)


def _classify_block(block: dict, page_bounds, top_frac=0.28, bottom_frac=0.15) -> str:
    label = block.get("label", "").lower()
    if label == "table":
        return "table"
    x0, y0, x1, y1 = page_bounds
    page_h = y1 - y0
    _, by0, _, by1 = block["coordinate"]
    if label == "doc_title" or label == "footer":
        return "header" if label == "doc_title" else "footer"
    if by0 <= y0 + page_h * top_frac:
        return "header"
    if by1 >= y1 - page_h * bottom_frac:
        return "footer"
    return "body"


def _attach_ocr_text(bbox, ocr_tokens):
    cx0, cy0, cx1, cy1 = bbox
    return " ".join(
        t["text"] for t in ocr_tokens
        if cx0 <= (t["coordinates"][0] + t["coordinates"][2]) / 2 <= cx1
        and cy0 <= (t["coordinates"][1] + t["coordinates"][3]) / 2 <= cy1
    )


def _blocks_from_docling(docling_blocks: list, page_origin, ocr_tokens: list) -> list:
    x0, y0 = page_origin
    blocks = []
    for b in docling_blocks:
        label = b.get("label", "").lower()
        block_type = DOCLING_LABEL_MAP.get(label, "other")
        bx0, by0, bx1, by1 = b["bbox"]
        rel_bbox = [bx0 - x0, by0 - y0, bx1 - x0, by1 - y0]
        entry = {
            "type": block_type,
            "text": _attach_ocr_text([bx0, by0, bx1, by1], ocr_tokens),
            "bbox": rel_bbox,
        }
        if block_type == "table":
            entry["columns"] = [rel_bbox[0], rel_bbox[2]]
        blocks.append(entry)
    return blocks


def _blocks_from_region_layout(region_blocks: list, page_bounds, ocr_tokens: list) -> list:
    x0, y0, _, _ = page_bounds
    blocks = []
    for b in region_blocks:
        block_type = _classify_block(b, page_bounds)
        cx0, cy0, cx1, cy1 = b["coordinate"]
        rel_bbox = [cx0 - x0, cy0 - y0, cx1 - x0, cy1 - y0]
        entry = {
            "type": block_type,
            "text": _attach_ocr_text([cx0, cy0, cx1, cy1], ocr_tokens),
            "bbox": rel_bbox,
        }
        if block_type == "table":
            entry["columns"] = [rel_bbox[0], rel_bbox[2]]
        blocks.append(entry)
    return blocks


def _to_scoring_page(page_entry: dict) -> dict:
    """Convert one element from all_results to the page dict format
    that score_pair() / segment_pages() expects."""
    bounds = _page_bounds(page_entry)
    x0, y0, x1, y1 = bounds
    page_height = y1 - y0

    ocr_tokens = page_entry.get("ocr", [])
    # Reading-order text
    sorted_tokens = sorted(ocr_tokens, key=lambda t: (round(t["coordinates"][1] / 20), t["coordinates"][0]))
    lines = [t["text"] for t in sorted_tokens]
    full_text = "\n".join(lines)

    docling_blocks = page_entry.get("layout", {}).get("docling_layout", [])
    if docling_blocks:
        blocks = _blocks_from_docling(docling_blocks, (x0, y0), ocr_tokens)
    else:
        blocks = _blocks_from_region_layout(
            page_entry.get("layout", {}).get("region_layout", []), bounds, ocr_tokens
        )

    rel_ocr_tokens = [
        {
            "text": t["text"],
            "coordinates": [
                t["coordinates"][0] - x0,
                t["coordinates"][1] - y0,
                t["coordinates"][2] - x0,
                t["coordinates"][3] - y0,
            ],
            "rec_score": t.get("rec_score", 1.0),
        }
        for t in ocr_tokens
    ]

    return {
        "page_num": page_entry.get("page_num", 0),
        "text": full_text,
        "lines": lines,
        "blocks": blocks,
        "ocr_tokens": rel_ocr_tokens,
        "page_height": page_height,
    }


# ---------------------------------------------------------------------------
# Step A — Boundary detection
# ---------------------------------------------------------------------------

def _detect_groups(all_results: list, threshold: float = 50.0) -> dict:
    """
    Walk all_results in page order, reusing the existing module's
    score_pair() to decide each adjacent boundary.
    Returns {
        "groups": [[0], [1,2,3], ...],       # 0-based page indices
        "debug_scores": [                     # per-boundary debug entries
            {"from_page": N, "to_page": N+1, "score": ..., "signals": {...},
             "decision": ..., "decided_by": ...}, ...
        ],
    }
    """
    # Convert once
    scoring_pages = [_to_scoring_page(p) for p in all_results]

    groups = []
    current = [0]
    debug_scores = []

    for i in range(1, len(scoring_pages)):
        result = score_pair(scoring_pages[i - 1], scoring_pages[i])
        debug_entry = {
            "from_page": i - 1,  # 0-based
            "to_page": i,
            "score": result["score"],
            "signals": result.get("signals", {}),
        }

        # Determine continuation
        if "decision" in result:
            is_continuation = result["decision"] == "continuation"
            debug_entry["decision"] = result["decision"]
            debug_entry["decided_by"] = result.get("decided_by", "override")
        else:
            is_continuation = result["score"] > threshold
            debug_entry["decision"] = "continuation" if is_continuation else "new_document"
            debug_entry["decided_by"] = "threshold_fallback"
            debug_entry["threshold_used"] = threshold

        # Check near-blank page: always attach to previous group
        if is_near_blank(scoring_pages[i]):
            is_continuation = True
            debug_entry["decision"] = "continuation"
            debug_entry["decided_by"] = "near_blank_page"
            debug_entry["signals"]["near_blank_page"] = True

        debug_scores.append(debug_entry)

        if is_continuation:
            current.append(i)
        else:
            groups.append(current)
            current = [i]

    groups.append(current)

    return {
        "groups": groups,
        "debug_scores": debug_scores,
    }


# ---------------------------------------------------------------------------
# Step B — Table merge within a continuous group
# ---------------------------------------------------------------------------

_PANDAS_PLACEHOLDER_RE = re.compile(r"^(|Unnamed:\s*\d+)$")


def _first_block_is_table(page_content: dict) -> bool:
    """Check if the topmost layout block on the page is a table."""
    # Use docling_layout if available, else region_layout
    layout = page_content.get("layout", {})
    docling_blocks = layout.get("docling_layout", [])
    if docling_blocks:
        topmost = min(docling_blocks, key=lambda b: b["bbox"][1])
        return topmost.get("label", "").lower() == "table"

    region_blocks = layout.get("region_layout", [])
    if not region_blocks:
        return False
    topmost = min(region_blocks, key=lambda b: b["coordinate"][1])
    return topmost.get("label", "").lower() == "table"


def _get_table_header_row(table: dict) -> str:
    """Get the first header row text from a table's row_wise or column_wise data.
    Returns empty string if no header found."""
    # Try row_wise first
    row_wise = table.get("row_wise", [])
    if row_wise and len(row_wise) > 0:
        header_cells = []
        # Check if first row is marked as header
        for cell in table.get("cells", []):
            if cell.get("row") == 0:
                header_cells.append(cell.get("text", "").strip())
        if header_cells:
            return "|".join(header_cells)

    # Fallback: extract from column_wise keys
    column_wise = table.get("column_wise", {})
    if column_wise:
        headers = list(column_wise.keys())
        return "|".join(headers)

    return ""


def _is_pandas_placeholder(header_text: str) -> bool:
    """True if the header text is empty or a pandas auto-generated placeholder."""
    if not header_text:
        return True
    parts = header_text.split("|")
    return all(bool(_PANDAS_PLACEHOLDER_RE.match(p.strip())) for p in parts)


def _merge_tables_in_group(
    results_slice: list,
    scoring_pages: list,
) -> list:
    """
    Given a contiguous list of all_results entries forming one group (size >= 2),
    physically merge continuing tables across page boundaries.

    Uses a running "active_table" stored on page 0 so that a table continuing
    across 3+ pages (page 1 → page 2 → page 3) gets correctly chained:
    page 2's table merges into page 1's, then page 3's table compares against
    the now-enlarged page 1 table (not page 2, which is empty after the first
    merge).

    Mutates a DEEP COPY of the entries (returned as new list).
    The original all_results is NEVER modified.
    """
    merged = copy.deepcopy(results_slice)

    # active_last_table_idx: (page_index, table_index) pointing to the table
    # that a continuation candidate on a later page would merge into.
    # Starts as (0, last) — the last table of page 0.
    # After a merge, it stays the same (page 0's last table grew).
    # When no merge, it advances to (current_page, last).
    active_location = None
    if merged[0].get("tables"):
        active_location = (0, len(merged[0]["tables"]) - 1)

    for idx in range(len(merged) - 1):
        page_b = merged[idx + 1]

        # Only the first table on page B is a merge candidate,
        # and only if it's also the topmost layout block.
        tables_b = page_b.get("tables", [])
        if not tables_b:
            continue
        if not _first_block_is_table(page_b):
            # Page B doesn't start with a table — reset active to this
            # page's last table (new table segment).
            active_location = (idx + 1, len(tables_b) - 1)
            continue

        candidate_table_b = tables_b[0]

        if active_location is None:
            active_location = (idx + 1, len(tables_b) - 1)
            continue

        # Get active table from stored location
        a_page_idx, a_tbl_idx = active_location
        active_table = merged[a_page_idx]["tables"][a_tbl_idx]

        # Compare headers
        header_a = _get_table_header_row(active_table)
        header_b = _get_table_header_row(candidate_table_b)

        # Determine if merge should happen (Case 1 or Case 2)
        should_merge = False
        if header_a and header_b and header_a == header_b:
            should_merge = True
        elif _is_pandas_placeholder(header_b):
            should_merge = True

        if not should_merge:
            # Case 3 — mismatch. Start a new segment from this page.
            active_location = (idx + 1, len(tables_b) - 1)
            continue

        # Intra-flow text block check on page B
        if _text_block_intervenes_single(candidate_table_b, page_b):
            active_location = (idx + 1, len(tables_b) - 1)
            continue

        # ---- PHYSICAL MERGE ----
        # Append candidate_table_b's rows into active_table, and store the
        # merged result back into the active table's location.
        merged_table = _append_table_data(active_table, candidate_table_b)
        merged[a_page_idx]["tables"][a_tbl_idx] = merged_table

        # Remove the merged table from page_b
        page_b["tables"].pop(0)

    return merged


def _text_block_intervenes_single(table_b: dict, page_b: dict) -> bool:
    """
    Simplified check: is there any non-table, non-page-header layout block
    *above* table_b on page_b? If yes, the table is NOT a direct continuation
    from a previous page — it starts after intervening text.
    """
    table_b_top = table_b.get("table_bbox", [0, 0, 0, 0])[1] if table_b.get("table_bbox") else 0

    for block in page_b.get("layout", {}).get("docling_layout", []):
        label = block.get("label", "").lower()
        if label == "table":
            continue
        if label in ("page-header", "title"):
            if block["bbox"][1] < table_b_top and block["bbox"][3] - block["bbox"][1] < 60:
                continue
        if block["bbox"][1] < table_b_top - 5:
            return True

    for block in page_b.get("layout", {}).get("region_layout", []):
        label = block.get("label", "").lower()
        if label == "table":
            continue
        if block["coordinate"][1] < table_b_top - 5:
            return True

    return False


def _text_block_intervenes(
    page_a: dict,
    table_a: dict,
    page_b: dict,
    table_b: dict,
    scoring_page_b: Optional[dict],
) -> bool:
    """
    If a text layout block appears AFTER table_a on page_a or BEFORE table_b
    on page_b (excluding a simple page-header at the very top of page_b),
    the tables do NOT merge.
    """
    # Check page A: any non-table block with y > table_a's bottom edge
    table_a_bottom = table_a.get("table_bbox", [0, 0, 0, 0])[3] if table_a.get("table_bbox") else 0
    for block in page_a.get("layout", {}).get("docling_layout", []):
        if block.get("label", "").lower() in ("text", "paragraph", "section-header", "list-item", "key-value region"):
            if block["bbox"][1] > table_a_bottom + 5:  # strictly below the table
                return True
    for block in page_a.get("layout", {}).get("region_layout", []):
        if block.get("label", "").lower() != "table":
            if block["coordinate"][1] > table_a_bottom + 5:
                return True

    # Check page B: any non-header, non-table block above table_b (but not
    # a simple top-of-page header)
    table_b_top = table_b.get("table_bbox", [0, 0, 0, 0])[1] if table_b.get("table_bbox") else 0
    for block in page_b.get("layout", {}).get("docling_layout", []):
        label = block.get("label", "").lower()
        if label == "table":
            continue
        if label in ("page-header", "title"):
            # Only skip if it's at the very top of the page, typical header
            if block["bbox"][1] < table_b_top and block["bbox"][3] - block["bbox"][1] < 60:
                continue
        if block["bbox"][1] < table_b_top - 5:
            return True

    # Check region_layout on page_b
    table_b_top_rl = table_b_top  # already have it
    for block in page_b.get("layout", {}).get("region_layout", []):
        label = block.get("label", "").lower()
        if label == "table":
            continue
        if block["coordinate"][1] < table_b_top_rl - 5:
            return True

    return False


def _append_table_data(target: dict, source: dict) -> dict:
    """Append source table's rows into target table (deep copy of target)."""
    result = copy.deepcopy(target)

    # row_wise: extend list
    if "row_wise" in source and "row_wise" in result:
        result["row_wise"].extend(copy.deepcopy(source.get("row_wise", [])))
    elif "row_wise" in source and "row_wise" not in result:
        result["row_wise"] = copy.deepcopy(source.get("row_wise", []))

    # column_wise: extend each column's list
    src_cols = source.get("column_wise", {})
    tgt_cols = result.get("column_wise", {})
    if src_cols:
        if not tgt_cols:
            result["column_wise"] = copy.deepcopy(src_cols)
        else:
            for key in src_cols:
                if key in tgt_cols:
                    tgt_cols[key].extend(copy.deepcopy(src_cols[key]))
                else:
                    tgt_cols[key] = copy.deepcopy(src_cols[key])

    # cells: extend with row offset
    cells_src = source.get("cells", [])
    cells_tgt = result.get("cells", [])
    max_row_tgt = max((c.get("row", 0) for c in cells_tgt), default=0) + 1 if cells_tgt else 0
    for cell in cells_src:
        new_cell = copy.deepcopy(cell)
        if "row" in new_cell:
            new_cell["row"] = new_cell.get("row", 0) + max_row_tgt
        cells_tgt.append(new_cell)
    result["cells"] = cells_tgt

    # columns: keep target's columns (should be same structure)
    # html: could concatenate tbody
    html_tgt = result.get("html", "")
    html_src = source.get("html", "")
    if html_tgt and html_src:
        # Append rows from source html into target html
        # Simple approach: merge the tbody sections
        import re as _re
        tbody_match_src = _re.search(r"<tbody>(.*?)</tbody>", html_src, _re.DOTALL)
        if tbody_match_src and "<tbody>" in html_tgt:
            result["html"] = html_tgt.replace("</tbody>", tbody_match_src.group(1) + "</tbody>")
        elif tbody_match_src:
            result["html"] += tbody_match_src.group(0)

    return result


# ---------------------------------------------------------------------------
# Build merged view (single synthetic page dict) for extraction
# ---------------------------------------------------------------------------

def _compute_page_height(page_entry: dict) -> float:
    """Get the height of a page from its layout bounds."""
    bounds = _page_bounds(page_entry)
    return bounds[3] - bounds[1]


def _build_merged_view(
    group_indices: list,
    all_results: list,
    merged_results: list,
) -> dict:
    """
    Build a single merged page dict from a group of 2+ pages,
    using post-merge table data from merged_results.
    The merged view offsets Y-coordinates so pages stack vertically.
    """
    # Calculate cumulative Y-offsets
    page_heights = [_compute_page_height(all_results[i]) for i in group_indices]
    y_offsets = [sum(page_heights[:i]) for i in range(len(group_indices))]

    merged_ocr = []
    merged_tables = []
    merged_docling_layout = []
    merged_region_layout = []
    merged_image = all_results[group_indices[0]].get("image", "")

    for local_idx, global_idx in enumerate(group_indices):
        y_off = y_offsets[local_idx]
        source_result = merged_results[local_idx]
        orig_page = all_results[global_idx]

        # OCR tokens: offset Y
        for tok in source_result.get("ocr", []):
            tok_copy = copy.deepcopy(tok)
            coords = tok_copy.get("coordinates", [])
            if len(coords) == 4:
                tok_copy["coordinates"] = [
                    coords[0], coords[1] + y_off,
                    coords[2], coords[3] + y_off,
                ]
            merged_ocr.append(tok_copy)

        # Tables: offset Y in table_bbox and cells
        for table in source_result.get("tables", []):
            table_copy = copy.deepcopy(table)
            # Offset table_bbox
            tbbox = table_copy.get("table_bbox", [])
            if len(tbbox) == 4:
                table_copy["table_bbox"] = [
                    tbbox[0], tbbox[1] + y_off,
                    tbbox[2], tbbox[3] + y_off,
                ]
            # Offset cells
            for cell in table_copy.get("cells", []):
                ccoords = cell.get("coordinates", [])
                if len(ccoords) == 4:
                    cell["coordinates"] = [
                        ccoords[0], ccoords[1] + y_off,
                        ccoords[2], ccoords[3] + y_off,
                    ]
            # Offset visual_cells
            for vc in table_copy.get("visual_cells", []):
                if len(vc) == 4:
                    vc[1] += y_off
                    vc[3] += y_off
            merged_tables.append(table_copy)

        # Docling layout: offset bbox
        for d in orig_page.get("layout", {}).get("docling_layout", []):
            d_copy = copy.deepcopy(d)
            bbox = d_copy.get("bbox", [])
            if len(bbox) == 4:
                d_copy["bbox"] = [bbox[0], bbox[1] + y_off, bbox[2], bbox[3] + y_off]
            merged_docling_layout.append(d_copy)

        # Region layout: offset coordinate
        for r in orig_page.get("layout", {}).get("region_layout", []):
            r_copy = copy.deepcopy(r)
            coord = r_copy.get("coordinate", [])
            if len(coord) == 4:
                r_copy["coordinate"] = [coord[0], coord[1] + y_off, coord[2], coord[3] + y_off]
            merged_region_layout.append(r_copy)

    merged_layout = {
        "block_layout": copy.deepcopy(all_results[group_indices[0]].get("layout", {}).get("block_layout", [])),
        "region_layout": merged_region_layout,
        "docling_layout": merged_docling_layout,
    }

    # Copy block_layout entries if any have Y-coords and need offset
    if merged_layout["block_layout"]:
        blk_off = y_offsets[0]
        for blk in merged_layout["block_layout"]:
            coord = blk.get("coordinate", [])
            if len(coord) == 4:
                blk["coordinate"] = [coord[0], coord[1] + blk_off, coord[2], coord[3] + blk_off]

    return {
        "image": merged_image,
        "layout": merged_layout,
        "ocr": merged_ocr,
        "tables": merged_tables,
    }


# ---------------------------------------------------------------------------
# Build per-group C1 merged content file
# ---------------------------------------------------------------------------

def _build_group_content(
    group_indices: list,
    all_results: list,
    merged_results: list,
    debug_entries: list,
) -> dict:
    """
    Build the per-group content dict for the C1 file:
      { group_pages, boundaries, pages: [ {page_num, region_layout, docling_layout, ocr, tables}, ... ] }
    tables entries are POST-MERGE (continued tables appended & removed).
    """
    # Build boundaries subset for this group
    boundaries = []
    for de in debug_entries:
        if de["from_page"] in group_indices and de["to_page"] in group_indices:
            boundaries.append({
                "from_page": de["from_page"] + 1,  # 1-based for output readability
                "to_page": de["to_page"] + 1,
                "decision": de.get("decision", ""),
                "score": de.get("score", 0),
                "decided_by": de.get("decided_by", ""),
                "override": de.get("signals", {}).get("override"),
            })

    pages = []
    for local_idx, global_idx in enumerate(group_indices):
        orig = all_results[global_idx]
        merged_result = merged_results[local_idx]
        pages.append({
            "page_num": global_idx + 1,
            "region_layout": copy.deepcopy(orig.get("layout", {}).get("region_layout", [])),
            "docling_layout": copy.deepcopy(orig.get("layout", {}).get("docling_layout", [])),
            "ocr": copy.deepcopy(orig.get("ocr", [])),
            "tables": copy.deepcopy(merged_result.get("tables", [])),
        })

    return {
        "group_pages": [gi + 1 for gi in group_indices],
        "boundaries": boundaries,
        "pages": pages,
    }


# ---------------------------------------------------------------------------
# C2 — job-level summary
# ---------------------------------------------------------------------------

def _build_job_summary(
    groups_info: dict,
    debug_scores: list,
    job_id: str,
) -> dict:
    """Build the job-level summary for the C2 output file."""
    groups_1based = [[gi + 1 for gi in g] for g in groups_info["groups"]]

    debug_export = []
    for de in debug_scores:
        entry = {
            "from_page": de["from_page"] + 1,
            "to_page": de["to_page"] + 1,
            "score": de.get("score"),
            "decision": de.get("decision"),
            "decided_by": de.get("decided_by"),
            "signals": de.get("signals", {}),
        }
        if "threshold_used" in de:
            entry["threshold_used"] = de["threshold_used"]
        debug_export.append(entry)

    return {
        "job_id": job_id,
        "groups": groups_1based,
        "boundary_decisions": debug_export,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_segmentation(
    all_results: list,
    job_id: str,
    output_dir: Path,
    threshold: float = 50.0,
    log_writer=None,
) -> dict:
    """
    Called by document_service.py between STEP 4 and STEP 5.
    Only call when len(all_results) > 1 (single-page jobs are no-ops).

    log_writer: optional StructuredLogWriter instance. When provided and in
    DEBUG/ERROR mode, writes structured rows to Page_stream_segmentation.csv.

    Returns:
        groups_info: {
            "groups": [[0], [1,2,3], ...],       # 0-based page index groups
            "merged_views": {                     # only for groups of size 2+
                (0, 2): {
                    "merged_page": {...},          # single synthetic page for extraction
                    "group_first_idx": 0,
                    "group_last_idx": 2,
                    "group_page_numbers": [1, 2, 3],
                },
            },
            "debug_scores": [...],
        }
    """
    import time as _time

    def _seg_log(phase, description, status="Completed", decision="",
                 input_summary="", output_summary="", error="",
                 duration="", level="DEBUG"):
        """Helper: write to Page_stream_segmentation.csv if log_writer present."""
        if log_writer is not None:
            log_writer.log_segmentation(
                level=level, phase=phase, description=description,
                status=status, decision=decision,
                input_summary=input_summary, output_summary=output_summary,
                error=error, duration=duration,
                function="run_segmentation",
            )

    seg_logger, seg_handler = make_buffered_logger("page_stream_segmentation")
    seg_logger.info("=" * 80)
    seg_logger.info("PAGE STREAM SEGMENTATION STARTED")
    seg_logger.info("=" * 80)
    seg_logger.info("Total pages in job: %d", len(all_results))
    _seg_log("Init", f"Page Stream Segmentation started",
             input_summary=f"{len(all_results)} pages, threshold={threshold}")

    # -----------------------------------------------------------------------
    # Step A — Boundary detection
    # -----------------------------------------------------------------------
    seg_logger.info("Step A: Detecting page boundaries...")
    _seg_log("Step A - Boundary Detection", "Detecting page boundaries",
             status="Processing", input_summary=f"{len(all_results)} pages")
    _t0 = _time.perf_counter()
    group_data = _detect_groups(all_results, threshold=threshold)
    groups = group_data["groups"]
    debug_scores = group_data["debug_scores"]
    _dur_a = f"{_time.perf_counter() - _t0:.4f}"

    groups_str = str([[g + 1 for g in grp] for grp in groups])
    seg_logger.info("Groups found: %s", groups_str)
    _seg_log("Step A - Boundary Detection",
             f"Boundary detection completed: {len(groups)} group(s) found",
             status="Completed", decision=f"{len(groups)} group(s)",
             output_summary=groups_str, duration=_dur_a)

    # Setup: compute scoring pages once (needed for table merge checks)
    scoring_pages = [_to_scoring_page(p) for p in all_results]

    # -----------------------------------------------------------------------
    # Step B — Table merge per group
    # -----------------------------------------------------------------------
    seg_logger.info("Step B: Merging continuing tables within groups...")
    _seg_log("Step B - Table Merge", "Merging continuing tables within groups",
             status="Processing", input_summary=f"{len(groups)} group(s)")

    merged_views = {}  # key: (first_idx, last_idx) -> merged view info
    group_first_pages = {}  # first_idx -> group info for file writing

    for group in groups:
        if len(group) < 2:
            _seg_log("Step B - Table Merge",
                     f"Group {[g+1 for g in group]}: single page, skipping merge",
                     decision="Skipped")
            continue  # standalone page — no merging needed

        # Deep-copy slice of all_results for this group and merge tables
        merged_results = _merge_tables_in_group(
            [all_results[i] for i in group],
            [scoring_pages[i] for i in group],
        )

        # Build merged view for extraction (single synthetic page)
        merged_page = _build_merged_view(group, all_results, merged_results)

        first_idx = group[0]
        last_idx = group[-1]
        key = (first_idx, last_idx)

        merged_views[key] = {
            "merged_page": merged_page,
            "group_first_idx": first_idx,
            "group_last_idx": last_idx,
            "group_page_numbers": [g + 1 for g in group],
        }

        group_first_pages[first_idx] = {
            "group_indices": group,
            "merged_results": merged_results,
        }
        _seg_log("Step B - Table Merge",
                 f"Group pages {[g+1 for g in group]}: tables merged",
                 decision="Merged",
                 output_summary=f"{len(merged_results)} merged page(s)")

    # -----------------------------------------------------------------------
    # Step C1 — Write per-group merged content file
    # -----------------------------------------------------------------------
    seg_logger.info("Step C1: Writing per-group merged content files...")
    _seg_log("Step C1 - Write Group Content",
             "Writing per-group merged content (Page_stream_segmentation.json)",
             status="Processing")

    for first_idx, group_info in group_first_pages.items():
        group_indices = group_info["group_indices"]
        merged_results = group_info["merged_results"]

        group_content = _build_group_content(
            group_indices, all_results, merged_results, debug_scores
        )

        # Path: Output/<job_id>/page_<first_page>/response/Page_stream_segmentation.json
        first_page_no = first_idx + 1
        c1_dir = output_dir / f"page_{first_page_no}" / "response"
        os.makedirs(c1_dir, exist_ok=True)
        c1_path = c1_dir / "Page_stream_segmentation.json"

        with open(c1_path, "w", encoding="utf-8") as f:
            json.dump(group_content, f, indent=2, ensure_ascii=False)

        seg_logger.info("  -> Written %s", c1_path)
        _seg_log("Step C1 - Write Group Content",
                 f"Written Page_stream_segmentation.json for pages starting at page {first_page_no}",
                 output_summary=str(c1_path))

    # -----------------------------------------------------------------------
    # Step C2 — Write job-level summary and log
    # -----------------------------------------------------------------------
    seg_logger.info("Step C2: Writing job-level summary...")
    _seg_log("Step C2 - Job Summary", "Writing job-level segmentation summary",
             status="Processing")

    # Summary JSON
    summary = _build_job_summary(group_data, debug_scores, job_id)
    c2_output_dir = output_dir / "Page_stream_segmentation" / "output"
    os.makedirs(c2_output_dir, exist_ok=True)
    c2_path = c2_output_dir / "Page_stream_segmentation.json"
    with open(c2_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    seg_logger.info("  -> Written %s", c2_path)
    _seg_log("Step C2 - Job Summary",
             "Page_stream_segmentation.json written at job level",
             output_summary=str(c2_path))

    # Log file
    c2_log_dir = output_dir / "Page_stream_segmentation" / "log"
    os.makedirs(c2_log_dir, exist_ok=True)
    c2_log_path = c2_log_dir / "Page_stream.log"

    # Flush buffered log to file
    log_file_handler = logging.FileHandler(c2_log_path, mode="w", encoding="utf-8")
    log_file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    for record in seg_handler.records:
        log_file_handler.handle(record)
    log_file_handler.close()
    seg_logger.info("  -> Written %s", c2_log_path)

    # Flush buffered log entries into the main pipeline logger
    flush_buffered_logger(seg_handler, logger)

    # Final summary log
    _seg_log("Complete",
             f"Page Stream Segmentation completed: {len(groups)} group(s)",
             output_summary=f"Groups: {[[g+1 for g in grp] for grp in groups]}")

    # -----------------------------------------------------------------------
    # Return result
    # -----------------------------------------------------------------------
    return {
        "groups": groups,
        "merged_views": merged_views,
        "debug_scores": debug_scores,
    }