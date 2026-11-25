# app/services/docling.py
"""
Runs, per page image:
  1. Local ONNX layout detection  → find "Table" regions (docling-layout-heron)
  2. PaddleOCR                    → full-page OCR tokens
  3. Docling TableFormer          → table structure (html / dataframe / cells)
  4. Crops each detected table region to disk for table_det_rec.py

Models are loaded once at startup in app/models/model_loading.py and
imported here as ready-to-use instances — this module does no model
loading of its own.

Returned dict (consumed by document_service.py):
{
    "ocr": [ {coordinates, det_score, text, rec_score}, ... ],
    "tables": [
        {
            table_index, table_type, table_bbox, table_offset, padding,
            crop_path, html, column_wise, row_wise, cells, visual_cells,
        }, ...
        # html/column_wise/row_wise/cells come from TableFormer;
        # table_bbox/table_offset/padding/crop_path come from the crop
        # step -- both built together, in the same loop, per table, so
        # this is already the final per-table shape (no re-merge needed
        # downstream). table_type is None and visual_cells is [] until
        # table_det_rec.py's process_table_visuals() fills them in
        # (classification + cell detection).
    ],
    "docling_layout": [
        {label, score, bbox}, ...   # FULL, unfiltered docling-layout-heron
                                    # detections (Table, Key-Value Region,
                                    # Text, Picture, etc). document_service.py
                                    # merges this into page["layout"] as its
                                    # own node, alongside block_layout /
                                    # region_layout (which come from a
                                    # different model in region_layout.py).
}

Each table's "table_offset" is the top-left corner (in the *original*
full-page image) of the saved crop, padding included. table_det_rec.py
uses this offset to translate cell/box coordinates produced from the
*cropped* image (e.g. wired/wireless visual cell detection) back into the
same full-page coordinate space that "cells" (from TableFormer) already
use — so a table's visual_cells line up with that same table's cells.
"""

import os
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from PIL import Image

from docling_core.types.doc import TableCell
from docling_core.types.doc.document import TableData

from app.services.model_loading import (
    layout_detector,
    ocr_engine,
    tf_predictor,
)

from app.core.logger import logger

TABLEFORMER_SCALE = 2.0
CROP_PADDING = 10


def _sec(t0: float) -> str:
    return f"{time.perf_counter() - t0:.3f}s"


# ──────────────────────────────────────────────────────────────────────────────
# TERMINAL TIMING SUMMARY
# ──────────────────────────────────────────────────────────────────────────────
def _print_timing_summary(timings: list, total_override: Optional[float] = None) -> None:
    """
    Prints a per-page timing breakdown to the terminal, e.g.:

      1_layout_detection                       1.180s
      2_ocr                                    5.043s
      3_tableformer_predict                    2.126s
      4_all_tables_build_and_export_total      0.055s
    ------------------------------------------------------------
      TOTAL                                    8.404s

    `timings` is a list of (label, seconds) tuples, in order.

    `total_override`: pass this when some of the entries in `timings`
    ran concurrently (e.g. layout detection + OCR, in the same thread
    pool) -- naively summing every row would double-count the time
    they overlapped. Pass the real wall-clock total instead so TOTAL
    reflects actual elapsed time, not "as if run one-by-one" time.
    """
    label_width = 38
    total = total_override if total_override is not None else sum(dur for _, dur in timings)

    print()
    for label, dur in timings:
        print(f"  {label:<{label_width}}{dur:>8.3f}s")
    print("-" * 60)
    print(f"  {'TOTAL':<{label_width}}{total:>8.3f}s")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# TERMINAL OCR TEXT DUMP
# ──────────────────────────────────────────────────────────────────────────────
def _print_ocr_text(tokens: list) -> None:
    """
    Prints every recognized OCR token's text to the terminal, e.g.:

      [OCR] 000  det=0.892  rec=0.996  TAXINVOICE
      [OCR] 001  det=0.989  rec=0.961  123B20/8XXXXXX
      ...
      [OCR] TOTAL TOKENS: 38
    """
    print()
    print("-" * 60)
    print("  OCR RECOGNIZED TEXT")
    print("-" * 60)
    for tok in tokens:
        print(
            f"  [OCR] {tok['id']:03d}  "
            f"det={tok['det_score']:.3f}  "
            f"rec={tok['rec_score']:.3f}  "
            f"{tok['text']}"
        )
    print("-" * 60)
    print(f"  TOTAL TOKENS: {len(tokens)}")
    print("-" * 60)
    print()


