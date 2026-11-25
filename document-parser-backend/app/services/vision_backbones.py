# # app/services/vision_backbones.py
# """
# Reusable model classes for the custom document-intelligence path (docling.py):

# - LayoutDetector : local ONNX layout model, used to find table regions
# - OCREngine      : PaddleOCR PP-OCRv5 detector + recognizer
# - load_tf_predictor : loads Docling's TableFormer (TFPredictor) once

# These are defined here (rather than in model_loading.py or docling.py
# directly) so that:
#   - model_loading.py can import + instantiate them once at startup
#   - docling.py can import the *instances* from model_loading.py
# without creating a circular import between the two.
# """

# import json
# import os
# from typing import Optional

# import numpy as np
# import onnxruntime as ort
# from PIL import Image
# from paddleocr import TextDetection, TextRecognition

# from docling_ibm_models.tableformer.data_management.tf_predictor import TFPredictor


# # Full label map for the docling-layout-heron ONNX model
# LAYOUT_CLASSES = {
#     0:  "Caption",
#     1:  "Footnote",
#     2:  "Formula",
#     3:  "List-item",
#     4:  "Page-footer",
#     5:  "Page-header",
#     6:  "Picture",
#     7:  "Section-header",
#     8:  "Table",
#     9:  "Text",
#     10: "Title",
#     11: "Document Index",
#     12: "Code",
#     13: "Checkbox-Selected",
#     14: "Checkbox-Unselected",
#     15: "Form",
#     16: "Key-Value Region",
# }


# # ──────────────────────────────────────────────────────────────────────────────
# # Layout detection (ONNX)
# # ──────────────────────────────────────────────────────────────────────────────
# class LayoutDetector:

#     MODEL_INPUT_SIZE = 640

#     def __init__(
#         self,
#         onnx_path: str,
#         threshold: float = 0.7,
#         providers: Optional[list] = None,
#     ):
#         if providers is None:
#             available = ort.get_available_providers()
#             providers = (
#                 ["CUDAExecutionProvider", "CPUExecutionProvider"]
#                 if "CUDAExecutionProvider" in available
#                 else ["CPUExecutionProvider"]
#             )
#         self.session = ort.InferenceSession(onnx_path, providers=providers)
#         self.threshold = threshold
#         print(f"[layout] ONNX session ready  providers={self.session.get_providers()}")

#     def detect(self, image: Image.Image) -> list:

#         S = self.MODEL_INPUT_SIZE

#         resized = image.resize((S, S))
#         img_np = np.array(resized, dtype=np.uint8).transpose(2, 0, 1)
#         img_np = np.expand_dims(img_np, axis=0)
#         orig_sz = np.array([[S, S]], dtype=np.int64)

#         labels_out, boxes_out, scores_out = self.session.run(
#             None,
#             {"images": img_np, "orig_target_sizes": orig_sz},
#         )

#         labels = labels_out[0]
#         boxes = boxes_out[0]
#         scores = scores_out[0]

#         keep = scores >= self.threshold
#         labels = labels[keep]
#         boxes = boxes[keep]
#         scores = scores[keep]

#         sx = image.width / S
#         sy = image.height / S

#         detections = []
#         for lbl_id, box, score in zip(labels, boxes, scores):
#             detections.append({
#                 "label": LAYOUT_CLASSES.get(int(lbl_id), f"class_{int(lbl_id)}"),
#                 "score": round(float(score), 3),
#                 "bbox": [
#                     round(box[0] * sx, 1),
#                     round(box[1] * sy, 1),
#                     round(box[2] * sx, 1),
#                     round(box[3] * sy, 1),
#                 ],
#             })

#         return detections


# # ──────────────────────────────────────────────────────────────────────────────
# # OCR (PaddleOCR PP-OCRv5)
# # ──────────────────────────────────────────────────────────────────────────────
# class OCREngine:
#     def __init__(
#         self,
#         det_model: str = "PP-OCRv5_server_det",
#         rec_model: str = "PP-OCRv5_mobile_rec",
#         engine: str = "onnxruntime",
#         det_thresh: float = 0.2,
#         rec_thresh: float = 0.2,
#     ):
#         self.det = TextDetection(model_name=det_model, engine=engine)
#         self.rec = TextRecognition(model_name=rec_model, engine=engine)
#         self.det_thresh = det_thresh
#         self.rec_thresh = rec_thresh
#         print(f"[ocr] PaddleOCR ready  det={det_model}  rec={rec_model}")

#     def run(self, image: Image.Image) -> list:

#         img_np = np.array(image.convert("RGB"))
#         det_result = self.det.predict(img_np)
#         tokens = []

#         if not det_result or det_result[0] is None:
#             return tokens

#         dt_polys = det_result[0].get("dt_polys", [])
#         dt_scores = det_result[0].get("dt_scores", [1.0] * len(dt_polys))

