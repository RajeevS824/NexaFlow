# app/services/table_det_rec.py

import os
import time

from app.services.model_loading import (
    table_Classification,
    wired_TableCellsDetection,
)

from app.core.logger import logger


# ============================================================
# TABLE PROCESSING
# ============================================================

def process_table_visuals(table_outputs):
    """Runs table-type classification + wired cell detection on each
    table's cropped image, then maps the detected cell boxes back into
    the same full-page coordinate space that table["cells"] (from
    docling.py / TableFormer) already uses.

    Cell detection only runs for tables classified as "wired". Tables
    classified as "wireless" skip detection entirely and keep
    visual_cells as an empty list.

    The wired detection model runs on the *cropped* table image, so its
    boxes come back relative to that crop's own (0, 0) origin. Each
    table's own table_offset (the crop's top-left corner in the original
    page image, set by docling.py) is added back so visual_cells for THIS
    table land under THIS table, in the same coordinate space as its cells —
    not a shared/global origin, and not left in crop-local coordinates.
    """
    for table in table_outputs:

        crop_path = table["crop_path"]
        t_idx = table["table_index"]

        offset = table.get("table_offset") or {"x": 0, "y": 0}
        offset_x = offset.get("x", 0)
        offset_y = offset.get("y", 0)

        if not crop_path or not os.path.exists(crop_path):
            logger.warning(f"Crop image not found: {crop_path}")
            continue

        # ==============================================================
        # TABLE CLASSIFICATION
        # ==============================================================

        cls_start  = time.perf_counter()
        table_type = "wired"

        try:
            cls_output = table_Classification.predict(crop_path)

            for cls_res in cls_output:
                label = cls_res.json["res"]["label_names"][0]
                if "wireless" in label.lower():
                    table_type = "wireless"

            logger.info(f"Table {t_idx} type → {table_type}")

        except Exception as exc:
            logger.warning(f"Classification failed for table {t_idx} → {exc}")
            table_type = "wired"

        print(f"[TABLE TYPE] Table {t_idx} → {table_type.upper()}")

        logger.info(
            f"[TIMING] Table {t_idx} classification → "
            f"{time.perf_counter() - cls_start:.3f}s"
        )

        # ==============================================================
        # CELL DETECTION (wired tables only)
        # ==============================================================

        visual_cells: list[list[int]] = []

        if table_type == "wired":

            det_start = time.perf_counter()

            try:
                cell_output = wired_TableCellsDetection.predict(crop_path)

                for cell_res in cell_output:
                    boxes = cell_res.json["res"]["boxes"]

                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box["coordinate"])

                        # Translate crop-local coordinates → full-page
                        # coordinates for THIS table, using THIS table's own
                        # offset. Keeps visual_cells aligned with "cells" and
                        # correctly scoped to this specific table.
                        visual_cells.append([
                            x1 + offset_x,
                            y1 + offset_y,
                            x2 + offset_x,
                            y2 + offset_y,
                        ])

            except Exception as exc:
                logger.warning(
                    f"Cell detection failed for table {t_idx} → {exc}"
                )

            logger.info(
                f"[TIMING] Table {t_idx} cell detection → "
                f"{time.perf_counter() - det_start:.3f}s"
            )

        else:
            logger.info(
                f"Table {t_idx} is wireless → skipping cell detection, "
                f"keeping visual_cells empty"
            )

        logger.info(
            f"Table {t_idx} → {len(visual_cells)} cell(s) detected"
        )

        table["table_type"] = table_type

        table["visual_cells"] = visual_cells

    return table_outputs