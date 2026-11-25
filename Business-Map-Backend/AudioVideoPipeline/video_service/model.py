###############################################################
# VIDEO SERVICE — MODEL
# Qwen3-VL model loading, device setup, and inference helper
###############################################################

import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

import torch
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

logger = logging.getLogger(__name__)

# ==================================================
# PERSISTENT MODEL STORAGE
# ==================================================
# Same pattern as audio_service/pipeline_v3_1_production.py: reuse a local
# copy if one already exists, else copy from an optional shared
# PERSISTENT_MODELS_DIR, else download straight into the portable
# LOCAL_MODEL_CACHE_DIR (repo_root/models by default) via
# audio_service/download_models.py's download_qwen(). This keeps Qwen3-VL
# cached the same consistent way as Whisper, instead of
# falling back to the default ~/.cache/huggingface/hub.

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PERSISTENT_MODELS_DIR = os.environ.get("PERSISTENT_MODELS_DIR")
LOCAL_MODEL_CACHE_DIR = Path(os.environ.get("LOCAL_MODEL_CACHE_DIR", str(_REPO_ROOT / "models")))

# download_qwen lives in audio_service/download_models.py alongside the
# other downloaders; add that folder to sys.path so it can be imported
# from here without duplicating the download logic.
_AUDIO_SERVICE_DIR = _REPO_ROOT / "AudioVideoPipeline" / "audio_service"
if str(_AUDIO_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_AUDIO_SERVICE_DIR))


def _ensure_local_qwen(model_id: str) -> str:
    """Guarantee a local, loadable copy of Qwen3-VL exists; returns its path."""
    name = model_id.split("/")[-1]
    dst = LOCAL_MODEL_CACHE_DIR / name

    if dst.exists() and any(dst.rglob("*")):
        logger.info(f"[model-cache] '{name}' already present locally at {dst}.")
        return str(dst)

    if PERSISTENT_MODELS_DIR:
        src = Path(PERSISTENT_MODELS_DIR) / name
        if src.exists():
            logger.info(f"[model-cache] Copying '{name}' from persistent storage ({src}) -> {dst} ...")
            LOCAL_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
            return str(dst)
        logger.info(f"[model-cache] No persistent copy of '{name}' found at {src}; will download instead.")

    logger.info(f"[model-cache] Downloading '{name}' (first time this session)...")
    from download_models import download_qwen
    download_qwen(dst, model_id)
    return str(dst)


def _resolve_qwen_source(model_id: str) -> str:
    """
    Resolve a loadable source for Qwen3-VL, with a fallback chain so a
    single broken step never kills startup:
      1. Local-cache-first via _ensure_local_qwen() (models/ folder,
         optionally seeded from PERSISTENT_MODELS_DIR).
      2. If that fails for any reason (disk full, permission error,
         corrupted partial download, network blip during the copy/
         download step, etc.) — fall back to handing the bare repo id
         straight to from_pretrained, which downloads into the default
         ~/.cache/huggingface/hub instead. Slower/less portable, but
         keeps the service usable rather than failing outright.
    """
    try:
        return _ensure_local_qwen(model_id)
    except Exception as e:
        logger.warning(
            f"[model-cache] Local resolution of '{model_id}' failed ({e}); "
            f"falling back to default Hugging Face cache."
        )
        return model_id

device = "cuda" if torch.cuda.is_available() else "cpu"

if device == "cpu":
    # Make sure PyTorch actually uses every available core for CPU
    # inference — left at its default in some environments, this can be
    # artificially limited.
    torch.set_num_threads(os.cpu_count() or 4)
    logger.info(f"CPU inference — using {torch.get_num_threads()} threads")

# ==================================================
# TOKEN LIMITS
# ==================================================

MAX_NEW_TOKENS_ACTION   = 64    # single action line needs ~20-30 tokens
MAX_NEW_TOKENS_SUMMARY  = 2048  # per-batch summary JSON
MAX_NEW_TOKENS_SEMANTIC = 150   # semantic judge JSON response

# ==================================================
# RETRY CONFIG
# ==================================================

_INFERENCE_MAX_RETRIES = 2
_INFERENCE_RETRY_DELAY = 1.0

# ==================================================
# MODEL CACHE (Singleton)
# ==================================================

_model     = None
_processor = None

MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"

_load_error: str | None = None