#         for cell_id, (poly, det_score) in enumerate(zip(dt_polys, dt_scores)):
#             if det_score < self.det_thresh:
#                 continue
#             poly_np = np.asarray(poly)
#             x0 = int(poly_np[:, 0].min()); x1 = int(poly_np[:, 0].max())
#             y0 = int(poly_np[:, 1].min()); y1 = int(poly_np[:, 1].max())
#             if x1 <= x0 or y1 <= y0:
#                 continue
#             crop = img_np[y0:y1, x0:x1]
#             if crop.size == 0:
#                 continue
#             rec_res = self.rec.predict(crop)
#             if not rec_res or rec_res[0] is None:
#                 continue
#             text = rec_res[0].get("rec_text", "")
#             rec_score = rec_res[0].get("rec_score", 0.0)
#             if not text or rec_score < self.rec_thresh:
#                 continue

#             tokens.append({
#                 "id": cell_id,
#                 "text": text,
#                 "bbox": {"l": x0, "t": y0, "r": x1, "b": y1},
#                 "det_score": round(float(det_score), 4),
#                 "rec_score": round(float(rec_score), 4),
#             })

#         # Reading order: top (y), then left (x) as tiebreaker.
#         tokens.sort(key=lambda t: (t["bbox"]["t"], t["bbox"]["l"]))
#         for new_id, tok in enumerate(tokens):
#             tok["id"] = new_id

#         return tokens


# # ──────────────────────────────────────────────────────────────────────────────
# # TableFormer (Docling's TFPredictor)
# # ──────────────────────────────────────────────────────────────────────────────
# def load_tf_predictor(
#     artifacts_dir: str,
#     device: str = "cpu",
#     num_threads: int = 4,
# ) -> TFPredictor:
#     config_path = os.path.join(artifacts_dir, "tm_config.json")
#     with open(config_path) as f:
#         tf_config = json.load(f)

#     tf_config.setdefault("model", {})["save_dir"] = artifacts_dir
#     tf_config.setdefault("predict", {})
#     tf_config["predict"].setdefault("pdf_cell_iou_thres", 0.05)
#     tf_config["predict"].setdefault("bbox", True)
#     tf_config["predict"]["device"] = device

#     predictor = TFPredictor(tf_config, device=device, num_threads=num_threads)
#     print(f"[tableformer] TFPredictor ready  artifacts_dir={artifacts_dir}")
#     return predictor



# app/services/vision_backbones.py
"""
Reusable model classes for the custom document-intelligence path (docling.py):

- LayoutDetector : local ONNX layout model, used to find table regions
- OCREngine      : PaddleOCR PP-OCRv5 detector + recognizer
- load_tf_predictor : loads Docling's TableFormer (TFPredictor) once

These are defined here (rather than in model_loading.py or docling.py
directly) so that:
  - model_loading.py can import + instantiate them once at startup
  - docling.py can import the *instances* from model_loading.py
without creating a circular import between the two.
"""

import json
import os
from typing import Optional

import numpy as np
import onnxruntime as ort
from PIL import Image
from paddleocr import TextDetection, TextRecognition

from docling_ibm_models.tableformer.data_management.tf_predictor import TFPredictor


# Full label map for the docling-layout-heron ONNX model
LAYOUT_CLASSES = {
    0:  "Caption",
    1:  "Footnote",
    2:  "Formula",
    3:  "List-item",
    4:  "Page-footer",
    5:  "Page-header",
    6:  "Picture",
    7:  "Section-header",
    8:  "Table",
    9:  "Text",
    10: "Title",
    11: "Document Index",
    12: "Code",
    13: "Checkbox-Selected",
    14: "Checkbox-Unselected",
    15: "Form",
    16: "Key-Value Region",
}