# ──────────────────────────────────────────────────────────────────────────────
# OCR → JSON
# ──────────────────────────────────────────────────────────────────────────────
def _ocr_tokens_to_json(tokens: list) -> list:
    out = []
    for tok in tokens:
        b = tok["bbox"]
        out.append({
            "coordinates": [b["l"], b["t"], b["r"], b["b"]],
            "det_score": tok["det_score"],
            "text": tok["text"],
            "rec_score": tok["rec_score"],
        })
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Reconstruct raw OCR tokens from JSON format (inverse of _ocr_tokens_to_json)
# ──────────────────────────────────────────────────────────────────────────────
def _reconstruct_ocr_tokens(ocr_json: list) -> list:
    """
    Converts the JSON-serialized OCR token format back into the internal
    format that TableFormer's _build_page_input expects:

    JSON format (from full_doc_result["ocr"]):
        {"coordinates": [l, t, r, b], "det_score": ..., "text": ..., "rec_score": ...}

    Internal format (what _build_page_input / _predict_table_structure need):
        {"id": ..., "text": ..., "bbox": {"l": ..., "t": ..., "r": ..., "b": ...},
         "det_score": ..., "rec_score": ...}
    """
    tokens = []
    for idx, tok in enumerate(ocr_json):
        coords = tok["coordinates"]  # [l, t, r, b]
        tokens.append({
            "id": idx,
            "text": tok["text"],
            "bbox": {
                "l": coords[0],
                "t": coords[1],
                "r": coords[2],
                "b": coords[3],
            },
            "det_score": tok["det_score"],
            "rec_score": tok["rec_score"],
        })
    return tokens


# ──────────────────────────────────────────────────────────────────────────────
# TableFormer plumbing (ported 1:1 from the standalone pipeline script)
# ──────────────────────────────────────────────────────────────────────────────
def _build_page_input(image_rgb: Image.Image, ocr_tokens: list, scale: float = TABLEFORMER_SCALE) -> dict:
    w_orig, h_orig = image_rgb.size
    w_scaled = int(round(w_orig * scale))
    h_scaled = int(round(h_orig * scale))

    img_scaled = image_rgb.resize((w_scaled, h_scaled), Image.LANCZOS)
    img_np = np.asarray(img_scaled)

    scaled_tokens = []
    for tok in ocr_tokens:
        b = tok["bbox"]
        scaled_tokens.append({
            "id": tok["id"],
            "text": tok["text"],
            "bbox": {
                "l": b["l"] * scale,
                "t": b["t"] * scale,
                "r": b["r"] * scale,
                "b": b["b"] * scale,
            },
        })

    return {
        "width": w_scaled,
        "height": h_scaled,
        "image": img_np,
        "tokens": scaled_tokens,
    }


def _predict_table_structure(image_rgb: Image.Image, table_bboxes: list, ocr_tokens: list) -> list:
    page_input = _build_page_input(image_rgb, ocr_tokens, TABLEFORMER_SCALE)
    scaled_table_bboxes = [
        [round(v) * TABLEFORMER_SCALE for v in bbox]
        for bbox in table_bboxes
    ]
    return tf_predictor.multi_table_predict(page_input, scaled_table_bboxes, do_matching=True)


def _tf_output_to_table_data(table_out: dict, scale: float = TABLEFORMER_SCALE) -> TableData:
    table_cells = []
    for element in table_out["tf_responses"]:
        tc = TableCell.model_validate(element)
        if tc.bbox is not None:
            tc.bbox = tc.bbox.scaled(1.0 / scale)
        table_cells.append(tc)

    num_rows = table_out["predict_details"].get("num_rows", 0)
    num_cols = table_out["predict_details"].get("num_cols", 0)

    return TableData(num_rows=num_rows, num_cols=num_cols, table_cells=table_cells)