def load_model():
    """
    Load model and processor once. Returns (model, processor) on success.

    Raises RuntimeError on load failure. app.py calls this during startup;
    a failed load must abort the service so /submit-job is never served
    without a working model.
    """
    global _model, _processor, device, _load_error

    if _model is not None and _processor is not None:
        return _model, _processor

    dtype = torch.float16 if device == "cuda" else torch.float32
    model_source = _resolve_qwen_source(MODEL_ID)
    logger.info(f"Loading model: {MODEL_ID} from {model_source} on device={device} (dtype={dtype})")

    try:
        _model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_source, torch_dtype=dtype, device_map=None,
        ).to(device)
        _processor = AutoProcessor.from_pretrained(
            model_source, min_pixels=256 * 28 * 28, max_pixels=896 * 28 * 28,
        )
    except (RuntimeError, torch.cuda.OutOfMemoryError) as e:
        if device != "cuda":
            _load_error = f"CPU load failed: {e}"
            logger.error(_load_error)
            _model, _processor = None, None
            raise RuntimeError(_load_error)

        logger.warning(f"GPU load of '{MODEL_ID}' failed ({e}); falling back to CPU.")
        _model, _processor = None, None
        torch.cuda.empty_cache()
        device = "cpu"
        dtype = torch.float32
        torch.set_num_threads(os.cpu_count() or 4)

        try:
            _model = Qwen3VLForConditionalGeneration.from_pretrained(
                model_source, torch_dtype=dtype, device_map=None,
            ).to(device)
            _processor = AutoProcessor.from_pretrained(
                model_source, min_pixels=256 * 28 * 28, max_pixels=896 * 28 * 28,
            )
        except Exception as e2:
            _load_error = f"CPU fallback also failed: {e2}"
            logger.error(_load_error)
            _model, _processor = None, None
            raise RuntimeError(_load_error)
    except Exception as e:
        # Anything else unexpected (bad download, missing files, etc.)
        _load_error = f"Unexpected load failure: {e}"
        logger.error(_load_error)
        _model, _processor = None, None
        raise RuntimeError(_load_error)

    _load_error = None
    logger.info("✓ Model and processor loaded")
    return _model, _processor


def get_model():
    """Return already-loaded model. Raises if not initialized."""
    if _model is None or _processor is None:
        raise RuntimeError("Model not loaded — call load_model() at startup")
    return _model, _processor


def is_model_ready() -> bool:
    """True once the model has loaded successfully."""
    return _model is not None and _processor is not None


def get_load_error() -> str | None:
    """Returns the last load-failure reason, or None if load succeeded / hasn't been attempted."""
    return _load_error

# ==================================================
# INFERENCE HELPER (with retry)
# ==================================================

def run_inference(messages: list, max_new_tokens: int = MAX_NEW_TOKENS_ACTION) -> str:
    """
    Single forward pass through Qwen3-VL. Returns decoded text.

    Includes retry logic for transient inference failures (2 retries
    with backoff) before the existing GPU→CPU fallback. This ensures
    the pipeline stays resilient to temporary GPU memory spikes or
    transient runtime errors without crashing the overall flow.
    """
    global _model, _processor, device
    model, processor = get_model()

    # Retry loop for transient failures
    last_error = None
    for attempt in range(1, _INFERENCE_MAX_RETRIES + 1):
        try:
            return _generate(model, processor, messages, max_new_tokens, device)
        except (RuntimeError, torch.cuda.OutOfMemoryError) as e:
            last_error = e
            # A mid-run GPU OOM (e.g. an unusually large/long frame batch)
            # shouldn't fail the whole job if we can still finish it on CPU.
            # This is a one-time fallback: once we've dropped to CPU we stay
            # there (device is updated globally) rather than retrying this
            # path on every call.
            if device != "cuda" or "out of memory" not in str(e).lower():
                if attempt < _INFERENCE_MAX_RETRIES:
                    backoff = _INFERENCE_RETRY_DELAY * attempt
                    logger.warning(f"Inference attempt {attempt} failed ({e}); retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                    continue
                raise
            logger.warning(
                f"GPU inference OOM ({e}); retrying this request on CPU and "
                f"switching device for subsequent calls."
            )
            torch.cuda.empty_cache()
            device = "cpu"
            torch.set_num_threads(os.cpu_count() or 4)
            model = model.to(device)
            _model = model
            return _generate(model, processor, messages, max_new_tokens, device)
        except Exception as e:
            last_error = e
            if attempt < _INFERENCE_MAX_RETRIES:
                backoff = _INFERENCE_RETRY_DELAY * attempt
                logger.warning(f"Inference attempt {attempt} failed ({e}); retrying in {backoff:.1f}s...")
                time.sleep(backoff)
                continue
            raise

    raise last_error


def _generate(model, processor, messages: list, max_new_tokens: int, run_device: str) -> str:
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    inputs = {k: v.to(run_device) for k, v in inputs.items()}

    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)

    trimmed = [
        out[len(inp):]
        for inp, out in zip(inputs["input_ids"], generated_ids)
    ]
    return processor.batch_decode(
        trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()


# ==================================================
# JSON RESPONSE PARSER
# ==================================================

def parse_json_response(raw: str) -> dict:
    """
    Robust JSON parser — handles markdown fences, leading/trailing garbage,
    and truncated output. Returns parsed dict or raises ValueError.
    """
    clean = raw.strip()

    # Strip markdown fences
    if clean.startswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
    clean = clean.rstrip("`").strip()

    # Attempt 1: direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract first {...} block
    s, e = clean.find("{"), clean.rfind("}") + 1
    if s != -1 and e > s:
        try:
            return json.loads(clean[s:e])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in: {raw[:200]}")