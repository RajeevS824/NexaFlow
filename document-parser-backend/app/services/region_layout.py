# region_layout.py

import cv2
from typing import Optional

from app.services.model_loading import (
    block_layout_model,
    region_layout_model
)

from app.core.logger import logger


def process_layout(image_path, cancel_check: Optional[callable] = None):

    # =================================================
    # LOAD IMAGE
    # =================================================
    image = cv2.imread(image_path)

    if image is None:
        logger.error(f"Unable to load image → {image_path}")
        raise ValueError(f"Unable to load image: {image_path}")

    logger.info("Layout processing started")
    logger.debug(f"Image path → {image_path}")
    logger.debug(f"Image shape → {image.shape}")

    # =================================================
    # FINAL RESULT CONTAINER
    # =================================================
    combined_results = {
        "input_path": image_path,
        "page_index": None,
        "block_layout": [],
        "region_layout": []
    }

    # =================================================
    # BLOCK LAYOUT DETECTION
    # =================================================
    logger.info("Block layout detection started")

    if cancel_check and cancel_check():
        raise RuntimeError("Pipeline cancelled by client disconnect")

    block_output = block_layout_model.predict(
        image_path,
        batch_size=1,
        layout_nms=True
    )

    # =================================================
    # REGION LAYOUT DETECTION
    # =================================================
    logger.info("Region layout detection started")

    if cancel_check and cancel_check():
        raise RuntimeError("Pipeline cancelled by client disconnect")

    region_output = region_layout_model.predict(
        image_path,
        batch_size=1,
        layout_nms=True
    )

    # =================================================
    # PROCESS BLOCK LAYOUT
    # =================================================
    for res in block_output:
        combined_results["block_layout"] = res.json["res"]["boxes"]

    logger.debug(
        f"Total blocks → {len(combined_results['block_layout'])}"
    )

    # =================================================
    # PROCESS REGION LAYOUT
    # =================================================
    for res in region_output:
        combined_results["region_layout"] = res.json["res"]["boxes"]

    logger.debug(
        f"Total regions → {len(combined_results['region_layout'])}"
    )

    logger.info("Layout processing completed")

    return combined_results


