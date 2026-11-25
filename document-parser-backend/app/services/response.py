
"""
response.py

"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.logger import logger


# ---------------------------------------------------
# COLORS
# ---------------------------------------------------

COLORS = {
    "block_layout": {
        "outline": (255, 0, 0),      # Red
        "width": 4,
    },

    # "region_table": {
    #     "outline": (255, 20, 147),   # Pink
    #     "width": 3,
    # },

    "region_other": {
        "outline": (46, 125, 50),      # Green
        "width": 2,
    },

    "ocr": {
        "outline": (0, 0, 255),      # Blue
        "width": 2,
    },

    "visual_cell": {
        "outline" : (34, 139, 34),    # forest green
        "width": 2,
    },

    # "table_cell": {
    #     "outline": (255, 255, 0),    # Yellow
    #     "width": 2,
    # },

    # docling-layout-heron detections (layout.docling_layout), drawn
    # directly from the model's raw output — independent of
    # region_layout (pink/green above, a different model).
    "docling_table": {
        "outline" : (34, 139, 34),    # forest green
        "width": 2,
    },

    "docling_keyvalue": {
        "outline": (148, 0, 211),    # Purple
        "width": 2,
    },
}


# ---------------------------------------------------
# TABLE / CELL GRID CONSTANTS
# ---------------------------------------------------

# Small outward padding applied purely for *drawing* the docling
# "Table" border, so the cyan outline sits just outside the real
# table region instead of clipping through the outermost cells.
# This does NOT affect any coordinate math used for cell placement.
TABLE_BORDER_DRAW_PADDING = 6

# Inward padding applied when building the reconstructed cell grid
# below, so the outermost cell edges sit exactly flush with the
# table's own bbox (table_bbox), never spilling past it.
CELL_GRID_PADDING = 0


# ---------------------------------------------------
# EXTRACT LAYOUT
# ---------------------------------------------------

def _extract_layout(data):

    layout = data.get("layout", {})

    return {
        "input_path":    layout.get("input_path"),
        "page_index":    layout.get("page_index"),
        "block_layout":  layout.get("block_layout",  []),
        "region_layout": layout.get("region_layout", []),
        # Full docling-layout-heron detections (Table, Key-Value Region,
        # Text, Picture, etc.) — a separate model from region_layout above.
        "docling_layout": layout.get("docling_layout", []),
    }


# ---------------------------------------------------
# EXTRACT OCR
# ---------------------------------------------------

def _extract_ocr(data):

    cleaned_ocr = []

    for item in data.get("ocr", []):
        cleaned_ocr.append({
            "coordinates": item.get("coordinates", []),
            "text":        item.get("text", ""),
            "det_score":   item.get("det_score"),
            "rec_score":   item.get("rec_score"),
        })

    return cleaned_ocr


# ---------------------------------------------------
# EXTRACT TABLES
# ---------------------------------------------------

def _extract_tables(data):

    cleaned_tables = []

    for table in data.get("tables", []):
        cleaned_tables.append({
            "table_index":  table.get("table_index"),
            "table_type":   table.get("table_type"),
            "table_bbox":   table.get("table_bbox"),
            "table_offset": table.get("table_offset"),
            "padding":      table.get("padding"),       # single int constant
            "visual_cells": table.get("visual_cells", []),  # for annotation
            "html":         table.get("html", ""),
            "column_wise":  table.get("column_wise", {}),
            "row_wise":     table.get("row_wise", []),
            "cells":        table.get("cells", []),         # row/col/text/coordinates
        })

    return cleaned_tables


# ---------------------------------------------------
# EXPORT CLEAN JSON
# ---------------------------------------------------

def response(
    input_json_path,
    output_dir="app/output/json",
    output_filename="response.json",
):

    logger.info("Generating clean JSON...")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned_output = []

    for page in data:
        cleaned_page = {
            "image":  page.get("image"),
            "layout": _extract_layout(page),
            "ocr":    _extract_ocr(page),
            "tables": _extract_tables(page),
        }
        cleaned_output.append(cleaned_page)

    out_path = os.path.join(output_dir, output_filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_output, f, indent=4, ensure_ascii=False)

    logger.info(f"Clean JSON saved → {out_path}")

    return cleaned_output, os.path.abspath(out_path)


# ---------------------------------------------------
# DRAW RECTANGLE
# ---------------------------------------------------

def _draw_rect(draw, bbox, color, width):
    draw.rectangle(bbox, outline=color, width=width)


# ---------------------------------------------------
# BUILD PROPER TABLE CELL GRID (wireless tables only)
# ---------------------------------------------------
#
# `cells` (row/col/coordinates, already tagged with row+col index and
# is_header) is the docling/TableFormer structure. For WIRELESS tables
# there is no drawn grid and no visual_cells (process_table_visuals
# intentionally skips wireless cell detection), so this reconstructs
# one clean bbox per (row, col) that:
#
#   1. Never extends past the table's own bbox (`table_bbox`) — the
#      leftmost column's left edge and rightmost column's right edge
#      are snapped exactly onto the table border, likewise for the
#      first/last row's top/bottom edge.
#   2. Has no gaps or overlaps between neighboring columns/rows — any
#      mismatch between a column's right edge and the next column's
#      left edge (or a row's bottom vs the next row's top) is resolved
#      by splitting the difference at the midpoint.
#   3. Column x-boundaries are taken from the HEADER row wherever a
#      header exists (it's the cleanest, most reliably detected row)
#      and then reused for every data row below it, so columns line up
#      vertically even though there are no drawn grid lines to anchor
#      them.
#
# ---------------------------------------------------

def _compute_table_grid(cells, table_bbox, padding=CELL_GRID_PADDING):

    if not cells or not table_bbox or len(table_bbox) != 4:
        return []

    tx0, ty0, tx1, ty1 = table_bbox

    inner_x0 = tx0 + padding
    inner_y0 = ty0 + padding
    inner_x1 = tx1 - padding
    inner_y1 = ty1 - padding

    if inner_x1 <= inner_x0 or inner_y1 <= inner_y0:
        inner_x0, inner_y0, inner_x1, inner_y1 = tx0, ty0, tx1, ty1

    # --------------------------------------------------
    # Group raw cell coordinates by column index and row index.
    # --------------------------------------------------

    cols = {}
    rows = {}

    for cell in cells:

        coord = cell.get("coordinates")

        if not coord or len(coord) != 4:
            continue

        col_i = cell.get("col")
        row_i = cell.get("row")
        x0, y0, x1, y1 = coord

        if col_i is not None:
            cols.setdefault(col_i, []).append(
                (x0, x1, cell.get("is_header"))
            )

        if row_i is not None:
            rows.setdefault(row_i, []).append((y0, y1))

    if not cols or not rows:
        return []

    col_indices = sorted(cols.keys())
    row_indices = sorted(rows.keys())

    # --------------------------------------------------
    # COLUMN BOUNDARIES — tiling by center + midpoint
    #
    # Using each column's raw text min/max as its boundary (the old
    # approach) leaves gaps whenever the detected text doesn't fill the
    # whole visual column — which is the normal case for a wireless
    # table (no drawn grid lines to anchor to), and is exactly what was
    # showing up as cells floating away from the table border and from
    # each other.
    #
    # Instead: take the CENTER x of each column (preferring the header
    # row's center when a header exists, since it's the cleanest/most
    # reliable row), then set the boundary between two neighboring
    # columns at the midpoint of their centers. Every column then spans
    # from the previous midpoint to the next midpoint — a true tiling
    # with no gaps and no overlaps — and the first/last column's outer
    # edge is snapped exactly onto the table border. This holds
    # regardless of how tight or off-center the underlying detected
    # text box is.
    # --------------------------------------------------

    col_centers = {}

    for col_i in col_indices:

        entries = cols[col_i]

        header_entries = [(x0, x1) for x0, x1, is_h in entries if is_h]
        source = header_entries if header_entries else [(x0, x1) for x0, x1, _ in entries]

        col_centers[col_i] = sum((x0 + x1) / 2.0 for x0, x1 in source) / len(source)

    col_bounds = {}
    n_cols = len(col_indices)

    for i, col_i in enumerate(col_indices):

        left = (
            inner_x0
            if i == 0
            else (col_centers[col_indices[i - 1]] + col_centers[col_i]) / 2.0
        )
        right = (
            inner_x1
            if i == n_cols - 1
            else (col_centers[col_i] + col_centers[col_indices[i + 1]]) / 2.0
        )

        col_bounds[col_i] = [left, right]

    # --------------------------------------------------
    # ROW BOUNDARIES — same center + midpoint tiling as columns
    # --------------------------------------------------

    row_centers = {}

    for row_i in row_indices:
        entries = rows[row_i]
        row_centers[row_i] = sum((y0 + y1) / 2.0 for y0, y1 in entries) / len(entries)

    row_bounds = {}
    n_rows = len(row_indices)

    for i, row_i in enumerate(row_indices):

        top = (
            inner_y0
            if i == 0
            else (row_centers[row_indices[i - 1]] + row_centers[row_i]) / 2.0
        )
        bottom = (
            inner_y1
            if i == n_rows - 1
            else (row_centers[row_i] + row_centers[row_indices[i + 1]]) / 2.0
        )

        row_bounds[row_i] = [top, bottom]

    # --------------------------------------------------
    # BUILD FINAL PER-CELL BOXES
    #
    # No hard-clip step here: the tiling above already guarantees every
    # box sits within [inner_x0, inner_x1] x [inner_y0, inner_y1], with
    # the outermost cells flush against the table border.
    # --------------------------------------------------

    grid_boxes = []

    for cell in cells:

        row_i = cell.get("row")
        col_i = cell.get("col")

        if row_i not in row_bounds or col_i not in col_bounds:
            continue

        x0, x1 = col_bounds[col_i]
        y0, y1 = row_bounds[row_i]

        if x1 <= x0 or y1 <= y0:
            continue

        grid_boxes.append([x0, y0, x1, y1])

    return grid_boxes


# ---------------------------------------------------
# ANNOTATE IMAGE
# ---------------------------------------------------

def annotate_invoice(
    json_path,
    image_path,
    output_dir="app/output",
    output_filename="annotated_invoice.png",
):

    logger.info(f"Annotating image → {image_path}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    page_data = None

    for page in data:
        if os.path.abspath(page.get("image", "")) == os.path.abspath(image_path):
            page_data = page
            break

    if page_data is None:
        raise ValueError(f"No matching page found for image: {image_path}")

    image = Image.open(image_path).convert("RGB")
    draw  = ImageDraw.Draw(image)

    # --------------------------------------------------
    # BLOCK LAYOUT  (red)
    # --------------------------------------------------

    for block in page_data.get("layout", {}).get("block_layout", []):

        coord = block.get("coordinate", [])

        if len(coord) != 4:
            continue

        _draw_rect(
            draw=draw,
            bbox=coord,
            color=COLORS["block_layout"]["outline"],
            width=COLORS["block_layout"]["width"],
        )

    # --------------------------------------------------
    # REGION LAYOUT
    # table -> pink (currently disabled)
    # others -> green
    # --------------------------------------------------

    for region in page_data.get("layout", {}).get("region_layout", []):

        coord = region.get("coordinate", [])

        if len(coord) != 4:
            continue

        if region.get("label") == "table":
            # Pink "region_table" drawing intentionally disabled — skip
            # instead of falling through to _draw_rect with undefined
            # color/width.
            continue

        color = COLORS["region_other"]["outline"]
        width = COLORS["region_other"]["width"]

        _draw_rect(
            draw=draw,
            bbox=coord,
            color=color,
            width=width,
        )

    # --------------------------------------------------
    # OCR TOKENS  (blue)
    # --------------------------------------------------

    for ocr in page_data.get("ocr", []):

        coords = ocr.get("coordinates", [])

        if not coords or len(coords) != 4:
            continue

        _draw_rect(
            draw=draw,
            bbox=coords,
            color=COLORS["ocr"]["outline"],
            width=COLORS["ocr"]["width"],
        )

    # --------------------------------------------------
    # TABLE CELLS  (orange)
    #
    # Branches on table_type (set by table_det_rec.py's
    # process_table_visuals):
    #
    #   - "wired": a real cell-detection model
    #     (wired_TableCellsDetection) already ran on this table and
    #     produced table["visual_cells"] in full-page pixel coordinates.
    #     Draw those boxes directly — no reconstruction needed.
    #
    #   - "wireless" (or "docling", i.e. table_rec disabled): no cell
    #     detection model ran, so visual_cells is always []. Fall back
    #     to reconstructing a grid from the docling `cells` structure
    #     via _compute_table_grid (header-anchored column boundaries).
    # --------------------------------------------------

    for table in page_data.get("tables", []):

        table_type = (table.get("table_type") or "").lower()

        if table_type == "wired":
            boxes_to_draw = [
                cell for cell in table.get("visual_cells", [])
                if cell and len(cell) == 4
            ]
        else:
            boxes_to_draw = _compute_table_grid(
                cells=table.get("cells", []),
                table_bbox=table.get("table_bbox"),
            )

        for bbox in boxes_to_draw:
            _draw_rect(
                draw=draw,
                bbox=bbox,
                color=COLORS["visual_cell"]["outline"],
                width=COLORS["visual_cell"]["width"],
            )

    # --------------------------------------------------
    # DOCLING-LAYOUT-HERON DETECTIONS  (Table = cyan, Key-Value Region = purple)
    #
    # layout.docling_layout is the FULL, unfiltered output of the heron
    # model (layout_detector.detect() inside docling.py's
    # convert_document()) — every entry is {"label", "score", "bbox"}.
    # This is the exact detector that decided table_bbox / table_offset
    # for cropping, TableFormer, and cell detection, so drawing it here
    # shows you the real region the rest of the pipeline is built on.
    #
    # This is intentionally independent of region_layout (pink "table"
    # box above), which comes from a different model in
    # region_layout.py / process_layout() and may disagree with heron.
    #
    # A small outward padding is applied only to the "Table" border
    # itself (drawing only — not used anywhere in cell math) so the
    # cyan outline sits just outside the reconstructed cell grid above
    # instead of visually clipping through the outermost cells.
    # --------------------------------------------------

    for entry in page_data.get("layout", {}).get("docling_layout", []):

        bbox = entry.get("bbox")
        label = entry.get("label")

        if not bbox or len(bbox) != 4:
            continue

        if label == "Table":
            color = COLORS["docling_table"]["outline"]
            width = COLORS["docling_table"]["width"]
            pad = TABLE_BORDER_DRAW_PADDING
            bbox = [
                bbox[0] - pad,
                bbox[1] - pad,
                bbox[2] + pad,
                bbox[3] + pad,
            ]
        elif label == "Key-Value Region":
            color = COLORS["docling_keyvalue"]["outline"]
            width = COLORS["docling_keyvalue"]["width"]
        else:
            continue  # only Table / Key-Value Region are drawn

        _draw_rect(
            draw=draw,
            bbox=bbox,
            color=color,
            width=width,
        )

    # --------------------------------------------------
    # TABLE CELLS  (yellow) — legacy raw drawing, disabled
    # cells[].coordinates are ALREADY in full-page pixel
    # coordinates (top-left origin) — produced directly by
    # docling.py's _extract_table_data(), NOT crop-local.
    # Do NOT apply table_offset here; that would double-shift
    # them off the page.
    # --------------------------------------------------

    # for table in page_data.get("tables", []):

    #     for cell in table.get("cells", []):

    #         coord = cell.get("coordinates")

    #         if not coord or len(coord) != 4:
    #             continue

    #         _draw_rect(
    #             draw=draw,
    #             bbox=coord,
    #             color=COLORS["table_cell"]["outline"],
    #             width=COLORS["table_cell"]["width"],
    #         )

    out_path = os.path.abspath(
        os.path.join(output_dir, output_filename)
    )

    image.save(out_path)

    logger.info(f"Annotated image saved → {out_path}")

    return out_path