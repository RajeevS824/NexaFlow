# ============================================================
# keyvalue_extraction.py
# ============================================================
import re
from datetime import datetime
import app.services.keyvalue_extraction as _self

from app.core.logger import logger

# ============================================================
# SEPARATORS
# Characters used to split key from value in OCR text
# ============================================================

SEPARATORS = [":-", ":=", ":", "=", "#", "|", ">", "<", "»", "«"]

# ============================================================
# THRESHOLDS  (all magic numbers live here - change here only)
# ============================================================

# Phase 1 / Phase 3 same-row: max vertical difference (px)
SAME_ROW_Y_TOLERANCE = 38

# Phase 3 same-row far-row thresholds (3-way):
#   key inside DOCLING table        -> keyinside_table_value_FAR_ROW_THRESHOLD (2500 px)
#   key inside REGION-ONLY table    -> PHASE3_REGION_TABLE_THRESHOLD (400 px)
#   key outside any table           -> PHASE3_HORIZONTAL_FAR_THRESHOLD (1500 px)
PHASE3_HORIZONTAL_FAR_THRESHOLD = 1500     # outside any table
PHASE3_REGION_TABLE_THRESHOLD   = 1500      # inside region-layout "table" only
# PHASE3_DOCLING_TABLE_THRESHOLD  = 400      # legacy (superseded; kept for reference)

# Phase 3 down-column: stop collecting if gap between consecutive items exceeds this
COLUMN_GAP_THRESHOLD = 70

# Phase 4 same-row: if value center-X is farther than this -> fall to down-column
PHASE4_HORIZONTAL_FAR_THRESHOLD = 500

# Phase 4 down search: gap from key bottom to first text below (px)
PHASE4_DOWN_GAP_THRESHOLD = 70

# Phase 4 down search: gap between items collected inside a layout region
PHASE4_LAYOUT_COLLECT_GAP = 70

# Phase 5: key row must have text > this px away to be considered "too far"
# for a same-row value (used by extract_phase5_row_value).
PHASE5_FAR_ROW_THRESHOLD = 2500

# Phase 5 down-column: stop collecting if text-to-text gap exceeds this (px)
PHASE5_COLUMN_GAP_THRESHOLD = 70

# Phase 3 / Phase 4 dynamic threshold: used when key IS inside a docling table.
keyinside_table_value_FAR_ROW_THRESHOLD = 2500

# Phase 1 Case 3 and Case 4: max horizontal distance (px) from key center to value box.
PHASE1_CASE3_CASE4_FAR_THRESHOLD = 800

# Phase 4 row search outside-table thresholds:
#   key has NO separator -> 2000 px
#   key HAS separator    ->  800 px
PHASE4_ROW_OUTSIDE_NO_SEP_THRESHOLD   = 2000
PHASE4_ROW_OUTSIDE_WITH_SEP_THRESHOLD = 800

# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_text(text, trim_whitespace=True):
    if text is None:
        return ""
    if trim_whitespace:
        text = " ".join(text.split())
    return text.lower().strip()

def get_bbox_from_polygon(poly):
    """
    Normalize a bounding box representation into [x1, y1, x2, y2].

    Supports two input shapes, since upstream OCR/table sources are not
    always consistent:

      1. FLAT BBOX  (what the current pipeline actually emits):
           poly = [x1, y1, x2, y2]
         i.e. a flat list of 4 numbers.

      2. POLYGON OF POINTS  (what this function originally assumed):
           poly = [[x1, y1], [x2, y2], [x3, y3], [x4, y4], ...]
         i.e. a list of (x, y) pairs.

    FIX: Previously this function assumed shape (2) unconditionally and
    did `p[0] for p in poly`. When `poly` was actually a flat bbox (shape 1),
    each `p` was an int, causing:
        TypeError: 'int' object is not subscriptable
    This guard detects the flat-bbox case first and short-circuits safely.
    """
    if poly is None:
        return [0, 0, 0, 0]

    # Case 1: flat bbox -> [x1, y1, x2, y2] (all scalar numbers)
    if len(poly) == 4 and all(isinstance(v, (int, float)) for v in poly):
        x1, y1, x2, y2 = poly
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

    # Case 2: polygon of points -> [[x, y], [x, y], ...]
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return [min(xs), min(ys), max(xs), max(ys)]

def is_inside_region(ocr_box, region_box):
    x1, y1, x2, y2 = get_bbox_from_polygon(ocr_box)
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    rx1, ry1, rx2, ry2 = region_box
    return cx >= rx1 and cy >= ry1 and cx <= rx2 and cy <= ry2

def get_center(poly):
    x1, y1, x2, y2 = get_bbox_from_polygon(poly)
    return ((x1 + x2) / 2, (y1 + y2) / 2)

def sort_items_top_to_bottom(items):
    return sorted(items, key=lambda item: get_center(item["coordinates"])[1])

def sort_regions_top_to_bottom(regions):
    return sorted(regions, key=lambda r: r["coordinate"][1])

def sort_tables_top_to_bottom(tables):
    return sorted(
        tables,
        key=lambda t: (t.get("table_bbox") or [0, 0, 0, 0])[1]
    )

def is_alias_match(alias, text_norm):
    pattern = r'\b' + re.escape(alias) + r'\b'
    return bool(re.search(pattern, text_norm))

def is_key_text(text, aliases_norm):
    txt = normalize_text(text)
    return any(is_alias_match(alias, txt) for alias in aliases_norm)

def build_all_keys(labels):
    all_keys = set()
    for label_cfg in labels:
        all_keys.add(normalize_text(label_cfg["label_name"]))
        for alias in label_cfg.get("aliases", []):
            all_keys.add(normalize_text(alias))
    return all_keys

def is_any_document_key(text, all_keys_norm):
    txt = normalize_text(text)
    return any(is_alias_match(key, txt) for key in all_keys_norm)

def get_matched_alias(text_norm, label_name_norm, original_label, original_aliases):
    matches = []
    if is_alias_match(label_name_norm, text_norm):
        matches.append((original_label, "label_name"))
    for alias in original_aliases:
        alias_norm = normalize_text(alias)
        if is_alias_match(alias_norm, text_norm):
            matches.append((alias, "alias"))
    if not matches:
        return None, None
    best = max(
        matches,
        key=lambda m: (
            1 if normalize_text(m[0]) == text_norm else 0,
            len(normalize_text(m[0]))
        )
    )
    logger.info(
        f"[MATCH] OCR text='{text_norm}' matched by: "
        f"{best[1].upper()}='{best[0]}' "
        f"(from {len(matches)} candidate(s))"
    )
    return best[0], best[1]

def has_separator(text):
    return any(sep in text for sep in SEPARATORS)

def starts_with_separator(text):
    stripped = text.strip()
    return any(stripped.startswith(sep) for sep in SEPARATORS)

def strip_leading_separator(text):
    stripped = text.strip()
    for sep in SEPARATORS:
        if stripped.startswith(sep):
            return stripped[len(sep):].strip()
    return stripped

def strip_trailing_separator(text):
    stripped = text.strip()
    for sep in SEPARATORS:
        if stripped.endswith(sep):
            return stripped[: -len(sep)].strip()
    return stripped

def is_separator_only(text):
    return text.strip() in SEPARATORS

# ============================================================
# EXACT FOUNDKEY MATCH
# ============================================================

def is_exact_foundkey_match(text, aliases_norm):
    cleaned = normalize_text(strip_trailing_separator(text))
    return any(cleaned == alias for alias in aliases_norm)

# ============================================================
# BBOX UNION / OVERLAP HELPERS
# ============================================================