def _table_data_to_dataframe(table_data: TableData, doc=None, **kwargs) -> pd.DataFrame:
    if table_data.num_rows == 0 or table_data.num_cols == 0:
        return pd.DataFrame()

    num_headers = 0
    for row in table_data.grid:
        if len(row) == 0:
            raise RuntimeError(f"Invalid table. {len(row)=} but {table_data.num_cols=}.")
        if any(cell.column_header for cell in row):
            num_headers += 1
        else:
            break

    columns: Optional[list] = None
    if num_headers > 0:
        columns = ["" for _ in range(table_data.num_cols)]
        for i in range(num_headers):
            for j, cell in enumerate(table_data.grid[i]):
                col_name = cell._get_text(doc=doc, **kwargs)
                if columns[j] != "":
                    col_name = f".{col_name}"
                columns[j] += col_name

        # Any column left with no header text at all (blank/unrecognized
        # header cell) gets a generic placeholder name instead of "" --
        # "Column Header 1", "Column Header 2", etc, numbered by position.
        # This is what prevents multiple blank columns from colliding
        # under the same "" key later (in html/column_wise/cells export).
        for j in range(len(columns)):
            if columns[j] == "":
                columns[j] = f"Column Header {j + 1}"
    elif table_data.num_cols > 0:
        # No header row detected at all -- still name columns generically
        # rather than falling back to pandas' default integer columns
        # (0, 1, 2, ...), so column_wise keys are always readable strings.
        columns = [f"Column Header {j + 1}" for j in range(table_data.num_cols)]

    table_rows = [
        [cell._get_text(doc=doc, **kwargs) for cell in row]
        for row in table_data.grid[num_headers:]
    ]

    return pd.DataFrame(table_rows, columns=columns)


def _escape_html(text: str) -> str:
    return (text or "").replace("&", "&").replace("<", "<").replace(">", ">")


def _table_data_to_html(table_data: TableData) -> str:
    if table_data.num_rows == 0 or table_data.num_cols == 0:
        return "<table></table>"

    grid = table_data.grid
    covered = set()
    html_rows = []

    for r, row in enumerate(grid):
        cells_html = []
        for c, cell in enumerate(row):
            if (r, c) in covered:
                continue
            if cell.start_row_offset_idx != r or cell.start_col_offset_idx != c:
                continue

            rowspan = cell.end_row_offset_idx - cell.start_row_offset_idx
            colspan = cell.end_col_offset_idx - cell.start_col_offset_idx

            for rr in range(cell.start_row_offset_idx, cell.end_row_offset_idx):
                for cc in range(cell.start_col_offset_idx, cell.end_col_offset_idx):
                    covered.add((rr, cc))

            tag = "th" if cell.column_header else "td"
            attrs = ""
            if rowspan > 1:
                attrs += f' rowspan="{rowspan}"'
            if colspan > 1:
                attrs += f' colspan="{colspan}"'

            cells_html.append(f"<{tag}{attrs}>{_escape_html(cell.text)}</{tag}>")

        if cells_html:
            html_rows.append("<tr>" + "".join(cells_html) + "</tr>")

    return "<table>" + "".join(html_rows) + "</table>"


def _table_data_to_cells_json(table_data: TableData) -> list:
    """Cell coordinates here are in the *original full-page* image's
    coordinate space (TableFormer/OCR both operate on the full page, not a
    per-table crop), so they are directly comparable to table_bbox and to
    the visual_cells produced later by table_det_rec.py once offset."""
    cells_out = []
    for tc in table_data.table_cells:
        if tc.bbox is not None:
            coords = [round(tc.bbox.l), round(tc.bbox.t), round(tc.bbox.r), round(tc.bbox.b)]
        else:
            coords = None

        if tc.column_header:
            header_type = "col_header"
        elif tc.row_header:
            header_type = "row_header"
        elif tc.row_section:
            header_type = "row_section"
        else:
            header_type = None

        cells_out.append({
            "row": tc.start_row_offset_idx,
            "col": tc.start_col_offset_idx,
            "text": tc.text,
            "coordinates": coords,
            "is_header": bool(header_type),
            "header_type": header_type,
        })
    return cells_out


def _dataframe_to_column_row_wise(df: pd.DataFrame):
    try:
        # Original (name-based) export path.
        column_wise = {str(col): df[col].tolist() for col in df.columns}
    except AttributeError as exc:
        # df[col] returned a DataFrame instead of a Series -- this happens
        # when two or more columns share the exact same name (duplicate
        # headers that weren't caught upstream), since DataFrames don't
        # have .tolist(). This previously crashed the whole build/export
        # step with "'DataFrame' object has no attribute 'tolist'",
        # silently dropping the table (most visible on region_layout
        # fallback tables, which hit blank/duplicate headers more often
        # than Heron-detected tables).
        #
        # Catch it and fall back to positional (iloc) indexing, which
        # can't collapse into a DataFrame, de-duplicating any repeated
        # keys so nothing gets silently overwritten.
        logger.warning(
            f"[docling] column_wise export hit a duplicate-column issue "
            f"({exc}); falling back to positional (iloc) extraction"
        )
        column_wise = {}
        for i, col in enumerate(df.columns):
            key = str(col)
            if key in column_wise:
                key = f"{key}.{i}"
            column_wise[key] = df.iloc[:, i].tolist()
    row_wise = df.values.tolist()
    return column_wise, row_wise


