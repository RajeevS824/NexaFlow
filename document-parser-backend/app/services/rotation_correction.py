# rotation_correction.py

import numpy as np
from PIL import Image

from app.services.model_loading import orientation_model
from app.core.logger import logger


def correct_rotation(image_path: str) -> None:
    """
    Detects and corrects the rotation of a document image.
    Overwrites the original file in-place with the corrected image.

    Args:
        image_path: Path to the image file to correct (PNG recommended).
    """

    logger.info(f"Running rotation correction → {image_path}")

    try:
        results = orientation_model.predict(image_path)

        for res in results:

            img: np.ndarray = res["input_img"]
            angle: str      = res["label_names"][0]

            logger.debug(f"Predicted orientation angle → {angle}°")

            # ─────────────────────────────────────────────────────
            # Rotate to correct orientation (lossless)
            # ─────────────────────────────────────────────────────
            if angle == "90":
                corrected = np.rot90(img, k=1)

            elif angle == "180":
                corrected = np.rot90(img, k=2)

            elif angle == "270":
                corrected = np.rot90(img, k=3)

            else:
                logger.debug("Image already upright (0°) — no rotation applied")
                corrected = img

            corrected = np.ascontiguousarray(corrected)

            Image.fromarray(corrected).save(image_path)

            logger.info(f"Rotation corrected ({angle}°) → saved → {image_path}")

    except Exception as e:
        logger.error(f"Rotation correction failed for {image_path} → {e}", exc_info=True)
        raise