# ──────────────────────────────────────────────────────────────────────────────
# Layout detection (ONNX)
# ──────────────────────────────────────────────────────────────────────────────
class LayoutDetector:

    MODEL_INPUT_SIZE = 640

    def __init__(
        self,
        onnx_path: str,
        threshold: float = 0.7,
        providers: Optional[list] = None,
    ):
        if providers is None:
            available = ort.get_available_providers()
            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if "CUDAExecutionProvider" in available
                else ["CPUExecutionProvider"]
            )
        self.session = ort.InferenceSession(onnx_path, providers=providers)
        self.threshold = threshold
        print(f"[layout] ONNX session ready  providers={self.session.get_providers()}")

    def detect(self, image: Image.Image) -> list:

        S = self.MODEL_INPUT_SIZE

        resized = image.resize((S, S))
        img_np = np.array(resized, dtype=np.uint8).transpose(2, 0, 1)
        img_np = np.expand_dims(img_np, axis=0)
        orig_sz = np.array([[S, S]], dtype=np.int64)

        labels_out, boxes_out, scores_out = self.session.run(
            None,
            {"images": img_np, "orig_target_sizes": orig_sz},
        )

        labels = labels_out[0]
        boxes = boxes_out[0]
        scores = scores_out[0]

        keep = scores >= self.threshold
        labels = labels[keep]
        boxes = boxes[keep]
        scores = scores[keep]

        sx = image.width / S
        sy = image.height / S

        detections = []
        for lbl_id, box, score in zip(labels, boxes, scores):
            # NOTE (FIX): box[i] is numpy.float32 straight from the ONNX
            # session. round(x, ndigits) with an explicit ndigits PRESERVES
            # the input's type (unlike single-arg round(), which always
            # returns a plain Python int) — so without an explicit float()
            # cast here, these stay numpy.float32 and break json.dump()
            # wherever this bbox is serialized directly (e.g.
            # layout.docling_layout in raw.json/response.json).
            # Casting to float() BEFORE rounding guarantees a native
            # Python float everywhere this detection is used — as a
            # table_bbox after cropping, and as a raw docling_layout entry.
            detections.append({
                "label": LAYOUT_CLASSES.get(int(lbl_id), f"class_{int(lbl_id)}"),
                "score": round(float(score), 3),
                "bbox": [
                    round(float(box[0]) * sx, 1),
                    round(float(box[1]) * sy, 1),
                    round(float(box[2]) * sx, 1),
                    round(float(box[3]) * sy, 1),
                ],
            })

        return detections


# ──────────────────────────────────────────────────────────────────────────────
# OCR (PaddleOCR PP-OCRv5)
# ──────────────────────────────────────────────────────────────────────────────
class OCREngine:
    def __init__(
        self,
        det_model: str = "PP-OCRv6_medium_det",
        rec_model: str = "PP-OCRv6_medium_rec",
        engine: str = "onnxruntime",
        det_thresh: float = 0.2,
        rec_thresh: float = 0.2,
    ):
        self.det = TextDetection(model_name=det_model, engine=engine)
        self.rec = TextRecognition(model_name=rec_model, engine=engine)
        self.det_thresh = det_thresh
        self.rec_thresh = rec_thresh
        print(f"[ocr] PaddleOCR ready  det={det_model}  rec={rec_model}")

    def run(self, image: Image.Image) -> list:

        img_np = np.array(image.convert("RGB"))
        det_result = self.det.predict(img_np)
        tokens = []

        if not det_result or det_result[0] is None:
            return tokens

        dt_polys = det_result[0].get("dt_polys", [])
        dt_scores = det_result[0].get("dt_scores", [1.0] * len(dt_polys))

        for cell_id, (poly, det_score) in enumerate(zip(dt_polys, dt_scores)):
            if det_score < self.det_thresh:
                continue
            poly_np = np.asarray(poly)
            x0 = int(poly_np[:, 0].min()); x1 = int(poly_np[:, 0].max())
            y0 = int(poly_np[:, 1].min()); y1 = int(poly_np[:, 1].max())
            if x1 <= x0 or y1 <= y0:
                continue
            crop = img_np[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            rec_res = self.rec.predict(crop)
            if not rec_res or rec_res[0] is None:
                continue
            text = rec_res[0].get("rec_text", "")
            rec_score = rec_res[0].get("rec_score", 0.0)
            if not text or rec_score < self.rec_thresh:
                continue

            tokens.append({
                "id": cell_id,
                "text": text,
                "bbox": {"l": x0, "t": y0, "r": x1, "b": y1},
                "det_score": round(float(det_score), 4),
                "rec_score": round(float(rec_score), 4),
            })

        # Reading order: top (y), then left (x) as tiebreaker.
        tokens.sort(key=lambda t: (t["bbox"]["t"], t["bbox"]["l"]))
        for new_id, tok in enumerate(tokens):
            tok["id"] = new_id

        return tokens


# ──────────────────────────────────────────────────────────────────────────────
# TableFormer (Docling's TFPredictor)
# ──────────────────────────────────────────────────────────────────────────────
def load_tf_predictor(
    artifacts_dir: str,
    device: str = "cpu",
    num_threads: int = 4,
) -> TFPredictor:
    config_path = os.path.join(artifacts_dir, "tm_config.json")
    with open(config_path) as f:
        tf_config = json.load(f)

    tf_config.setdefault("model", {})["save_dir"] = artifacts_dir
    tf_config.setdefault("predict", {})
    tf_config["predict"].setdefault("pdf_cell_iou_thres", 0.05)
    tf_config["predict"].setdefault("bbox", True)
    tf_config["predict"]["device"] = device

    predictor = TFPredictor(tf_config, device=device, num_threads=num_threads)
    print(f"[tableformer] TFPredictor ready  artifacts_dir={artifacts_dir}")
    return predictor