# ──────────────────────────────────────────────────────────────────────────────
# Cropping — this is what table_det_rec.py consumes for classification /
# visual cell detection
# ──────────────────────────────────────────────────────────────────────────────
def _crop_table(
    image_rgb: Image.Image,
    bbox: list,
    idx: int,
    table_image_dir: Optional[str],
    padding: int = CROP_PADDING,
) -> dict:
    W, H = image_rgb.size
    l, t, r, b = [round(v) for v in bbox]

    # Padded crop bounds, clamped to the page.
    pl = max(l - padding, 0)
    pt = max(t - padding, 0)
    pr = min(r + padding, W)
    pb = min(b + padding, H)

    crop_path = None
    if table_image_dir:
        os.makedirs(table_image_dir, exist_ok=True)
        crop_path = os.path.join(table_image_dir, f"table_{idx}_crop.png")
        try:
            image_rgb.crop((pl, pt, pr, pb)).save(crop_path)
        except Exception as exc:
            logger.warning(f"[docling] could not save crop for table {idx}: {exc}")
            crop_path = None

    return {
        "table_index": idx,
        "crop_path": crop_path,
        "table_bbox": [l, t, r, b],
        # Top-left of the *saved crop* (padding included) in full-page
        # coordinates. table_det_rec.py adds this to any box detected on
        # the cropped image to bring it back into full-page space.
        "table_offset": {"x": pl, "y": pt},
        "padding": padding,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Standalone table pipeline (TableFormer + build/export)
# Extracted so it can be called both from convert_document() (normal path)
# and from document_service.py (fallback path when Heron detects no tables).
# ──────────────────────────────────────────────────────────────────────────────
def run_table_pipeline(
    image_rgb: Image.Image,
    ocr_tokens: list,
    table_bboxes: list,
    table_html_dir: Optional[str] = None,
    table_image_dir: Optional[str] = None,
    cancel_check: Optional[callable] = None,
) -> list:
    """
    Run TableFormer prediction + build/export for each table bbox.

    Parameters
    ----------
    image_rgb : PIL.Image
        The full-page RGB image.
    ocr_tokens : list
        Raw OCR tokens with format:
        {"id": int, "text": str, "bbox": {"l":..., "t":..., "r":..., "b":...},
         "det_score": float, "rec_score": float}
    table_bboxes : list of [l, t, r, b]
        Bounding boxes of tables to process.
    table_html_dir : str or None
        Directory to save per-table HTML files (optional).
    table_image_dir : str or None
        Directory to save per-table crop images (optional).
    cancel_check : callable or None
        Called periodically; if returns True, pipeline is cancelled.

    Returns
    -------
    list of dict
        Each dict has the standard table output shape:
        {table_index, table_type, table_bbox, table_offset, padding,
         crop_path, html, column_wise, row_wise, cells, visual_cells}
    """
    table_outputs = []

    if not table_bboxes:
        return table_outputs

    # ------------------------------------------------------------
    # 3. TableFormer prediction
    # ------------------------------------------------------------
    t0 = time.perf_counter()
    tf_outputs = _predict_table_structure(image_rgb, table_bboxes, ocr_tokens)
    t_tf = time.perf_counter() - t0
    logger.info(f"[docling] TableFormer prediction done ({t_tf:.3f}s)")

    # ------------------------------------------------------------
    # 4. Build + export all tables (html / dataframe / cells / crop)
    #
    # Built as ONE merged list per table (not two parallel lists) --
    # html/column_wise/row_wise/cells (from TableFormer) and
    # crop_path/table_bbox/table_offset/padding (from _crop_table) are
    # both produced right here, in the same loop, in the same order,
    # so there's no reason to hand them back separately and make the
    # caller re-zip them by table_index later. table_type and
    # visual_cells are left as placeholders -- table_det_rec.py's
    # process_table_visuals() fills those in (classification + cell
    # detection), later.
    # ------------------------------------------------------------
    t0 = time.perf_counter()
    for idx, (table_out, bbox) in enumerate(zip(tf_outputs, table_bboxes), start=1):
        if cancel_check and cancel_check():
            raise RuntimeError("Pipeline cancelled by client disconnect")
        table_data = _tf_output_to_table_data(table_out)
        df = _table_data_to_dataframe(table_data)
        html = _table_data_to_html(table_data)
        cells_json = _table_data_to_cells_json(table_data)
        column_wise, row_wise = _dataframe_to_column_row_wise(df)

        if table_html_dir:
            os.makedirs(table_html_dir, exist_ok=True)
            html_path = os.path.join(table_html_dir, f"table_{idx}.html")
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception as exc:
                logger.warning(f"[docling] could not save html for table {idx}: {exc}")

        crop_meta = _crop_table(image_rgb, bbox, idx, table_image_dir)

        table_outputs.append({
            "table_index": idx,
            "table_type": None,
            "table_bbox": crop_meta["table_bbox"],
            "table_offset": crop_meta["table_offset"],
            "padding": crop_meta["padding"],
            "crop_path": crop_meta["crop_path"],
            "html": html,
            "column_wise": column_wise,
            "row_wise": row_wise,
            "cells": cells_json,
            "visual_cells": [],
        })
    t_build_export = time.perf_counter() - t0
    logger.info(
        f"[docling] Built + exported {len(table_outputs)} table(s) "
        f"({t_build_export:.3f}s)"
    )

    return table_outputs


# ──────────────────────────────────────────────────────────────────────────────
# Fallback: run table pipeline from already-converted OCR JSON format
# (used by document_service.py when Heron detects no tables but
#  region_layout has table entries)
# ──────────────────────────────────────────────────────────────────────────────
def run_table_pipeline_from_ocr_json(
    image_path: str,
    ocr_json: list,
    table_bboxes: list,
    table_html_dir: Optional[str] = None,
    table_image_dir: Optional[str] = None,
    cancel_check: Optional[callable] = None,
) -> list:
    """
    Convenience wrapper for the fallback path. Takes the OCR tokens in
    their JSON-serialized format (as stored in full_doc_result["ocr"]),
    reconstructs the raw token format, and calls run_table_pipeline().

    Parameters
    ----------
    image_path : str
        Path to the full-page image.
    ocr_json : list
        OCR tokens in JSON format from full_doc_result["ocr"]:
        [{"coordinates": [l, t, r, b], "det_score": ..., "text": ..., "rec_score": ...}, ...]
    table_bboxes : list of [l, t, r, b]
        Bounding boxes of tables to process.
    table_html_dir : str or None
        Directory to save per-table HTML files (optional).
    table_image_dir : str or None
        Directory to save per-table crop images (optional).
    cancel_check : callable or None
        Called periodically; if returns True, pipeline is cancelled.

    Returns
    -------
    list of dict
        Same shape as run_table_pipeline()'s return value.
    """
    image_rgb = Image.open(image_path).convert("RGB")
    ocr_tokens = _reconstruct_ocr_tokens(ocr_json)
    return run_table_pipeline(
        image_rgb=image_rgb,
        ocr_tokens=ocr_tokens,
        table_bboxes=table_bboxes,
        table_html_dir=table_html_dir,
        table_image_dir=table_image_dir,
        cancel_check=cancel_check,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────
def convert_document(
    image_path: str,
    table_html_dir: Optional[str] = None,
    table_image_dir: Optional[str] = None,
    tables_enabled: bool = True,
    cancel_check: Optional[callable] = None,
 ) -> dict:
    """
    Layout detection (docling-layout-heron) ALWAYS runs, regardless of
    tables_enabled — it produces docling_layout entries that are useful
    even when tables are disabled (e.g. Key-Value Region, Section-header,
    Title, etc.). The detections are filtered to exclude Picture, Text,
    and Caption labels before being stored.

    tables_enabled=False  -> layout detection + OCR only. TableFormer
    (structure detection + dataframe/html export), crop/export, and any
    downstream table-specific steps (table_det_rec, table_colextraction)
    are all skipped entirely.

    tables_enabled=True   -> existing full behavior (layout detection +
    OCR + TableFormer + crop/export), unchanged.
    """

    timings = []  # list of (label, seconds) for the terminal summary
    pool_wall = 0.0   # wall-clock time for the layout+OCR pool (or just OCR, if tables disabled)

    image_rgb = Image.open(image_path).convert("RGB")

    if cancel_check and cancel_check():
        raise RuntimeError("Pipeline cancelled by client disconnect")

    def _run_layout():
        t0 = time.perf_counter()
        dets = layout_detector.detect(image_rgb)
        return dets, time.perf_counter() - t0

    def _run_ocr():
        t0 = time.perf_counter()
        toks = ocr_engine.run(image_rgb)
        return toks, time.perf_counter() - t0

    # ------------------------------------------------------------
    # 1 + 2. Layout detection (docling-layout-heron) and OCR, run
    #    CONCURRENTLY. Neither depends on the other -- both only need
    #    image_rgb. Both ALWAYS run, even when tables are disabled, so
    #    that docling_layout (heron's full set of detections, excluding
    #    Picture/Text/Caption) is always populated in raw.json.
    #
    #    When tables are disabled, table_bboxes = [] (no TableFormer /
    #    crop), but layout detection still produces the full set of
    #    labels (Section-header, Key-Value Region, Title, etc.) that
    #    get stored in docling_layout.
    # ------------------------------------------------------------
    pool_wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_layout = pool.submit(_run_layout)
        future_ocr = pool.submit(_run_ocr)

        detections, t_layout = future_layout.result()
        if cancel_check and cancel_check():
            raise RuntimeError("Pipeline cancelled by client disconnect")
        ocr_tokens, t_ocr = future_ocr.result()
    pool_wall = time.perf_counter() - pool_wall_start

    timings.append(("1_layout_detection", t_layout))
    timings.append(("2_ocr", t_ocr))
    timings.append(("1+2_layout_and_ocr_wall_clock", pool_wall))

    if tables_enabled:
        table_bboxes = [d["bbox"] for d in detections if d["label"] == "Table"]
        logger.info(
            f"[docling] layout={t_layout:.3f}s  ocr={t_ocr:.3f}s  "
            f"(ran concurrently, wall={pool_wall:.3f}s)  "
            f"{len(table_bboxes)} table(s) detected"
        )
    else:
        table_bboxes = []
        logger.info(
            f"[docling] layout={t_layout:.3f}s  ocr={t_ocr:.3f}s  "
            f"(ran concurrently, wall={pool_wall:.3f}s)  "
            f"tables disabled -> skipping TableFormer / crop"
        )
        logger.info(f"[docling] OCR → {len(ocr_tokens)} token(s) ({t_ocr:.3f}s)")

    # Docling-layout-heron detections — every class (Table, Key-Value
    # Region, Section-header, Title, etc.), each as
    # {"label", "score", "bbox"}. Picture, Text, and Caption labels
    # are filtered out since those are not useful for downstream
    # layout purposes (they represent generic content regions).
    # Stored into raw.json so document_service.py can merge it into
    # page["layout"]["docling_layout"], separate from region_layout
    # (a different model, from region_layout.py / process_layout()).
    EXCLUDED_LAYOUT_LABELS = {"Picture", "Text", "Caption"}
    docling_layout = [
        d for d in detections if d["label"] not in EXCLUDED_LAYOUT_LABELS
    ]

    _print_ocr_text(ocr_tokens)

    ocr_json = _ocr_tokens_to_json(ocr_tokens)

    table_outputs = []

    if table_bboxes:
        # Time the overall TableFormer pipeline (both prediction + build/export)
        tf_start = time.perf_counter()
        table_outputs = run_table_pipeline(
            image_rgb=image_rgb,
            ocr_tokens=ocr_tokens,
            table_bboxes=table_bboxes,
            table_html_dir=table_html_dir,
            table_image_dir=table_image_dir,
            cancel_check=cancel_check,
        )
        t_tf_build = time.perf_counter() - tf_start
        timings.append(("3+4_tableformer_build_export_total", t_tf_build))
    else:
        # No tables detected -- step 4 took effectively no time.
        t_tf_build = 0.0
        timings.append(("4_all_tables_build_and_export_total", t_tf_build))

    # ------------------------------------------------------------
    # Print terminal timing summary for this page
    #
    # TOTAL = pool_wall (layout+OCR ran concurrently -- or just OCR's
    # own time, if tables were disabled) + TableFormer + build/export.
    # NOT a naive sum of every row above, since layout_detection and
    # ocr overlapped in time and summing both would double-count that
    # overlap.
    # ------------------------------------------------------------
    _print_timing_summary(timings, total_override=pool_wall + t_tf_build)

    return {
        "ocr": ocr_json,
        "tables": table_outputs,
        "docling_layout": docling_layout,
    }