def bbox_union(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    return [min(ax1, bx1), min(ay1, by1), max(ax2, bx2), max(ay2, by2)]

def boxes_overlap(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    return not (ax2 <= bx1 or ax1 >= bx2 or ay2 <= by1 or ay1 >= by2)

# ============================================================
# TABLE HELPERS
# ============================================================

def get_table_containing_key(key_item, tables):
    """Returns the docling table dict whose table_bbox contains the
    key box's center, or None if the key is not inside any table."""
    for table in tables:
        table_box = table.get("table_bbox")
        if not table_box or len(table_box) != 4:
            continue
        if is_inside_region(key_item["coordinates"], table_box):
            return table
    return None

def is_key_in_table_region(key_item, tables):
    """True if key box center falls inside any DOCLING table's table_bbox."""
    table = get_table_containing_key(key_item, tables)
    if table:
        logger.info(
            f"[TABLE GUARD] Key '{key_item['text'].strip()}' is inside "
            f"DOCLING TABLE region {table.get('table_bbox')}."
        )
        return True
    return False

def should_block_down_search(key_item, tables):
    """Block down search when key is inside a docling table (Phase 2)."""
    if is_key_in_table_region(key_item, tables):
        logger.info(
            f"[TABLE GUARD] DOWN SEARCH BLOCKED for key "
            f"'{key_item['text'].strip()}' (key is inside a docling table)."
        )
        return True
    return False

# ============================================================
# OVERLAP-AWARE TABLE GUARD
# ============================================================

def get_overlap_aware_table_bboxes(tables, regions):
    """
    Build effective table bboxes for the down-search guard.
    For each Docling table, expand its bbox with any overlapping
    region_layout 'table' entries.
    """
    effective_bboxes = []
    region_table_boxes = [
        r["coordinate"]
        for r in regions
        if r.get("label", "").lower() == "table"
    ]
    for table in tables:
        table_box = table.get("table_bbox")
        if not table_box or len(table_box) != 4:
            continue
        effective = list(table_box)
        for reg_box in region_table_boxes:
            if boxes_overlap(effective, reg_box):
                expanded = bbox_union(effective, reg_box)
                logger.info(
                    f"[OVERLAP GUARD] Docling table {effective} overlaps "
                    f"region table {reg_box} -> union bbox {expanded}."
                )
                effective = expanded
        effective_bboxes.append(effective)
    return effective_bboxes


def should_block_down_search_overlap_aware(key_item, tables, regions):
    """
    Overlap-aware down-search block for Phase 3 and Phase 4.
    Blocks when key center falls inside any effective table bbox.
    Non-overlapping region-only tables are NOT considered here.
    """
    effective_bboxes = get_overlap_aware_table_bboxes(tables, regions)
    key_x1, key_y1, key_x2, key_y2 = get_bbox_from_polygon(key_item["coordinates"])
    key_cx = (key_x1 + key_x2) / 2
    key_cy = (key_y1 + key_y2) / 2

    for eff_box in effective_bboxes:
        ex1, ey1, ex2, ey2 = eff_box
        if ex1 <= key_cx <= ex2 and ey1 <= key_cy <= ey2:
            logger.info(
                f"[OVERLAP GUARD] DOWN SEARCH BLOCKED for key "
                f"'{key_item['text'].strip()}' -- inside effective "
                f"table bbox {eff_box}."
            )
            return True
    return False

# ============================================================
# COMBINED TABLE MEMBERSHIP CHECK
# ============================================================

def is_key_in_region_table_only(key_item, tables, regions):
    """
    True when key is inside a region_layout table that does NOT
    overlap any docling table.
    """
    for region in regions:
        if region.get("label", "").lower() != "table":
            continue
        region_box = region["coordinate"]
        if not is_inside_region(key_item["coordinates"], region_box):
            continue
        overlaps_docling = False
        for table in tables:
            table_box = table.get("table_bbox")
            if table_box and boxes_overlap(region_box, table_box):
                overlaps_docling = True
                break
        if not overlaps_docling:
            return True
    return False

def is_key_in_any_table_or_region(key_item, tables, regions):
    """True if key is inside ANY table: docling OR region_layout 'table'."""
    # (a) Docling table check
    if is_key_in_table_region(key_item, tables):
        return True
    # (b) Region-layout "table" label check
    for region in regions:
        if region.get("label", "").lower() == "table":
            if is_inside_region(key_item["coordinates"], region["coordinate"]):
                logger.info(
                    f"[TABLE CHECK] Key '{key_item['text'].strip()}' is inside "
                    f"region_layout table {region['coordinate']}."
                )
                return True
    return False

# ============================================================
# TABLE-CELL HELPERS
# ============================================================

def get_cell_bbox(cell):
    return cell.get("coordinates") or [0, 0, 0, 0]

def get_cell_center(cell):
    x1, y1, x2, y2 = get_cell_bbox(cell)
    return ((x1 + x2) / 2, (y1 + y2) / 2)

def find_table_cell_keys(tables, aliases_norm):
    """
    Scan every table's 'cells' list for cells whose text exactly
    matches an alias. Returns list of (cell, table) tuples, sorted top-to-bottom.
    """
    found = []
    for table in tables:
        cells = table.get("cells") or []
        for cell in cells:
            text = cell.get("text", "")
            if not text:
                continue
            if is_exact_foundkey_match(text, aliases_norm):
                found.append((cell, table))
    found.sort(
        key=lambda pair: (
            (pair[1].get("table_bbox") or [0, 0, 0, 0])[1],
            pair[0].get("row", 0),
            pair[0].get("col", 0),
        )
    )
    return found

# ============================================================
# HEADER DETECTION HELPERS  (Phase 3 / Phase 5)
# ============================================================

def get_cell_at_position(ocr_item, table):
    """
    Find the cell in `table` whose coordinate box contains the
    center of `ocr_item`. Returns the cell dict or None.

    Used to check whether an OCR-detected text box corresponds to
    a specific table cell (e.g. to test is_header).
    """
    ocr_box = get_bbox_from_polygon(ocr_item["coordinates"])
    ocr_cx = (ocr_box[0] + ocr_box[2]) / 2
    ocr_cy = (ocr_box[1] + ocr_box[3]) / 2

    for cell in (table.get("cells") or []):
        cx1, cy1, cx2, cy2 = get_cell_bbox(cell)
        if cx1 <= ocr_cx <= cx2 and cy1 <= ocr_cy <= cy2:
            return cell
    return None


def is_ocr_item_header_in_table(ocr_item, table):
    """
    Returns True if the OCR item's center falls inside a cell that
    has is_header=True within the given docling table.

    Used by Phase 3 (to block row/down search) and Phase 5 (to skip
    header values in row and column search).
    """
    cell = get_cell_at_position(ocr_item, table)
    if cell is None:
        return False
    return bool(cell.get("is_header", False))

# ============================================================
# PHASE 5 TABLE-CELL ROW/COLUMN HELPERS
# ============================================================

def find_same_row_cell_value(key_cell, table, all_keys_norm):
    """
    Look for a sibling cell in the SAME table, SAME row, with a
    greater col index, that has non-empty text and is not a key.

    CHANGE (Phase 5 req 1): Cells with is_header=True are skipped --
    they are NOT returned as a value. The caller falls through to
    down-column search.
    """
    cells = table.get("cells") or []
    key_row = key_cell.get("row")
    key_col = key_cell.get("col", -1)
    key_cx, key_cy = get_cell_center(key_cell)

    same_row_cells = [
        c for c in cells
        if c.get("row") == key_row and c.get("col", -1) > key_col
    ]
    same_row_cells.sort(key=lambda c: c.get("col", 0))

    for cell in same_row_cells:
        text = (cell.get("text") or "").strip()
        if not text:
            continue

        if is_any_document_key(text, all_keys_norm):
            logger.info(
                f"[PHASE 5][CELL ROW] '{text}' is another key -- "
                f"stopping row search for this table-key cell."
            )
            return None

        cell_cx, cell_cy = get_cell_center(cell)
        if abs(cell_cx - key_cx) > PHASE5_FAR_ROW_THRESHOLD:
            logger.info(
                f"[PHASE 5][CELL ROW] '{text}' is too far "
                f"({abs(cell_cx - key_cx):.0f}px > {PHASE5_FAR_ROW_THRESHOLD}px) "
                f"-- stopping row search."
            )
            return None

        # CHANGE: Skip header cells -- they are column/row labels, not values
        if cell.get("is_header", False):
            logger.info(
                f"[PHASE 5][CELL ROW] '{text}' is a TABLE HEADER (is_header=True) "
                f"-- skipping this cell. Will fall through to down-column search."
            )
            continue

        logger.info(
            f"[PHASE 5][CELL ROW] Same-row cell value found: '{text}' "
            f"(row={key_row}, col={cell.get('col')})."
        )
        return text

    return None

# ============================================================
# PHASE 6 - DIRECT NEXT CELL VALUE
# ============================================================


def extract_phase6_next_cell_value(
    key_cell,
    table,
    all_keys_norm
):
    """
    If key is found inside a docling table cell,
    return the immediate next cell in the same row (col+1).

    Header cells are allowed.

    Only block when:
      - next cell is empty
      - next cell text is another document key
    """

    key_row = key_cell.get("row")
    key_col = key_cell.get("col")

    cells = table.get("cells") or []

    next_cell = next(
        (
            c
            for c in cells
            if c.get("row") == key_row
            and c.get("col") == (key_col + 1)
        ),
        None
    )

    if not next_cell:
        logger.info(
            f"[PHASE 6] No next cell found "
            f"(row={key_row}, col={key_col + 1})"
        )
        return None

    value = (next_cell.get("text") or "").strip()

    if not value:
        logger.info(
            f"[PHASE 6] Next cell is empty "
            f"(row={key_row}, col={key_col + 1})"
        )
        return None

    # Do not return another key
    if is_any_document_key(value, all_keys_norm):
        logger.info(
            f"[PHASE 6] Next cell '{value}' is another key. Skipping."
        )
        return None

    logger.info(
        f"[PHASE 6] Direct next-cell value found: '{value}' "
        f"(row={key_row}, col={key_col + 1})"
    )

    return value

def find_down_column_cell_value(key_cell, table, all_keys_norm):
    """
    Walk down the SAME column within the same table's 'cells' list,
    collecting non-empty text.

    CHANGE (Phase 5 req 1): Cells with is_header=True are skipped.
    CHANGE (Phase 5 req 2): Gap > PHASE5_COLUMN_GAP_THRESHOLD breaks
    the walk (consistent with OCR-based down-column search).
    """
    cells = table.get("cells") or []
    key_col = key_cell.get("col")
    key_row = key_cell.get("row", -1)
    key_cx, key_cy = get_cell_center(key_cell)

    candidates = [
        c for c in cells
        if c.get("col") == key_col and c.get("row", -1) > key_row
    ]
    candidates.sort(key=lambda c: c.get("row", 0))

    values   = []
    prev_cy  = key_cy   # gap chain starts at key's center-y

    for cell in candidates:
        cx, cy = get_cell_center(cell)
        gap = cy - prev_cy

        # CHANGE: break on gap (mirrors OCR down-column behaviour)
        if gap > PHASE5_COLUMN_GAP_THRESHOLD:
            logger.info(
                f"[PHASE 5][CELL COLUMN] Gap {gap:.1f}px > "
                f"{PHASE5_COLUMN_GAP_THRESHOLD}px -- stopping column walk "
                f"at cell '{(cell.get('text') or '').strip()}'. "
                f"Cells below are too far away."
            )
            break

        text = (cell.get("text") or "").strip()
        if not text:
            prev_cy = cy
            continue

        if is_any_document_key(text, all_keys_norm):
            logger.info(
                f"[PHASE 5][CELL COLUMN] '{text}' is another key -- "
                f"stopping column walk."
            )
            break

        # CHANGE: Skip header cells in down-column search
        if cell.get("is_header", False):
            logger.info(
                f"[PHASE 5][CELL COLUMN] '{text}' is a TABLE HEADER (is_header=True) "
                f"-- skipping this cell, continuing column walk."
            )
            prev_cy = cy
            continue

        logger.info(
            f"[PHASE 5][CELL COLUMN] Collecting value: '{text}' "
            f"(row={cell.get('row')}, col={cell.get('col')}, gap={gap:.1f}px)."
        )
        values.append(text)
        prev_cy = cy

    if values:
        result = ", ".join(values)
        logger.info(f"[PHASE 5][CELL COLUMN] Column value assembled: '{result}'.")
        return result
    return None

# ============================================================
# DATATYPE DETECTION
# ============================================================

def detect_value_dtype(value):
    if value is None:
        return None
    value = str(value).strip()
    if value == "":
        return "string"
    number_pattern = re.compile(r'^-?\d+(\.\d+)?$')
    if number_pattern.match(value.replace(",", "")):
        return "number"
    numeric_date_formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y",
        "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y", "%m/%d/%y",
    ]
    for fmt in numeric_date_formats:
        try:
            datetime.strptime(value, fmt)
            return "date"
        except Exception:
            pass
    alpha_date_formats = [
        "%d-%b-%Y", "%d %b %Y", "%d/%b/%Y",
        "%d-%B-%Y", "%d %B %Y",
        "%B %d, %Y", "%b %d, %Y",
        "%d-%b-%y", "%d %b %y",
    ]
    for fmt in alpha_date_formats:
        try:
            datetime.strptime(value, fmt)
            return "date"
        except Exception:
            pass
    return "string"

# ============================================================
# PHASE 1 HELPERS
# ============================================================

def extract_key_part(text):
    for sep in SEPARATORS:
        if sep in text:
            return text.split(sep, 1)[0].strip()
    return text.strip()

def phase1_key_fully_matches(text, aliases_norm):
    key_part = normalize_text(extract_key_part(text))
    return any(key_part == alias for alias in aliases_norm)

def extract_inline_value(text, aliases_norm):
    for sep in SEPARATORS:
        if sep in text:
            parts = text.split(sep, 1)
            if len(parts) > 1:
                value = parts[1].strip()
                if value and not is_key_text(value, aliases_norm):
                    return value
    return None

def extract_same_line_value(key_item, ocr_items, aliases_norm, regions):
    key_cx, key_cy = get_center(key_item["coordinates"])
    key_text = key_item["text"].strip()

    same_row = []
    for item in ocr_items:
        if item == key_item:
            continue
        cx, cy = get_center(item["coordinates"])
        if abs(cy - key_cy) <= SAME_ROW_Y_TOLERANCE and cx > key_cx:
            same_row.append((cx, item))
    same_row = sorted(same_row, key=lambda x: x[0])

    if not same_row:
        return None

    for i, (cx, item) in enumerate(same_row):
        text = item["text"].strip()

        # Case 2: key has no sep; next box starts with sep
        if not has_separator(key_text) and starts_with_separator(text):
            value = strip_leading_separator(text)
            if value and not is_key_text(value, aliases_norm):
                logger.info(f"[PHASE 1] Case 2 value found -> '{value}'")
                return value

        # Case 3: separator is its own box
        if is_separator_only(text):
            if i + 1 < len(same_row):
                next_cx, next_item = same_row[i + 1]
                next_text = next_item["text"].strip()
                if abs(next_cx - key_cx) > PHASE1_CASE3_CASE4_FAR_THRESHOLD:
                    logger.info(
                        f"[PHASE 1] Case 3 value '{next_text}' is too far "
                        f"({abs(next_cx - key_cx):.0f}px > "
                        f"{PHASE1_CASE3_CASE4_FAR_THRESHOLD}px) -- skipping."
                    )
                    continue
                if not is_key_text(next_text, aliases_norm):
                    logger.info(f"[PHASE 1] Case 3 value found -> '{next_text}'")
                    return next_text
            continue

        # Case 4: key box ends with sep, next box is value
        if has_separator(key_text):
            if abs(cx - key_cx) > PHASE1_CASE3_CASE4_FAR_THRESHOLD:
                logger.info(
                    f"[PHASE 1] Case 4 '{text}' is too far "
                    f"({abs(cx - key_cx):.0f}px > "
                    f"{PHASE1_CASE3_CASE4_FAR_THRESHOLD}px) -- skipping."
                )
                continue
            if not is_key_text(text, aliases_norm):
                logger.info(f"[PHASE 1] Case 4 value found -> '{text}'")
                return text

        if is_key_text(text, aliases_norm):
            logger.info(
                f"[PHASE 1] Same-row text '{text}' is another key -- "
                f"stopping row search."
            )
            return None

    return None

# ============================================================
# PHASE 2 DOWN COLUMN SEARCH
# ============================================================

def extract_phase2_down_column_value(key_item, ocr_items, all_keys_norm, tables):
    if should_block_down_search(key_item, tables):
        logger.info(
            "[PHASE 2] DOWN SEARCH BLOCKED -- key is inside a docling table. "
            "No down-column extraction for this key."
        )
        return None

    key_x1, key_y1, key_x2, key_y2 = get_bbox_from_polygon(key_item["coordinates"])
    key_cx, key_cy = get_center(key_item["coordinates"])

    candidates = []
    for item in ocr_items:
        if item is key_item:
            continue
        x1_t, y1_t, x2_t, y2_t = get_bbox_from_polygon(item["coordinates"])
        cy = (y1_t + y2_t) / 2
        column_overlap = (x2_t >= key_x1 and x1_t <= key_x2)
        if cy > key_y2 and column_overlap:
            candidates.append((cy, item))
    candidates.sort(key=lambda x: x[0])

    values  = []
    prev_cy = key_cy

    for cy, item in candidates:
        gap = cy - prev_cy
        if gap > COLUMN_GAP_THRESHOLD:
            logger.info(
                f"[PHASE 2] Gap {gap:.1f}px > {COLUMN_GAP_THRESHOLD}px -- "
                f"stopping column walk at '{item['text'].strip()}'."
            )
            break
        text = item["text"].strip()
        if not text:
            prev_cy = cy
            continue
        if is_any_document_key(text, all_keys_norm):
            logger.info(f"[PHASE 2] '{text}' is another key -- stopping column walk.")
            break
        values.append(text)
        prev_cy = cy

    return ", ".join(values) if values else None

# ============================================================
# PHASE 3 HELPERS
#
# CHANGES vs previous version:
#   1. 3-way far-row threshold:
#        key in DOCLING table        -> keyinside_table_value_FAR_ROW_THRESHOLD (2500 px)
#        key in REGION-ONLY table    -> PHASE3_REGION_TABLE_THRESHOLD (400 px)
#        key outside any table       -> PHASE3_HORIZONTAL_FAR_THRESHOLD (1500 px)
#      If a region table overlaps a docling table, the docling table wins
#      (is_key_in_region_table_only returns False in that case).
#   2. Header guard:
#        - If key is a TABLE HEADER (is_header=True in its docling table)
#          -> return None immediately (block row AND down search for this occurrence).
#        - If the closest valid same-row candidate is a TABLE HEADER
#          -> return None (block row AND down search for this occurrence).
#      In both cases the Phase 3 loop continues to the next key occurrence.
#   3. Down-search guard: unchanged (overlap-aware).
# ============================================================

def is_exact_key_match(text, aliases_norm):
    cleaned = normalize_text(strip_trailing_separator(text))
    return any(cleaned == alias for alias in aliases_norm)

def is_too_far_horizontally(key_cx, candidate_cx, threshold=PHASE3_HORIZONTAL_FAR_THRESHOLD):
    return abs(candidate_cx - key_cx) > threshold

def extract_phase3_down_column_value(key_item, ocr_items, all_keys_norm, tables, regions):
    """
    Phase 3 down-column search.
    Uses overlap-aware table guard: blocked when key falls inside a
    docling table bbox (possibly enlarged by an overlapping region table).
    """
    if should_block_down_search_overlap_aware(key_item, tables, regions):
        logger.info(
            "[PHASE 3][DOWN] BLOCKED by overlap-aware table guard -- "
            "key is inside an effective table bbox. "
            "No down-column extraction for this key occurrence."
        )
        return None

    key_x1, key_y1, key_x2, key_y2 = get_bbox_from_polygon(key_item["coordinates"])
    key_cx, key_cy = get_center(key_item["coordinates"])

    candidates = []
    for item in ocr_items:
        if item is key_item:
            continue
        x1_t, y1_t, x2_t, y2_t = get_bbox_from_polygon(item["coordinates"])
        cy = (y1_t + y2_t) / 2
        column_overlap = (x2_t >= key_x1 and x1_t <= key_x2)
        if cy > key_y2 and column_overlap:
            candidates.append((cy, item))
    candidates.sort(key=lambda x: x[0])

    values  = []
    prev_cy = key_cy

    for cy, item in candidates:
        gap = cy - prev_cy
        if gap > COLUMN_GAP_THRESHOLD:
            logger.info(
                f"[PHASE 3][DOWN] Gap {gap:.1f}px > {COLUMN_GAP_THRESHOLD}px -- "
                f"stopping at '{item['text'].strip()}'."
            )
            break
        text = item["text"].strip()
        if not text:
            prev_cy = cy
            continue
        if is_any_document_key(text, all_keys_norm):
            logger.info(f"[PHASE 3][DOWN] '{text}' is another key -- stopping.")
            break
        values.append(text)
        prev_cy = cy

    return ", ".join(values) if values else None


def extract_phase3_value(
    key_item,
    region_ocr,
    aliases_norm,
    tables,
    all_keys_norm,
    regions=None
):
    """
    Same-row value lookup for Phase 3, with 3-way dynamic far-row threshold
    and header guard.

    CHANGE 1 -- 3-way threshold (Requirement 1):
      key in DOCLING table        -> 2500 px  (keyinside_table_value_FAR_ROW_THRESHOLD)
      key in REGION-ONLY table    -> 400 px   (PHASE3_REGION_TABLE_THRESHOLD)
      key outside any table       -> 1500 px  (PHASE3_HORIZONTAL_FAR_THRESHOLD)

    CHANGE 2 -- Header guard (Requirement 2):
      If key is a table header (is_header=True in its docling table), OR
      the nearest valid same-row candidate is a table header, return None
      immediately -- blocking both row search and down search for this
      key occurrence. Phase 3 loop will continue to the next item.
    """
    if regions is None:
        regions = []

    key_cx, key_cy = get_center(key_item["coordinates"])
    key_text = key_item["text"].strip()

    # ----------------------------------------------------------
    # CHANGE 1: Determine far-row threshold (3-way)
    # ----------------------------------------------------------
    key_table = get_table_containing_key(key_item, tables)   # docling table or None

    if key_table:
        # Key is inside a docling table.
        # Region table overlapping docling is treated as docling (req 1).
        far_threshold = keyinside_table_value_FAR_ROW_THRESHOLD   # 2500
        logger.info(
            f"[PHASE 3] Key '{key_text}' is inside DOCLING TABLE "
            f"{key_table.get('table_bbox')} -- using far-row threshold "
            f"{far_threshold}px."
        )
    elif is_key_in_region_table_only(key_item, tables, regions):
        # Key is inside a region-layout 'table' that does NOT overlap any
        # docling table (independent region table).
        far_threshold = PHASE3_REGION_TABLE_THRESHOLD   # 400
        logger.info(
            f"[PHASE 3] Key '{key_text}' is inside a REGION-ONLY table "
            f"(no overlapping docling table) -- using far-row threshold "
            f"{far_threshold}px."
        )
    else:
        # Key is outside any table.
        far_threshold = PHASE3_HORIZONTAL_FAR_THRESHOLD   # 1500
        logger.info(
            f"[PHASE 3] Key '{key_text}' is outside any table -- using "
            f"far-row threshold {far_threshold}px."
        )

    # ----------------------------------------------------------
    # CHANGE 2a: Key header guard
    # If the key OCR item maps to a header cell in its docling table,
    # block row AND down search for this occurrence entirely.
    # ----------------------------------------------------------
    if key_table and is_ocr_item_header_in_table(key_item, key_table):
        logger.info(
            f"[PHASE 3] *** KEY IS A TABLE HEADER (is_header=True) for "
            f"'{key_text}' in table {key_table.get('table_bbox')}. "
            f"Blocking row search AND down search. "
            f"Searching further on the same page (continuing Phase 3 loop)."
        )
        return None

    # ----------------------------------------------------------
    # Same-row candidate search
    # ----------------------------------------------------------
    same_row_candidates = []
    for item in region_ocr:
        if item is key_item:
            continue
        cx, cy = get_center(item["coordinates"])
        if abs(cy - key_cy) <= SAME_ROW_Y_TOLERANCE and cx > key_cx:
            same_row_candidates.append((cx, item))
    same_row_candidates.sort(key=lambda x: x[0])

    if not same_row_candidates:
        logger.info(
            f"[PHASE 3] No same-row candidates found to the right of '{key_text}'. "
            f"Falling to down-column search."
        )
        return extract_phase3_down_column_value(
            key_item, region_ocr, all_keys_norm, tables, regions
        )

    for cx, item in same_row_candidates:
        value = item["text"].strip()

        # Another key -> fall to down search
        if is_any_document_key(value, all_keys_norm):
            logger.info(
                f"[PHASE 3] Same-row candidate '{value}' is another key -- "
                f"falling to down-column search."
            )
            return extract_phase3_down_column_value(
                key_item, region_ocr, all_keys_norm, tables, regions
            )

        # Too far -> fall to down search
        if is_too_far_horizontally(key_cx, cx, far_threshold):
            logger.info(
                f"[PHASE 3] Same-row candidate '{value}' is too far "
                f"({abs(cx - key_cx):.0f}px > {far_threshold}px) -- "
                f"falling to down-column search."
            )
            return extract_phase3_down_column_value(
                key_item, region_ocr, all_keys_norm, tables, regions
            )

        # CHANGE 2b: Value header guard
        # If this candidate maps to a table header cell, block BOTH
        # row search AND down search for this key occurrence.
        if key_table and is_ocr_item_header_in_table(item, key_table):
            logger.info(
                f"[PHASE 3] *** SAME-ROW VALUE '{value}' IS A TABLE HEADER "
                f"(is_header=True). Blocking row search AND down search. "
                f"Searching further on the same page (continuing Phase 3 loop)."
            )
            return None

        logger.info(
            f"[PHASE 3] Same-row value found: '{value}' "
            f"(distance from key: {abs(cx - key_cx):.0f}px, threshold: {far_threshold}px)."
        )
        return value

    logger.info(
        f"[PHASE 3] All same-row candidates exhausted without a valid value. "
        f"Falling to down-column search."
    )
    return extract_phase3_down_column_value(
        key_item, region_ocr, all_keys_norm, tables, regions
    )

# ============================================================
# PHASE 4 HELPERS
#
# CHANGE: Any key found inside a table (docling OR region_layout
# 'table') is now COMPLETELY SKIPPED in Phase 4.  The block is
# applied in find_key_value before calling the row/down helpers.
# Row and down helpers are unchanged and only reached for
# non-table keys.
# ============================================================

def does_box_overlap_layout(ocr_box, region_box):
    x1, y1, x2, y2 = get_bbox_from_polygon(ocr_box)
    rx1, ry1, rx2, ry2 = region_box
    return not (x2 < rx1 or x1 > rx2 or y2 < ry1 or y1 > ry2)

def get_layout_center_y(region_box):
    _, ry1, _, ry2 = region_box
    return (ry1 + ry2) / 2

def get_layout_center_x(region_box):
    rx1, _, rx2, _ = region_box
    return (rx1 + rx2) / 2

def touches_layout(ocr_box, region_box):
    x1, y1, x2, y2 = get_bbox_from_polygon(ocr_box)
    rx1, ry1, rx2, ry2 = region_box
    return not (x2 < rx1 or x1 > rx2 or y2 < ry1 or y1 > ry2)

def extract_phase4_row_value(
    key_item, ocr_items, regions, aliases_norm,
    tables=None, row_tolerance=SAME_ROW_Y_TOLERANCE
):
    """
    Same-row value lookup for Phase 4.

    NOTE: By the time this is called, the key is guaranteed to be
    OUTSIDE any table (the Phase 4 loop now blocks all table keys
    before reaching here). The three-way threshold is therefore
    simplified:
      key has NO separator  -> PHASE4_ROW_OUTSIDE_NO_SEP_THRESHOLD (2000 px)
      key HAS separator     -> PHASE4_ROW_OUTSIDE_WITH_SEP_THRESHOLD (800 px)
    (The table-inside branch is kept for safety but should never fire.)
    """
    key_cx, key_cy = get_center(key_item["coordinates"])
    key_text = key_item["text"].strip()

    # Determine threshold (table branches kept for safety)
    if tables is not None and is_key_in_table_region(key_item, tables):
        phase4_far_threshold = keyinside_table_value_FAR_ROW_THRESHOLD
        logger.info(
            f"[PHASE 4][ROW] Key '{key_text}' is inside a DOCLING table -- "
            f"threshold {phase4_far_threshold}px (should not normally reach here)."
        )
    elif is_key_in_region_table_only(key_item, tables, regions):
        phase4_far_threshold = PHASE4_HORIZONTAL_FAR_THRESHOLD
        logger.info(
            f"[PHASE 4][ROW] Key '{key_text}' is inside a REGION table -- "
            f"threshold {phase4_far_threshold}px (should not normally reach here)."
        )
    elif has_separator(key_text):
        phase4_far_threshold = PHASE4_ROW_OUTSIDE_WITH_SEP_THRESHOLD
        logger.info(
            f"[PHASE 4][ROW] Key '{key_text}' is outside any table and HAS a separator -- "
            f"using threshold {phase4_far_threshold}px."
        )
    else:
        phase4_far_threshold = PHASE4_ROW_OUTSIDE_NO_SEP_THRESHOLD
        logger.info(
            f"[PHASE 4][ROW] Key '{key_text}' is outside any table and has NO separator -- "
            f"using threshold {phase4_far_threshold}px."
        )

    same_row = []
    for item in ocr_items:
        if item is key_item:
            continue
        cx, cy = get_center(item["coordinates"])
        if abs(cy - key_cy) <= row_tolerance and cx > key_cx:
            same_row.append((cx, item))
    same_row.sort(key=lambda x: x[0])

    key_regions = {
        id(r) for r in regions
        if does_box_overlap_layout(key_item["coordinates"], r["coordinate"])
    }

    for cx, item in same_row:
        # Rule 2a: layout center lies between key and candidate -> break
        layout_blocks_row = False
        for region in regions:
            region_box = region["coordinate"]
            layout_cx  = get_layout_center_x(region_box)
            layout_cy  = get_layout_center_y(region_box)
            if (
                abs(layout_cy - key_cy) <= row_tolerance
                and layout_cx > key_cx
                and layout_cx <= cx
            ):
                logger.info(
                    f"[PHASE 4][ROW] Rule 2a -- layout region center "
                    f"({layout_cx:.0f}, {layout_cy:.0f}) lies between key and "
                    f"candidate '{item['text'].strip()}'. "
                    f"Row search blocked. Falling to down search."
                )
                layout_blocks_row = True
                break
        if layout_blocks_row:
            break

        # Rule 2b: candidate overlaps a foreign layout region -> skip
        overlaps = any(
            does_box_overlap_layout(item["coordinates"], r["coordinate"])
            for r in regions
            if id(r) not in key_regions
        )
        if overlaps:
            logger.info(
                f"[PHASE 4][ROW] Rule 2b -- '{item['text'].strip()}' overlaps "
                f"a foreign layout region -- skipping this candidate."
            )
            continue

        # Rule 2d: candidate too far -> break
        if abs(cx - key_cx) > phase4_far_threshold:
            logger.info(
                f"[PHASE 4][ROW] Rule 2d -- '{item['text'].strip()}' is too far "
                f"({abs(cx - key_cx):.0f}px > {phase4_far_threshold}px) -- "
                f"stopping row search."
            )
            break

        # Rule 2c: valid value
        text = item["text"].strip()
        if text and not is_key_text(text, aliases_norm):
            logger.info(f"[PHASE 4][ROW] Rule 2c -- row value found: '{text}'.")
            return text, "found"

    return None, "exhausted"


def extract_phase4_down_value(key_item, ocr_items, regions, tables, all_keys_norm):
    """
    Phase 4 down search -- uses key bbox x1..x2 as column window.
    Down-search is blocked when the key falls inside any effective
    table bbox (overlap-aware guard).
    """
    if should_block_down_search_overlap_aware(key_item, tables, regions):
        logger.info(
            "[PHASE 4][DOWN] BLOCKED by overlap-aware table guard. "
            "No down-column extraction for this key."
        )
        return None

    key_x1, key_y1, key_x2, key_y2 = get_bbox_from_polygon(key_item["coordinates"])
    key_cx, key_cy = get_center(key_item["coordinates"])

    candidates = []
    for item in ocr_items:
        if item is key_item:
            continue
        x1_t, y1_t, x2_t, y2_t = get_bbox_from_polygon(item["coordinates"])
        cy = (y1_t + y2_t) / 2
        column_overlap = (x2_t >= key_x1 and x1_t <= key_x2)
        if cy > key_y2 and column_overlap:
            candidates.append((cy, item))
    candidates.sort(key=lambda x: x[0])

    def collect_region_texts(region_box):
        region_texts = []
        prev_ry = key_cy
        for ritem in sort_items_top_to_bottom(ocr_items):
            if ritem is key_item:
                continue
            if not is_inside_region(ritem["coordinates"], region_box):
                continue
            x1_t, y1_t, x2_t, y2_t = get_bbox_from_polygon(ritem["coordinates"])
            if not (x2_t >= key_x1 and x1_t <= key_x2):
                continue
            rcy   = (y1_t + y2_t) / 2
            rtext = ritem["text"].strip()
            if not rtext:
                continue
            if is_any_document_key(rtext, all_keys_norm):
                logger.info(f"[PHASE 4][DOWN] Collect: '{rtext}' is a key -- stopping collect.")
                break
            if (rcy - prev_ry) > PHASE4_LAYOUT_COLLECT_GAP:
                logger.info(f"[PHASE 4][DOWN] Collect: gap break at '{rtext}'.")
                break
            region_texts.append(rtext)
            prev_ry = rcy
        return region_texts

    # STEP 1: find TEXT layout region directly below key
    text_region_found = None

    for region in regions:
        if region.get("label", "").lower() != "text":
            continue
        if touches_layout(key_item["coordinates"], region["coordinate"]):
            text_region_found = region
            logger.info("[PHASE 4][DOWN] STEP 1 -- key directly overlaps a TEXT layout region.")
            break

    if text_region_found:
        region_texts = collect_region_texts(text_region_found["coordinate"])
        if region_texts:
            value = ", ".join(region_texts)
            logger.info(f"[PHASE 4][DOWN] STEP 1 (key-overlap) value: '{value}'.")
            return value
        logger.info(
            "[PHASE 4][DOWN] STEP 1 -- key overlaps TEXT region but collected nothing. "
            "Falling to candidate walk."
        )
        text_region_found = None

    prev_cy_step1 = key_cy
    for cy, item in candidates:
        gap = cy - prev_cy_step1
        if gap > PHASE4_DOWN_GAP_THRESHOLD:
            logger.info(
                f"[PHASE 4][DOWN] STEP 1 -- gap {gap:.1f}px exceeded before "
                f"finding a TEXT region. Falling to STEP 2."
            )
            break
        text = item["text"].strip()
        if not text:
            prev_cy_step1 = cy
            continue
        if is_any_document_key(text, all_keys_norm):
            logger.info(
                f"[PHASE 4][DOWN] STEP 1 -- '{text}' is a key. "
                f"No TEXT region found above it. Falling to STEP 2."
            )
            break
        for region in regions:
            if region.get("label", "").lower() != "text":
                continue
            if is_inside_region(item["coordinates"], region["coordinate"]):
                text_region_found = region
                logger.info("[PHASE 4][DOWN] STEP 1 -- TEXT layout region found below key.")
                break
        if text_region_found:
            break
        prev_cy_step1 = cy

    if text_region_found:
        region_texts = collect_region_texts(text_region_found["coordinate"])
        if region_texts:
            value = ", ".join(region_texts)
            logger.info(f"[PHASE 4][DOWN] STEP 1 value: '{value}'.")
            return value
        logger.info("[PHASE 4][DOWN] STEP 1 -- text region empty. Falling to STEP 2.")

    # STEP 2: walk candidates, handle region overlaps
    logger.info("[PHASE 4][DOWN] STEP 2 -- walking column candidates.")
    prev_cy = key_cy

    for cy, item in candidates:
        text = item["text"].strip()
        if not text:
            prev_cy = cy
            continue
        gap = cy - prev_cy
        if gap > PHASE4_DOWN_GAP_THRESHOLD:
            logger.info(
                f"[PHASE 4][DOWN] STEP 2 -- gap {gap:.1f}px > "
                f"{PHASE4_DOWN_GAP_THRESHOLD}px at '{text}'. Stopping."
            )
            break
        if is_any_document_key(text, all_keys_norm):
            logger.info(f"[PHASE 4][DOWN] STEP 2 -- '{text}' is another key. Stopping.")
            break

        touching_region = None
        for region in regions:
            if touches_layout(item["coordinates"], region["coordinate"]):
                touching_region = region
                break

        if touching_region is not None:
            region_label = touching_region.get("label", "").lower()
            region_box   = touching_region["coordinate"]
            if region_label == "text":
                logger.info(f"[PHASE 4][DOWN] STEP 2 -- '{text}' overlaps TEXT region. Collecting.")
                region_texts = collect_region_texts(region_box)
                if region_texts:
                    value = ", ".join(region_texts)
                    logger.info(f"[PHASE 4][DOWN] STEP 2 text-region value: '{value}'.")
                    return value
                prev_cy = cy
                continue
            else:
                logger.info(
                    f"[PHASE 4][DOWN] STEP 2 -- '{text}' overlaps '{region_label}' region. "
                    f"Picking this text and stopping."
                )
                return text

        logger.info(f"[PHASE 4][DOWN] STEP 2 -- plain text value found: '{text}'.")
        return text

    return None

# ============================================================
# PHASE 5 HELPERS
#
# CHANGES vs previous version:
#   1. Header guard -- key is header  -> skip row search in Pass A,
#      fall through to down search in Pass B.
#   2. Header guard -- value is header -> skip that value in row
#      search; if all row candidates are headers, return None and
#      fall through to down search in Pass B.
#   3. Down-column search skips cells/OCR items with is_header=True.
#   4. Down-column search breaks on gap > PHASE5_COLUMN_GAP_THRESHOLD
#      (was already in cell-based path; now explicitly logged).
# ============================================================

def extract_phase5_row_value(key_item, ocr_items, aliases_norm, all_keys_norm, table):
    """
    Same-row value lookup, restricted to OCR boxes inside the given
    table's table_bbox.

    CHANGE: OCR items that correspond to a header cell (is_header=True)
    in this table are skipped -- they are labels, not values.
    """
    table_box = table.get("table_bbox")
    if not table_box or len(table_box) != 4:
        return None

    key_cx, key_cy = get_center(key_item["coordinates"])

    table_ocr = [
        item for item in ocr_items
        if item is not key_item and is_inside_region(item["coordinates"], table_box)
    ]

    same_row = []
    for item in table_ocr:
        cx, cy = get_center(item["coordinates"])
        if abs(cy - key_cy) <= SAME_ROW_Y_TOLERANCE and cx > key_cx:
            same_row.append((cx, item))
    same_row.sort(key=lambda x: x[0])

    for cx, item in same_row:
        text = item["text"].strip()
        if not text:
            continue

        if is_any_document_key(text, all_keys_norm):
            logger.info(
                f"[PHASE 5][ROW] '{text}' is another key -- "
                f"stopping row search for this table key."
            )
            return None

        if is_too_far_horizontally(key_cx, cx, PHASE5_FAR_ROW_THRESHOLD):
            logger.info(
                f"[PHASE 5][ROW] '{text}' is too far "
                f"({abs(cx - key_cx):.0f}px > {PHASE5_FAR_ROW_THRESHOLD}px) -- "
                f"stopping row search."
            )
            return None

        # CHANGE: Skip header cells -- they are structural labels, not values
        if is_ocr_item_header_in_table(item, table):
            logger.info(
                f"[PHASE 5][ROW] '{text}' is a TABLE HEADER (is_header=True) -- "
                f"skipping this candidate. Trying next same-row candidate."
            )
            continue

        logger.info(
            f"[PHASE 5][ROW] Row value found: '{text}' "
            f"(table_bbox={table_box})."
        )
        return text

    return None


def extract_phase5_down_column_value(key_item, ocr_items, all_keys_norm, table=None):
    """
    Collect text below key where x-range overlaps key x1..x2.

    CHANGE: If `table` is provided, OCR items that correspond to a
    header cell (is_header=True) in that table are skipped.
    Gap > PHASE5_COLUMN_GAP_THRESHOLD breaks the walk.
    """
    key_x1, key_y1, key_x2, key_y2 = get_bbox_from_polygon(key_item["coordinates"])
    key_cx, key_cy = get_center(key_item["coordinates"])

    candidates = []
    for item in ocr_items:
        if item is key_item:
            continue
        x1_t, y1_t, x2_t, y2_t = get_bbox_from_polygon(item["coordinates"])
        cy = (y1_t + y2_t) / 2
        column_overlap = (x2_t >= key_x1 and x1_t <= key_x2)
        if cy > key_y2 and column_overlap:
            candidates.append((cy, item))
    candidates.sort(key=lambda x: x[0])

    values  = []
    prev_cy = key_cy

    for cy, item in candidates:
        gap = cy - prev_cy
        if gap > PHASE5_COLUMN_GAP_THRESHOLD:
            logger.info(
                f"[PHASE 5][DOWN] Gap {gap:.1f}px > {PHASE5_COLUMN_GAP_THRESHOLD}px -- "
                f"stopping column walk at '{item['text'].strip()}'. "
                f"Items below are too far away."
            )
            break

        value = item["text"].strip()
        if not value:
            prev_cy = cy
            continue

        if is_key_text(value, all_keys_norm):
            logger.info(
                f"[PHASE 5][DOWN] '{value}' is another key -- "
                f"stopping column walk."
            )
            break

        # CHANGE: Skip OCR items that correspond to header cells in this table
        if table and is_ocr_item_header_in_table(item, table):
            logger.info(
                f"[PHASE 5][DOWN] '{value}' is a TABLE HEADER (is_header=True) -- "
                f"skipping this item in down-column search."
            )
            prev_cy = cy
            continue

        logger.info(
            f"[PHASE 5][DOWN] Collecting value: '{value}' "
            f"(gap from previous={gap:.1f}px)."
        )
        values.append(value)
        prev_cy = cy

    if values:
        result = ", ".join(values)
        logger.info(f"[PHASE 5][DOWN] Column value assembled: '{result}'.")
        return result
    return None

# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def find_key_value(label_cfg, page_data, all_keys_norm):

    original_label   = label_cfg["label_name"]
    original_aliases = label_cfg.get("aliases", [])
    label_name_norm  = normalize_text(original_label)
    aliases_norm     = [label_name_norm] + [normalize_text(a) for a in original_aliases]

    ocr_items = sort_items_top_to_bottom(page_data["ocr"])
    regions   = sort_regions_top_to_bottom(page_data["layout"]["region_layout"])
    tables    = sort_tables_top_to_bottom(page_data.get("tables", []))

    logger.info("=" * 60)
    logger.info(f"[START] Searching for key -> '{original_label}'")
    logger.info(
        f"[START] Page has {len(ocr_items)} OCR items, "
        f"{len(regions)} layout regions, {len(tables)} docling tables."
    )
    logger.info("=" * 60)

    # ========================================================
    # PHASE 1 -- FULL PAGE SEARCH
    # Strategy: scan every OCR item; key part must exactly equal
    # an alias; value found inline or on the same row (no down search).
    # ========================================================

    logger.info(f"[PHASE 1] -- FULL PAGE SEARCH -- key: '{original_label}'")
    phase1_found = False

    for item in ocr_items:
        text      = item["text"]
        text_norm = normalize_text(text)

        alias_present = any(is_alias_match(alias, text_norm) for alias in aliases_norm)
        if not alias_present:
            continue

        if not phase1_key_fully_matches(text, aliases_norm):
            logger.info(
                f"[PHASE 1] SKIP '{text}' -- alias is present in text but "
                f"the key part (left of separator) does not exactly equal "
                f"any alias. Moving to next OCR item."
            )
            continue

        matched_by, match_type = get_matched_alias(
            text_norm, label_name_norm, original_label, original_aliases
        )
        if not matched_by:
            continue

        phase1_found = True
        logger.info(f"[PHASE 1] Key matched -> '{text}'")

        # Case 1 -- inline separator (e.g. "Invoice #: 562023")
        value = extract_inline_value(text, aliases_norm)
        if value:
            logger.info(
                f"[PHASE 1] Case 1 -- inline value extracted: '{value}'. "
                f"Returning result."
            )
            return {
                "label_name": original_label,
                "required": label_cfg["required"],
                "data_type": label_cfg["data_type"],
                "retrived_dtype": detect_value_dtype(value),
                "value": value,
                "foundkey": text,
                "matched_by": matched_by,
                "match_type": match_type,
                "phase": "phase1_inline"
            }

        logger.info(
            "[PHASE 1] Case 1 -- no inline value (no separator in text, "
            "or right side of separator is empty/another key). "
            "Trying same-line search (Cases 2-4)."
        )

        # Cases 2-4 -- same-row, no down search
        value = extract_same_line_value(item, ocr_items, aliases_norm, regions)
        if value:
            logger.info(
                f"[PHASE 1] Cases 2-4 -- same-line value found: '{value}'. "
                f"Returning result."
            )
            return {
                "label_name": original_label,
                "required": label_cfg["required"],
                "data_type": label_cfg["data_type"],
                "retrived_dtype": detect_value_dtype(value),
                "value": value,
                "foundkey": text,
                "matched_by": matched_by,
                "match_type": match_type,
                "phase": "phase1_same_line"
            }

        logger.info(
            f"[PHASE 1] Cases 2-4 -- no same-line value found for '{text}'. "
            f"Continuing to next OCR item."
        )

    if not phase1_found:
        logger.info(
            f"[PHASE 1] FAILED -- no OCR item on the full page matched key "
            f"'{original_label}' with an exact key-part alias. "
            f"Moving to Phase 2."
        )
    else:
        logger.info(
            f"[PHASE 1] FAILED -- key was matched but no value was found "
            f"(inline or same-line). Moving to Phase 2."
        )

    # ========================================================
    # PHASE 2 -- REGION SEARCH (layout regions only)
    # Strategy: within each layout region, find an exact key match
    # that has a separator; then search down-column for value.
    # (No same-row search; separator is required.)
    # ========================================================

    logger.info(f"[PHASE 2] -- REGION SEARCH -- key: '{original_label}'")
    phase2_found = False

    for region in regions:
        region_box   = region["coordinate"]
        region_label = region.get("label", "unknown")

        region_ocr = sort_items_top_to_bottom([
            item for item in ocr_items
            if is_inside_region(item["coordinates"], region_box)
        ])

        for item in region_ocr:
            text      = item["text"]
            text_norm = normalize_text(text)

            alias_present = any(is_alias_match(alias, text_norm) for alias in aliases_norm)
            if not alias_present:
                continue

            if not is_exact_foundkey_match(text, aliases_norm):
                logger.info(
                    f"[PHASE 2] SKIP '{text}' in region '{region_label}' -- "
                    f"alias present but stripped text does not exactly equal "
                    f"any alias (may still carry extra characters)."
                )
                continue

            matched_by, match_type = get_matched_alias(
                text_norm, label_name_norm, original_label, original_aliases
            )
            if not matched_by:
                continue

            phase2_found = True
            logger.info(
                f"[PHASE 2] Key matched in region '{region_label}' -> '{text}'"
            )

            if not has_separator(text):
                logger.info(
                    f"[PHASE 2] '{text}' has NO separator -- Phase 2 requires "
                    f"a separator for down-column search. Skipping to Phase 3."
                )
                continue

            logger.info(
                f"[PHASE 2] Separator found in '{text}' -- attempting "
                f"down-column search within region '{region_label}'."
            )
            value = extract_phase2_down_column_value(item, region_ocr, all_keys_norm, tables)
            if value:
                logger.info(
                    f"[PHASE 2] Down-column value found: '{value}'. Returning result."
                )
                return {
                    "label_name": original_label,
                    "required": label_cfg["required"],
                    "data_type": label_cfg["data_type"],
                    "retrived_dtype": detect_value_dtype(value),
                    "value": value,
                    "foundkey": text,
                    "matched_by": matched_by,
                    "match_type": match_type,
                    "phase": "phase2_down_column"
                }

            logger.info(
                f"[PHASE 2] Down-column search found nothing below '{text}'. "
                f"Continuing to next item in region."
            )

    if not phase2_found:
        logger.info(
            f"[PHASE 2] FAILED -- no exact key match with a separator found "
            f"in any layout region. Moving to Phase 3."
        )
    else:
        logger.info(
            f"[PHASE 2] FAILED -- key(s) matched but down-column search "
            f"returned nothing. Moving to Phase 3."
        )

    # ========================================================
    # PHASE 3 -- EXACT KEY SEARCH WITHIN REGIONS
    # Strategy: within each layout region, find an exact key match
    # (no separator required); search same-row then down-column.
    #
    # CHANGES:
    #   * 3-way far-row threshold (docling->2500, region-only->400, none->1500)
    #   * Key or value that is a table header blocks row+down for
    #     that occurrence; Phase 3 loop continues to next item.
    # ========================================================

    logger.info(f"[PHASE 3] -- EXACT KEY SEARCH IN REGIONS -- key: '{original_label}'")
    phase3_found = False

    for region in regions:
        region_box   = region["coordinate"]
        region_label = region.get("label", "unknown")

        region_ocr = sort_items_top_to_bottom([
            item for item in ocr_items
            if is_inside_region(item["coordinates"], region_box)
        ])

        for item in region_ocr:
            text = item["text"]

            if not is_exact_key_match(text, aliases_norm):
                text_norm = normalize_text(text)
                if any(is_alias_match(alias, text_norm) for alias in aliases_norm):
                    logger.info(
                        f"[PHASE 3] SKIP '{text}' in region '{region_label}' -- "
                        f"alias present but text has a leading/trailing separator "
                        f"or is not an exact match after stripping."
                    )
                continue

            matched_by, match_type = get_matched_alias(
                normalize_text(text), label_name_norm, original_label, original_aliases
            )
            if not matched_by:
                continue

            phase3_found = True
            logger.info(
                f"[PHASE 3] Exact key match in region '{region_label}' -> '{text}'"
            )

            value = extract_phase3_value(
                item, region_ocr, aliases_norm, tables, all_keys_norm, regions
            )
            if value:
                logger.info(
                    f"[PHASE 3] Value found for '{text}': '{value}'. Returning result."
                )
                return {
                    "label_name": original_label,
                    "required": label_cfg["required"],
                    "data_type": label_cfg["data_type"],
                    "retrived_dtype": detect_value_dtype(value),
                    "value": value,
                    "foundkey": text,
                    "matched_by": matched_by,
                    "match_type": match_type,
                    "phase": "phase3_region"
                }

            logger.info(
                f"[PHASE 3] No value found for '{text}' (either blocked by "
                f"header guard, or row+down search returned nothing). "
                f"Continuing to next item."
            )

    if not phase3_found:
        logger.info(
            f"[PHASE 3] FAILED -- no exact key match found in any layout region. "
            f"Moving to Phase 4."
        )
    else:
        logger.info(
            f"[PHASE 3] FAILED -- key(s) matched but no value extracted "
            f"(header guard or empty searches). Moving to Phase 4."
        )

    # ========================================================
    # PHASE 4 -- GLOBAL LAYOUT-AWARE SEARCH
    # Strategy: scan full page; row search first, down search fallback.
    #
    # CHANGE: Any key found inside ANY table (docling OR region_layout
    # 'table') is completely skipped.  Phase 4 is table-free.
    # ========================================================

    logger.info(f"[PHASE 4] -- GLOBAL LAYOUT-AWARE SEARCH -- key: '{original_label}'")
    phase4_found = False

    for item in ocr_items:
        text      = item["text"]
        text_norm = normalize_text(text)

        alias_present = any(is_alias_match(alias, text_norm) for alias in aliases_norm)
        if not alias_present:
            continue

        if not is_exact_foundkey_match(text, aliases_norm):
            logger.info(
                f"[PHASE 4] SKIP '{text}' -- alias present but not an exact "
                f"foundkey match (extra chars after stripping separator)."
            )
            continue

        matched_by, match_type = get_matched_alias(
            text_norm, label_name_norm, original_label, original_aliases
        )
        if not matched_by:
            continue

        # CHANGE: Completely block table keys in Phase 4
        if is_key_in_any_table_or_region(item, tables, regions):
            logger.info(
                f"[PHASE 4] *** SKIP '{text}' -- key is inside a TABLE "
                f"(docling or region_layout 'table'). "
                f"Phase 4 is table-free: table keys are handled exclusively "
                f"by Phase 5. Searching further on the same page."
            )
            continue

        phase4_found = True
        logger.info(
            f"[PHASE 4] Key matched (outside any table) -> '{text}'. "
            f"Starting row search."
        )

        value, stop_reason = extract_phase4_row_value(
            item, ocr_items, regions, aliases_norm, tables
        )
        if value:
            logger.info(
                f"[PHASE 4] Row search succeeded: '{value}'. Returning result."
            )
            return {
                "label_name": original_label,
                "required": label_cfg["required"],
                "data_type": label_cfg["data_type"],
                "retrived_dtype": detect_value_dtype(value),
                "value": value,
                "foundkey": text,
                "matched_by": matched_by,
                "match_type": match_type,
                "phase": "phase4_row"
            }

        logger.info(
            f"[PHASE 4] Row search returned nothing (reason: {stop_reason}). "
            f"Falling to down-column search."
        )
        value = extract_phase4_down_value(item, ocr_items, regions, tables, all_keys_norm)
        if value:
            logger.info(
                f"[PHASE 4] Down-column search succeeded: '{value}'. Returning result."
            )
            return {
                "label_name": original_label,
                "required": label_cfg["required"],
                "data_type": label_cfg["data_type"],
                "retrived_dtype": detect_value_dtype(value),
                "value": value,
                "foundkey": text,
                "matched_by": matched_by,
                "match_type": match_type,
                "phase": "phase4_down"
            }

        logger.info(
            f"[PHASE 4] Both row and down search returned nothing for '{text}'. "
            f"Continuing to next OCR item."
        )

    if not phase4_found:
        logger.info(
            f"[PHASE 4] FAILED -- no key match found outside tables on the full page. "
            f"Moving to Phase 5."
        )
    else:
        logger.info(
            f"[PHASE 4] FAILED -- key(s) matched but no value extracted "
            f"(row and down searches both empty). Moving to Phase 5."
        )

    # ========================================================
    # PHASE 5 -- TABLE KEY SEARCH  (docling tables only)
    # Strategy: find key inside a docling table; try row search
    # (Pass A) then down-column search (Pass B).
    #
    # CHANGES:
    #   1. If key is a table header (is_header=True):
    #        - Skip Pass A (row search) for this key.
    #        - Fall through to Pass B (down-column search).
    #   2. In Pass A row search: value candidates that are table
    #        headers are skipped; if none remain, fall to Pass B.
    #   3. In Pass B down-column search: header values are skipped;
    #        gap > PHASE5_COLUMN_GAP_THRESHOLD breaks the walk.
    # ========================================================

    logger.info(f"[PHASE 5] -- TABLE KEY SEARCH (docling tables only) -- key: '{original_label}'")

    table_key_candidates = []

    # Collect OCR-based table key candidates
    for item in ocr_items:
        text      = item["text"]
        text_norm = normalize_text(text)

        alias_present = any(is_alias_match(alias, text_norm) for alias in aliases_norm)
        if not alias_present:
            continue

        if not is_exact_foundkey_match(text, aliases_norm):
            logger.info(
                f"[PHASE 5] SKIP (OCR) '{text}' -- not an exact foundkey match."
            )
            continue

        matched_by, match_type = get_matched_alias(
            text_norm, label_name_norm, original_label, original_aliases
        )
        if not matched_by:
            continue

        # Gate: key must be inside a docling table
        table = get_table_containing_key(item, tables)
        if table is None:
            logger.info(
                f"[PHASE 5] SKIP (OCR) '{text}' -- not inside any docling table "
                f"(Phase 5 is docling-table-only)."
            )
            continue

        logger.info(
            f"[PHASE 5] Eligible OCR key found: '{text}' "
            f"(table_bbox={table.get('table_bbox')})."
        )
        table_key_candidates.append(
            (item, text, matched_by, match_type, table, "ocr")
        )

    # Collect cell-based table key candidates
    cell_matches = find_table_cell_keys(tables, aliases_norm)
    for cell, table in cell_matches:
        cell_text  = cell.get("text", "")
        matched_by, match_type = get_matched_alias(
            normalize_text(cell_text), label_name_norm, original_label, original_aliases
        )
        if not matched_by:
            continue
        logger.info(
            f"[PHASE 5] Eligible CELL key found: '{cell_text}' "
            f"(row={cell.get('row')}, col={cell.get('col')}, "
            f"is_header={cell.get('is_header', False)}, "
            f"table_bbox={table.get('table_bbox')})."
        )
        table_key_candidates.append(
            (cell, cell_text, matched_by, match_type, table, "cell")
        )

    if not table_key_candidates:
        logger.info(
            f"[PHASE 5] FAILED -- no eligible key found inside any docling table. "
            f"Key '{original_label}' not found in any phase."
        )
    else:
        logger.info(
            f"[PHASE 5] Found {len(table_key_candidates)} table key candidate(s). "
            f"Starting Pass A (row search)."
        )

        # --------------------------------------------------
        # Pass A: row search across ALL matched table keys
        # --------------------------------------------------
        logger.info("[PHASE 5] -- Pass A: Row Search --")

        for key_obj, text, matched_by, match_type, table, source in table_key_candidates:

            # CHANGE 1: Detect if key is a table header
            if source == "cell":
                key_is_header = bool(key_obj.get("is_header", False))
            else:  # ocr
                key_is_header = is_ocr_item_header_in_table(key_obj, table)

            if key_is_header:
                logger.info(
                    f"[PHASE 5][PASS A] *** Key '{text}' is a TABLE HEADER "
                    f"(is_header=True). Skipping row search for this key. "
                    f"It will be attempted in Pass B (down-column search)."
                )
                continue   # fall through to Pass B

            logger.info(
                f"[PHASE 5][PASS A] Trying row search for key '{text}' "
                f"(source={source}, table_bbox={table.get('table_bbox')})."
            )

            if source == "cell":
                value = find_same_row_cell_value(key_obj, table, all_keys_norm)
                if not value:
                    logger.info(
                        f"[PHASE 5][PASS A] No same-row cell value for '{text}'. "
                        f"Will try next candidate (or Pass B)."
                    )
            else:
                value = extract_phase5_row_value(
                    key_obj, ocr_items, aliases_norm, all_keys_norm, table
                )
                if not value:
                    logger.info(
                        f"[PHASE 5][PASS A] No same-row OCR value for '{text}'. "
                        f"Will try next candidate (or Pass B)."
                    )

            if value:
                logger.info(
                    f"[PHASE 5][PASS A] Row value found for '{text}': '{value}'. "
                    f"Returning result."
                )
                return {
                    "label_name": original_label,
                    "required": label_cfg["required"],
                    "data_type": label_cfg["data_type"],
                    "retrived_dtype": detect_value_dtype(value),
                    "value": value,
                    "foundkey": text,
                    "matched_by": matched_by,
                    "match_type": match_type,
                    "phase": "phase5_table_row"
                }

        logger.info(
            "[PHASE 5] Pass A complete -- no row value found for any table key. "
            "Starting Pass B (down-column search)."
        )

        # --------------------------------------------------
        # Pass B: down-column fallback across ALL matched table keys
        # (includes header keys skipped in Pass A)
        # --------------------------------------------------
        logger.info("[PHASE 5] -- Pass B: Down-Column Search --")

        for key_obj, text, matched_by, match_type, table, source in table_key_candidates:

            logger.info(
                f"[PHASE 5][PASS B] Trying down-column search for key '{text}' "
                f"(source={source}, table_bbox={table.get('table_bbox')})."
            )

            if source == "cell":
                value = find_down_column_cell_value(key_obj, table, all_keys_norm)
                if not value:
                    logger.info(
                        f"[PHASE 5][PASS B] No down-column cell value for '{text}'. "
                        f"Trying next candidate."
                    )
            else:
                # CHANGE 3: pass `table` so header OCR items are skipped
                value = extract_phase5_down_column_value(
                    key_obj, ocr_items, all_keys_norm, table=table
                )
                if not value:
                    logger.info(
                        f"[PHASE 5][PASS B] No down-column OCR value for '{text}'. "
                        f"Trying next candidate."
                    )

            if value:
                logger.info(
                    f"[PHASE 5][PASS B] Down-column value found for '{text}': '{value}'. "
                    f"Returning result."
                )
                return {
                    "label_name": original_label,
                    "required": label_cfg["required"],
                    "data_type": label_cfg["data_type"],
                    "retrived_dtype": detect_value_dtype(value),
                    "value": value,
                    "foundkey": text,
                    "matched_by": matched_by,
                    "match_type": match_type,
                    "phase": "phase5_table_down_column"
                }

        logger.info("[PHASE 5] Pass B complete -- no down-column value found for any table key.")

    logger.info(
        f"[FINAL] Key '{original_label}' was NOT found in any phase "
        f"(Phase 1 -> 2 -> 3 -> 4 -> 5 all exhausted)."
    )


    # ========================================================
    # PHASE 6 -- DIRECT NEXT TABLE CELL
    # ========================================================

    logger.info(
        f"[PHASE 6] -- DIRECT NEXT TABLE CELL SEARCH -- "
        f"key: '{original_label}'"
    )

    for table in tables:

        cells = table.get("cells") or []

        for cell in cells:

            text = (cell.get("text") or "").strip()

            if not is_exact_foundkey_match(text, aliases_norm):
                continue

            matched_by, match_type = get_matched_alias(
                normalize_text(strip_trailing_separator(text)),
                label_name_norm,
                original_label,
                original_aliases
            )

            if not matched_by:
                continue

            value = extract_phase6_next_cell_value(
                cell,
                table,
                all_keys_norm
            )

            if value:

                return {
                    "label_name": original_label,
                    "required": label_cfg["required"],
                    "data_type": label_cfg["data_type"],
                    "retrived_dtype": detect_value_dtype(value),
                    "value": value,
                    "foundkey": text,
                    "matched_by": matched_by,
                    "match_type": match_type,
                    "phase": "phase6_next_cell"
                }
    # ========================================================
    # FINAL NOT FOUND
    # ========================================================

    return {
        "label_name": original_label,
        "required": label_cfg["required"],
        "data_type": label_cfg["data_type"],
        "retrived_dtype": None,
        "value": None,
        "foundkey": None,
        "matched_by": None,
        "match_type": None,
        "phase": "not_found"
    }

# ============================================================
# ENTRY POINT
# ============================================================

def main(request_data, raw_data, response_data, log=None):

    _real_logger = _self.logger
    if log is not None:
        _self.logger = log

    try:
        labels       = request_data["ocr"]["labels"]
        all_keys_norm = build_all_keys(labels)

        for page_index, page_data in enumerate(raw_data):

            logger.info("")
            logger.info("=" * 60)
            logger.info(f"PROCESSING PAGE {page_index + 1}")
            logger.info("=" * 60)

            page_data["ocr"] = page_data.get("ocr", [])

            page_results = []

            for label_cfg in labels:
                logger.info("")
                logger.info("=" * 50)
                logger.info(f"Searching for label: '{label_cfg['label_name']}'")
                logger.info("=" * 50)

                try:
                    result = find_key_value(label_cfg, page_data, all_keys_norm)
                    page_results.append(result)

                    if result["value"] is not None:
                        logger.info(
                            f"[RESULT] '{label_cfg['label_name']}' -> "
                            f"value='{result['value']}' | "
                            f"phase={result['phase']} | "
                            f"matched_by='{result['matched_by']}'"
                        )
                    else:
                        logger.info(
                            f"[RESULT] '{label_cfg['label_name']}' -> NOT FOUND "
                            f"(all phases exhausted)."
                        )

                except Exception as e:
                    logger.error(
                        f"[ERROR] Label '{label_cfg['label_name']}' failed with "
                        f"exception: {e}"
                    )
                    page_results.append({
                        "label_name": label_cfg["label_name"],
                        "required": label_cfg["required"],
                        "data_type": label_cfg["data_type"],
                        "retrived_dtype": None,
                        "value": None,
                        "foundkey": None,
                        "matched_by": None,
                        "match_type": None,
                        "phase": "error"
                    })

            response_data[page_index]["label_extraction"] = page_results

        return response_data

    finally:
        _self.logger = _real_logger