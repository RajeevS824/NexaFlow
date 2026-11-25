
# app/services/model_loading.py

import os
from pathlib import Path

from paddleocr import (
    LayoutDetection,
    TextDetection,
    TextRecognition,
    TableClassification,
    TableCellsDetection,
    DocImgOrientationClassification,
)

from app.core.logger import logger

from app.services.vision_backbones import (
    LayoutDetector,
    OCREngine,
    load_tf_predictor,
)


# ============================================================
# LAYOUT MODELS
# ============================================================

print("Loading layout models...")

block_layout_model = LayoutDetection(
    model_name="PP-DocBlockLayout",
     engine="onnxruntime",
)
print("Loaded → PP-DocBlockLayout")

region_layout_model = LayoutDetection(
    model_name="PP-DocLayout_plus-L",
     engine="onnxruntime",
)
print("Loaded → PP-DocLayout_plus-L")


# ============================================================
# TABLE MODELS
# ============================================================

print("Loading table models...")

table_Classification = TableClassification(
    model_name="PP-LCNet_x1_0_table_cls",
     engine="onnxruntime",
)
print("Loaded → PP-LCNet_x1_0_table_cls")

wired_TableCellsDetection = TableCellsDetection(
    model_name="RT-DETR-L_wired_table_cell_det",
     engine="onnxruntime",
)
print("Loaded → RT-DETR-L_wired_table_cell_det")

wireless_TableCellsDetection = TableCellsDetection(
    model_name="RT-DETR-L_wireless_table_cell_det",
     engine="onnxruntime",
)
print("Loaded → RT-DETR-L_wireless_table_cell_det")


# ============================================================
# ORIENTATION MODEL
# ============================================================

print("Loading orientation model...")

orientation_model = DocImgOrientationClassification(
    model_name="PP-LCNet_x1_0_doc_ori",
     engine="onnxruntime",

)

print("Loaded → PP-LCNet_x1_0_doc_ori")

# ============================================================
# MODEL PATHS
# ============================================================


def _resolve_model_dir() -> Path:
    env_override = os.getenv("TABLEDOC_MODEL_DIR", "").strip()
    if env_override:
        return Path(env_override).expanduser().resolve()

    current_file = Path(__file__).resolve()
    backend_dir = current_file.parent.parent
    candidates = [
        backend_dir / "models",
        backend_dir.parent / "models",
        Path.cwd() / "models",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return (backend_dir / "models").resolve()


MODEL_DIR = _resolve_model_dir()
BACKEND_DIR = MODEL_DIR.parent

REQUIRED_MODEL_PATHS = [
    MODEL_DIR / "docling-layout-heron-onnx" / "model.onnx",
    MODEL_DIR / "TableFormer" / "model_artifacts" / "tableformer" / "accurate",
]

missing_paths = [str(path) for path in REQUIRED_MODEL_PATHS if not path.exists()]
if missing_paths:
    raise FileNotFoundError(
        "Model files not found. Checked the following paths: " + ", ".join(missing_paths)
    )


# ============================================================
# CUSTOM LAYOUT + OCR + TABLEFORMER  (used by app/services/docling.py)
# ============================================================
#
# This is the model set behind convert_document() in app/services/docling.py:
#   - layout_detector : finds "Table" regions on the page (ONNX)
#   - ocr_engine      : PaddleOCR PP-OCRv5 tokens used for TableFormer matching
#   - tf_predictor    : Docling's TableFormer, run directly (no
#                       DocumentConverter involved) so we can feed it our
#                       own layout boxes + OCR tokens per page.
#
# Paths are rooted under the same MODEL_DIR / BACKEND_DIR used everywhere
# else in this file.

print("Loading custom layout detector, OCR engine, and TableFormer...")

LAYOUT_ONNX_PATH = os.path.join(
    MODEL_DIR,
    "docling-layout-heron-onnx",
    "model.onnx",
)

TABLEFORMER_ARTIFACTS_DIR = os.path.join(
    MODEL_DIR,
    "TableFormer",
    "model_artifacts",
    "tableformer",
    "accurate",
)

layout_detector = LayoutDetector(
    onnx_path=LAYOUT_ONNX_PATH,
    threshold=0.65,
)
print("Loaded → docling-layout-heron (ONNX)")

ocr_engine = OCREngine(
    det_model="PP-OCRv5_server_det",
    rec_model="PP-OCRv5_mobile_rec",
    engine="onnxruntime",
)
print("Loaded → PP-OCRv5 (docling.py OCR engine)")

tf_predictor = load_tf_predictor(TABLEFORMER_ARTIFACTS_DIR)
print("Loaded → TableFormer (accurate)")


# ============================================================
# ALL MODELS READY
# ============================================================

print("All models loaded successfully")
