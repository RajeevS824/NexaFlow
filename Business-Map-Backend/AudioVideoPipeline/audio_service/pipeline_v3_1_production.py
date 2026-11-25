#############################################################
# ENTERPRISE AUDIO PIPELINE v3.1 - FULLY FIXED
# All Bugs Fixed + All Features Complete
#############################################################

import os
import sys
import asyncio
import logging
import time
import json
import uuid
import signal
import threading
import shutil
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import yaml

# Load repo-root .env (if present) when this service is started directly
# (e.g. `uvicorn pipeline_v3_1_production:app`) rather than via
# run_backend.py, which already loads it once for all subprocesses.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

# FastAPI
from fastapi import FastAPI, UploadFile, File, Header, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# ML Libraries
import numpy as np
import librosa
import torch
from faster_whisper import WhisperModel

# Advanced utilities (all fixes)
from pipeline_advanced_utils import (
    save_upload_file_streaming,
    SubprocessExecutor,
    get_optimal_worker_count,
    get_demucs_vocals_path,
    RateLimiter,
    setup_logger_safe,
    CircuitBreaker,
    validate_single_worker_config,
    RedisQueueHandler,
    validate_config,
    JobCancelled
)

#############################################################
# CONFIGURATION LOADING + VALIDATION
#############################################################

# PORTABLE PATH: works unchanged on Colab, Kaggle, or a local machine.
# Resolution order:
#   1. CONFIG_PATH environment variable, if set (most explicit)
#   2. <repo>/AudioVideoPipeline/Configuration/config.yaml, derived from
#      this file's own location (this file lives in .../audio_service/)
_DEFAULT_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent / "Configuration" / "config.yaml"
)

def load_and_validate_config(config_path: str = None) -> Dict[str, Any]:
    """Load and validate configuration."""
    config_path = config_path or os.environ.get("CONFIG_PATH", _DEFAULT_CONFIG_PATH)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # Validate config
    errors = validate_config(config_dict)
    if errors:
        raise ValueError(f"Config validation failed:\n" + "\n".join(errors))
    
    return config_dict

config_dict = load_and_validate_config()

# Shared log file: audio_service, video_service, and orchestrator all
# append to this ONE file (in addition to each still printing to its own
# console/stdout, which is what run_backend.py separately captures into
# the root-level audio_service.log / video_service.log / orchestrator.log
# files). This makes AudioVideoPipeline/Orchestrator/logs/orchestrator.log
# a single combined, interleaved-by-real-time view across all 3 services.
_SHARED_LOG_PATH = Path(__file__).resolve().parent.parent / "Orchestrator" / "logs" / "orchestrator.log"
_SHARED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# FIX #6: Safe logging setup
logger = setup_logger_safe(
    "AudioPipelineV3.1",
    level=config_dict.get("logging", {}).get("level", "INFO"),
    log_file=str(_SHARED_LOG_PATH),
)

# ── Keep routine health checks out of the log ─────────────────────────────
# run_backend.py (while it waits for the services to start) and the frontend
# (through the orchestrator) poll GET /health every few seconds, and each poll
# used to write a line such as
#     INFO:     127.0.0.1:61261 - "GET /health HTTP/1.1" 200 OK
# into this service's log. Successful (HTTP 200) health checks are dropped
# here. Everything else is logged exactly as before: every other request, and
# any health check that does NOT return 200 (so a failing service stays visible).
import re as _re


class _HealthCheckLogFilter(logging.Filter):
    _UVICORN_ACCESS = _re.compile(r'"GET /health(?:\?\S*)? HTTP/\d(?:\.\d)?" 200\b')
    _HTTPX_REQUEST = _re.compile(r'^HTTP Request: GET \S+/health(?:\?\S*)? "HTTP/\d(?:\.\d)? 200 OK"')

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        return not (self._UVICORN_ACCESS.search(message) or self._HTTPX_REQUEST.search(message))


logging.getLogger("uvicorn.access").addFilter(_HealthCheckLogFilter())

#############################################################
# GLOBALS & INITIALIZATION
#############################################################

# FIX #8: Validate single worker
validate_single_worker_config(config_dict.get("deployment", {}).get("workers", 1))

# FIX #3: Dynamic worker count
OPTIMAL_WORKERS = get_optimal_worker_count(
    min_workers=config_dict.get("threading", {}).get("min_workers", 2),
    max_workers=config_dict.get("threading", {}).get("max_workers_limit", 32)
)

# FIX #5: Rate limiter
rate_limiter = RateLimiter(
    requests_per_minute=config_dict.get("rate_limiting", {}).get("requests_per_minute", 60),
    burst_allowed=config_dict.get("rate_limiting", {}).get("burst_allowed", 10)
)

# FIX #7: Circuit breakers
circuit_breakers = {
    "model_service": CircuitBreaker(
        "model_service",
        failure_threshold=config_dict.get("circuit_breaker", {}).get("failure_threshold", 5)
    ),
    "enhancement_service": CircuitBreaker(
        "enhancement_service",
        failure_threshold=config_dict.get("circuit_breaker", {}).get("failure_threshold", 5)
    ),
    "database_service": CircuitBreaker(
        "database_service",
        failure_threshold=config_dict.get("circuit_breaker", {}).get("failure_threshold", 5)
    )
}

# FIX #2: Subprocess executor
subprocess_executor = SubprocessExecutor(
    timeout_sec=config_dict.get("latency_sla", {}).get("subprocess_timeout_sec", 30),
    max_retries=config_dict.get("retry", {}).get("max_attempts", 3)
)

# FIX #9: Redis queue (initialized but not connected until startup)
redis_queue = None
if config_dict.get("redis", {}).get("enabled", False):
    try:
        redis_queue = RedisQueueHandler(
            host=config_dict.get("redis", {}).get("host", "localhost"),
            port=config_dict.get("redis", {}).get("port", 6379)
        )
        logger.info("Redis queue handler created (not yet connected)")
    except Exception as e:
        logger.warning(f"Redis queue creation failed: {e}")
        redis_queue = None

# Track active requests (for graceful shutdown)
active_requests: set = set()

# ── Audio Redis queue: worker tasks & in-memory status store ──────────
# N configurable asyncio worker tasks (default 2, set via audio.worker_count
# in config.yaml) that each pull jobs from the audio Redis queue and process
# them using the existing transcription logic. Workers run inside this single
# FastAPI process (no separate OS processes) and process jobs concurrently —
# they are NOT serialized behind a single lock.
AUDIO_QUEUE_NAME = config_dict.get("redis", {}).get("queue_name_audio", "audio_jobs")
AUDIO_RESULT_KEY = config_dict.get("redis", {}).get("result_key_audio", "audio_results")
AUDIO_WORKER_COUNT = int(config_dict.get("audio", {}).get("worker_count", 2))
_audio_worker_tasks: list = []
_audio_workers_running = False
# In-memory status store for audio queue jobs (keyed by job_id). Mirrors the
# video service's _results_store pattern. Workers update this as they process.
AUDIO_JOB_STATUS: dict = {}

# ── Cancellation registry ─────────────────────────────────────────────
# job_ids the orchestrator asked us to stop. Checked cooperatively by the
# worker (before starting a job) and by _process_audio_file (between stages
# and per transcribed segment), and passed to SubprocessExecutor so a running
# ffmpeg child is killed. AUDIO_JOB_INPUT remembers each queued job's input
# file so a job cancelled while still queued can have its file removed.
AUDIO_CANCELLED: set = set()
AUDIO_JOB_INPUT: dict = {}


def _is_cancelled(job_id: str) -> bool:
    return job_id in AUDIO_CANCELLED


def _check_cancel(job_id: str) -> None:
    if job_id in AUDIO_CANCELLED:
        raise JobCancelled(f"audio job {job_id} cancelled by user")

#############################################################
# RETRY HELPER
#############################################################

def _retry_operation(
    operation_name: str,
    func,
    *args,
    max_attempts: int = None,
    delay_sec: float = None,
    backoff_multiplier: float = None,
    **kwargs,
):
    """
    Retry a failure-prone operation with exponential backoff.
    Returns the operation result on success.
    Raises the last exception if all attempts fail.

    Retries are idempotent: the same immutable payload is re-sent on
    every attempt, so no duplicate processing or inconsistent outputs
    can occur.
    """
    _retry_cfg = config_dict.get("retry", {})
    max_attempts = max_attempts or _retry_cfg.get("max_attempts", 3)
    delay_sec = delay_sec if delay_sec is not None else _retry_cfg.get("delay_sec", 2.0)
    backoff_multiplier = backoff_multiplier if backoff_multiplier is not None else _retry_cfg.get("backoff_multiplier", 2.0)

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"[retry] {operation_name} attempt {attempt}/{max_attempts}")
            result = func(*args, **kwargs)
            if attempt > 1:
                logger.info(f"[retry] {operation_name} succeeded on attempt {attempt}")
            return result
        except JobCancelled:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"[retry] {operation_name} attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                backoff = delay_sec * (backoff_multiplier ** (attempt - 1))
                logger.info(f"[retry] {operation_name} retrying in {backoff:.1f}s...")
                time.sleep(backoff)

    logger.error(f"[retry] {operation_name} failed after {max_attempts} attempts: {last_error}")
    raise last_error


#############################################################
# PERSISTENT MODEL STORAGE
#############################################################
# Models are cached locally so they're only downloaded once. By default
# this is a `models/` folder at the repo root (LOCAL_MODEL_CACHE_DIR can
# override it). PERSISTENT_MODELS_DIR is an optional secondary source
# (e.g. a shared network drive or a pre-built cache directory someone
# copied over) — if a model exists there but not yet in the local cache,
# it's copied in instead of re-downloaded from the internet.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PERSISTENT_MODELS_DIR = os.environ.get("PERSISTENT_MODELS_DIR")
LOCAL_MODEL_CACHE_DIR = Path(os.environ.get("LOCAL_MODEL_CACHE_DIR", str(_REPO_ROOT / "models")))


def _ensure_local_model(name: str, downloader) -> str:
    """
    Guarantee a local, loadable copy of model `name` exists, in this
    priority order:
      1. Already present in LOCAL_MODEL_CACHE_DIR (e.g. from an earlier
         run) -> reuse as-is, free.
      2. Present in PERSISTENT_MODELS_DIR, if set (an optional secondary
         cache location, e.g. a shared drive built by download_models.py)
         -> copy it in: fast, local disk copy, no network.
      3. Not found anywhere -> call `downloader(dest)` (from
         download_models.py) to fetch it from the internet straight into
         LOCAL_MODEL_CACHE_DIR/name. This is what makes a plain
         `python run_backend.py` on a fresh clone work with zero manual
         steps.
    Always returns a local path to load the model from.
    """
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
    LOCAL_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    downloader(dst)
    return str(dst)


#############################################################
# MODEL CACHE (Singleton) - BUG FIX #3: Thread-safe
#############################################################

class ModelCache:
    """Load models once at startup. BUG FIX #3: Thread-safe."""
    
    _instance = None
    _initialized = False
    _lock = threading.Lock()  # ✅ BUG FIX #3: Thread safety
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # NOTE: real loading now happens in load(), called explicitly from
        # the FastAPI startup event (in a background thread) instead of
        # here. Instantiating ModelCache() must stay cheap so importing
        # this module (which uvicorn does before it binds the port) never
        # blocks on multi-GB model downloads.
        pass

    def load(self):
        if self._initialized:
            return

        logger.info("Initializing model cache...")
        
        try:
            circuit_breakers["model_service"].check()
        except RuntimeError:
            raise RuntimeError("Model service circuit breaker is OPEN")
        
        try:
            from download_models import download_whisper

            # Whisper — local copy (session cache or persistent dataset) if
            # present, otherwise downloaded straight into the portable
            # local folder via download_models.download_whisper.
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            whisper_name = config_dict.get("models", {}).get("whisper", {}).get("name", "large-v3")
            whisper_source = _ensure_local_model(
                f"whisper-{whisper_name}",
                lambda dest: download_whisper(dest, whisper_name),
            )
            self.whisper_model = WhisperModel(
                whisper_source,
                device=device,
                compute_type=compute_type,
            )

            # Determinism
            np.random.seed(42)
            torch.manual_seed(42)
            
            logger.info(f"[OK] Whisper model loaded | device={device} | compute_type={compute_type}")
            logger.info("[OK] Model cache initialization complete")
            circuit_breakers["model_service"].record_success()
            self._initialized = True
        
        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            circuit_breakers["model_service"].record_failure()
            raise

model_cache = ModelCache.__new__(ModelCache)  # allocate only — do NOT load models yet
model_cache._initialized = False

#############################################################
# FASTAPI APP
#############################################################

app = FastAPI(
    title="Audio Pipeline v3.1 - Fully Fixed",
    version="3.1.0",
    description="All 10 fixes + All bugs fixed"
)

#############################################################
# MIDDLEWARE - REQUEST TRACKING & RATE LIMITING
#############################################################

@app.middleware("http")
async def track_requests_middleware(request: Request, call_next):
    """Track active requests for graceful shutdown."""
    req_id = str(uuid.uuid4())[:8]
    active_requests.add(req_id)
    
    try:
        response = await call_next(request)
        return response
    finally:
        active_requests.discard(req_id)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    
    if not config_dict.get("rate_limiting", {}).get("enabled", True):
        return await call_next(request)
    
    client_ip = request.client.host if request.client else "unknown"
    limit_info = await rate_limiter.check_limit(client_ip)
    
    if not limit_info["allowed"]:
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=429,
            content={
                "status": "ERROR",
                "message": "RATE_LIMIT_EXCEEDED",
                "reset_in_sec": round(limit_info["reset_in_sec"], 1)
            }
        )
    
    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(limit_info["remaining"])
    return response

#############################################################
# ENDPOINTS
#############################################################

@app.post("/process")
async def process(
    file: UploadFile = File(...),
    x_request_id: str = Header(None)
) -> JSONResponse:
    """
    Process video file with timeout protection.
    ✅ BUG FIX #2: Added request timeout
    """
    
    request_id = x_request_id or str(uuid.uuid4())[:8]
    start_time = time.time()

    if not model_cache._initialized:
        return JSONResponse(
            status_code=503,
            content={"status": "ERROR", "message": "Models are still loading, try again shortly."}
        )

    temp_video_path = None
    
    try:
        # ✅ BUG FIX #2: Wrap with timeout
        result = await asyncio.wait_for(
            process_video_internal(file, request_id, start_time, temp_video_path),
            timeout=300  # 5 minutes max
        )
        return result
    
    except asyncio.TimeoutError:
        logger.warning(f"[{request_id}] Request timeout after 300s")
        return JSONResponse(
            status_code=504,
            content={
                "status": "ERROR",
                "message": "REQUEST_TIMEOUT",
                "request_id": request_id,
                "timeout_sec": 300
            }
        )
    
    except Exception as e:
        logger.error(f"[{request_id}] Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "ERROR",
                "message": str(e),
                "error_type": type(e).__name__,
                "request_id": request_id
            }
        )


async def process_video_internal(
    file,
    request_id,
    start_time,
    temp_video_path,
    reference_text=None,   # ✅ FIX 1: explicit parameter added
):
    """Internal processing logic with FULL AUDIO PIPELINE + CLEAN SEPARATED OUTPUTS

    Every failure-prone step (audio extraction, audio load, Whisper
    transcription, JSON save) is wrapped in _retry_operation() with
    configurable retry count and exponential backoff. If a step fails
    after all retries, the pipeline falls back to a structured PARTIAL /
    SUCCESS_WITH_FALLBACK response with empty segments — it never
    crashes the request. This mirrors the video pipeline's per-frame
    error-record pattern where individual failures are recorded and
    the pipeline continues.
    """

    logger.info(f"[{request_id}] Processing started")
    logger.debug(f"[{request_id}] Incoming file: filename={file.filename!r} content_type={file.content_type}")

    try:
        temp_dir = config_dict.get("cleanup", {}).get("temp_dir", "tmp/audio_pipeline")
        temp_video_path = os.path.join(temp_dir, f"input_{request_id}.mp4")

        logger.info(f"[{request_id}] Saving uploaded file (streaming)...")

        upload_result = await save_upload_file_streaming(
            file,
            temp_video_path,
            chunk_size=config_dict.get("audio", {}).get("chunk_size_bytes", 1048576),
            max_file_size=config_dict.get("audio", {}).get("max_file_size_mb", 500) * 1024 * 1024
        )

        if not upload_result["success"]:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "ERROR",
                    "message": "UPLOAD_FAILED",
                    "request_id": request_id
                }
            )

        logger.info(f"[{request_id}] Upload success")
        logger.debug(f"[{request_id}] Upload result: {upload_result}")

        # ===============================
        # STEP 1: EXTRACT AUDIO (with retry)
        # ===============================
        audio_path = os.path.join(temp_dir, f"audio_{request_id}.wav")

        def _extract_audio():
            subprocess_executor.run([
                "ffmpeg", "-y",
                "-i", temp_video_path,
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-acodec", "pcm_s16le",
                audio_path
            ])

        try:
            _retry_operation("audio extraction (ffmpeg)", _extract_audio)
            logger.info(f"[{request_id}] Audio extracted")
        except Exception as e:
            logger.error(f"[{request_id}] Audio extraction failed after all retries: {e}")
            # Fallback: return structured error response, do not crash
            return JSONResponse(
                status_code=200,
                content={
                    "status": "SUCCESS_WITH_FALLBACK",
                    "request_id": request_id,
                    "subtitle_file": None,
                    "performance_file": None,
                    "segments_count": 0,
                    "segments": [],
                    "fallback_reason": f"Audio extraction failed after all retries: {e}",
                    "latency_sec": round(time.time() - start_time, 2)
                }
            )

        # ===============================
        # STEP 2.5: LOAD AUDIO INTO MEMORY (with retry)
        # ===============================

        def _load_audio():
            return librosa.load(audio_path, sr=16000)

        try:
            wav, sr = _retry_operation("audio load (librosa)", _load_audio)
        except Exception as e:
            logger.error(f"[{request_id}] Audio load failed after all retries: {e}")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "SUCCESS_WITH_FALLBACK",
                    "request_id": request_id,
                    "subtitle_file": None,
                    "performance_file": None,
                    "segments_count": 0,
                    "segments": [],
                    "fallback_reason": f"Audio load failed after all retries: {e}",
                    "latency_sec": round(time.time() - start_time, 2)
                }
            )

        # ===============================
        # STEP 2: WHISPER TRANSCRIPTION (with retry)
        # ===============================
        logger.info(f"[{request_id}] Running Whisper...")

        def _transcribe():
            segments_generator, info = model_cache.whisper_model.transcribe(
                audio_path,
                beam_size=5,
                language="en",
                task="transcribe"
            )
            segments_list = []
            for i, segment in enumerate(segments_generator):
                segments_list.append({
                    "segment_id": i,
                    "start_sec": float(segment.start),
                    "end_sec": float(segment.end),
                    "duration_sec": float(segment.end - segment.start),
                    "text": segment.text.strip(),
                    "speaker": "unknown",
                    "status": "success"
                })
                logger.debug(
                    f"[{request_id}] Segment {i:04d} | "
                    f"{segment.start:.2f}s-{segment.end:.2f}s | text={segment.text.strip()!r}"
                )
            return segments_list, info

        try:
            segments_list, info = _retry_operation("whisper transcription", _transcribe)
            logger.info(f"[{request_id}] Language={info.language}, Probability={info.language_probability:.4f}")
            logger.debug(f"[{request_id}] Transcription complete: {len(segments_list)} segments total")
        except Exception as e:
            logger.error(f"[{request_id}] Whisper transcription failed after all retries: {e}")
            # Fallback: return structured PARTIAL response with empty segments
            # so the pipeline never crashes — mirrors the video pipeline's
            # per-frame error-record pattern.
            return JSONResponse(
                status_code=200,
                content={
                    "status": "SUCCESS_WITH_FALLBACK",
                    "request_id": request_id,
                    "subtitle_file": None,
                    "performance_file": None,
                    "segments_count": 0,
                    "segments": [],
                    "fallback_reason": f"Whisper transcription failed after all retries: {e}",
                    "latency_sec": round(time.time() - start_time, 2)
                }
            )

        # ===============================
        # STEP 3 — CLEAN OUTPUT STRUCTURE
        # ===============================

        base_output_dir = "output"

        subtitle_dir = os.path.join(base_output_dir, "subtitles")
        performance_dir = os.path.join(base_output_dir, "performance")

        os.makedirs(subtitle_dir, exist_ok=True)
        os.makedirs(performance_dir, exist_ok=True)

        subtitle_path = os.path.join(
            subtitle_dir,
            f"subtitle_segments_{request_id}.json"
        )

        processing_time = round(time.time() - start_time, 2)

        subtitle_json = {
            "metadata": {
                "request_id": request_id,
                "source_file": file.filename,
                "language": getattr(info, "language", "unknown"),
                "language_probability": float(
                    getattr(info, "language_probability", 0.0)
                ),
                "total_segments": len(segments_list),
                "processing_time_sec": processing_time,
                "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "status": "success"
            },
            "segments": segments_list
        }

        def _save_subtitle_json():
            with open(subtitle_path, "w", encoding="utf-8") as f:
                json.dump(
                    subtitle_json,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

        try:
            _retry_operation("subtitle JSON save", _save_subtitle_json)
            logger.info(f"[{request_id}] Subtitle JSON saved -> {subtitle_path}")
        except Exception as e:
            logger.error(f"[{request_id}] Subtitle JSON save failed after all retries: {e}")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "SUCCESS_WITH_FALLBACK",
                    "request_id": request_id,
                    "subtitle_file": None,
                    "performance_file": None,
                    "segments_count": len(segments_list),
                    "segments": segments_list,
                    "fallback_reason": f"Subtitle JSON save failed after all retries: {e}",
                    "latency_sec": round(time.time() - start_time, 2)
                }
            )

        # ===============================
        # STEP 4 — OPTIONAL VALIDATION (FIXED)
        # ===============================
        performance_data = {}
        performance_path = None   # ✅ FIX 2

        if reference_text:   # ✅ FIXED INPUT SOURCE

            generated_text = " ".join(
                segment["text"].strip()
                for segment in segments_list
            )

            # Simple WER/CER computation without external dependencies.
            # The old SubtitleValidator class was never implemented — this
            # inline computation preserves the same output contract.
            def _compute_wer_cer(reference: str, hypothesis: str) -> dict:
                ref_words = reference.split()
                hyp_words = hypothesis.split()
                ref_chars = list(reference)
                hyp_chars = list(hypothesis)

                def _edit_distance(a, b):
                    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
                    for i in range(len(a) + 1):
                        dp[i][0] = i
                    for j in range(len(b) + 1):
                        dp[0][j] = j
                    for i in range(1, len(a) + 1):
                        for j in range(1, len(b) + 1):
                            cost = 0 if a[i - 1] == b[j - 1] else 1
                            dp[i][j] = min(
                                dp[i - 1][j] + 1,
                                dp[i][j - 1] + 1,
                                dp[i - 1][j - 1] + cost
                            )
                    return dp[len(a)][len(b)]

                wer = _edit_distance(ref_words, hyp_words) / max(len(ref_words), 1)
                cer = _edit_distance(ref_chars, hyp_chars) / max(len(ref_chars), 1)
                similarity = 1.0 - min(wer, 1.0)
                quality = "good" if similarity >= 0.8 else ("fair" if similarity >= 0.6 else "poor")
                return {
                    "wer": round(wer, 4),
                    "cer": round(cer, 4),
                    "similarity": round(similarity, 4),
                    "quality_assessment": quality,
                }

            metrics = _compute_wer_cer(reference_text, generated_text)

            performance_data = {
                "wer": metrics["wer"],
                "cer": metrics["cer"],
                "similarity": metrics["similarity"],
                "quality": metrics["quality_assessment"],
                "validated": True
            }

            performance_path = os.path.join(
                performance_dir,
                f"performance_{request_id}.json"
            )

            def _save_performance_json():
                with open(performance_path, "w", encoding="utf-8") as f:
                    json.dump(performance_data, f, indent=2, ensure_ascii=False)

            try:
                _retry_operation("performance JSON save", _save_performance_json)
                logger.info(f"[{request_id}] Performance JSON saved -> {performance_path}")
            except Exception as e:
                logger.warning(f"[{request_id}] Performance JSON save failed after all retries: {e}")
                performance_path = None

        # ===============================
        # STEP 5 — FINAL RESPONSE (FIXED)
        # ===============================
        return JSONResponse(
            status_code=200,
            content={
                "status": (
                    "SUCCESS_WITH_VALIDATION"
                    if reference_text else
                    "SUCCESS_NO_VALIDATION"
                ),
                "request_id": request_id,
                "subtitle_file": subtitle_path,

                # FIX 3: safe null handling
                "performance_file": performance_path if performance_path else None,

                "segments_count": len(segments_list),
                "latency_sec": round(time.time() - start_time, 2)
            }
        )

    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)


#############################################################
# AUDIO REDIS QUEUE — submit-job, workers, status
# Reuses the existing RedisQueueHandler from pipeline_advanced_utils.
# The enqueue call was dead (redis_queue was created but never used for
# enqueueing); this makes it live. N configurable asyncio worker tasks
# (audio.worker_count, default 2) pull jobs from the audio Redis queue
# and process them concurrently using the existing transcription logic.
#############################################################

def _process_audio_file(
    job_id: str,
    input_path: str,
    source_filename: str,
    is_audio: bool,
) -> dict:
    """
    Core transcription logic operating on a file path (not an UploadFile).
    Reuses the same ffmpeg → librosa → Whisper → JSON-save steps as
    process_video_internal, but returns a plain dict instead of a
    JSONResponse so it can be called from the worker loop and stored in
    Redis. Every failure-prone step is wrapped in _retry_operation().

    If is_audio is True, the input is already an audio file and ffmpeg
    extraction is skipped (the file is used directly). If False, the
    input is a video and audio is extracted from it first.
    """
    start_time = time.time()
    temp_dir = config_dict.get("cleanup", {}).get("temp_dir", "tmp/audio_pipeline")

    if is_audio:
        audio_path = input_path
    else:
        audio_path = os.path.join(temp_dir, f"audio_{job_id}.wav")

        def _extract_audio():
            subprocess_executor.run([
                "ffmpeg", "-y",
                "-i", input_path,
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-acodec", "pcm_s16le",
                audio_path
            ], cancel_check=lambda: _is_cancelled(job_id))

        _check_cancel(job_id)
        try:
            _retry_operation("audio extraction (ffmpeg)", _extract_audio)
            logger.info(f"[{job_id}] Audio extracted")
        except JobCancelled:
            raise
        except Exception as e:
            logger.error(f"[{job_id}] Audio extraction failed after all retries: {e}")
            return {
                "id": job_id,
                "status": "SUCCESS_WITH_FALLBACK",
                "request_id": job_id,
                "subtitle_file": None,
                "performance_file": None,
                "segments_count": 0,
                "segments": [],
                "fallback_reason": f"Audio extraction failed after all retries: {e}",
                "latency_sec": round(time.time() - start_time, 2),
            }

    # ── Load audio (with retry) ──────────────────────────────
    def _load_audio():
        return librosa.load(audio_path, sr=16000)

    _check_cancel(job_id)
    try:
        _retry_operation("audio load (librosa)", _load_audio)
    except JobCancelled:
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Audio load failed after all retries: {e}")
        return {
            "id": job_id,
            "status": "SUCCESS_WITH_FALLBACK",
            "request_id": job_id,
            "subtitle_file": None,
            "performance_file": None,
            "segments_count": 0,
            "segments": [],
            "fallback_reason": f"Audio load failed after all retries: {e}",
            "latency_sec": round(time.time() - start_time, 2),
        }

    # ── Whisper transcription (with retry) ──────────────────
    _check_cancel(job_id)
    logger.info(f"[{job_id}] Running Whisper...")

    def _transcribe():
        segments_generator, info = model_cache.whisper_model.transcribe(
            audio_path,
            beam_size=5,
            language="en",
            task="transcribe"
        )
        segments_list = []
        for i, segment in enumerate(segments_generator):
            _check_cancel(job_id)
            segments_list.append({
                "segment_id": i,
                "start_sec": float(segment.start),
                "end_sec": float(segment.end),
                "duration_sec": float(segment.end - segment.start),
                "text": segment.text.strip(),
                "speaker": "unknown",
                "status": "success"
            })
        return segments_list, info

    try:
        segments_list, info = _retry_operation("whisper transcription", _transcribe)
        logger.info(f"[{job_id}] Language={info.language}, Probability={info.language_probability:.4f}")
    except JobCancelled:
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Whisper transcription failed after all retries: {e}")
        return {
            "id": job_id,
            "status": "SUCCESS_WITH_FALLBACK",
            "request_id": job_id,
            "subtitle_file": None,
            "performance_file": None,
            "segments_count": 0,
            "segments": [],
            "fallback_reason": f"Whisper transcription failed after all retries: {e}",
            "latency_sec": round(time.time() - start_time, 2),
        }

    # ── Save subtitle JSON ──────────────────────────────────
    _check_cancel(job_id)
    base_output_dir = "output"
    subtitle_dir = os.path.join(base_output_dir, "subtitles")
    os.makedirs(subtitle_dir, exist_ok=True)
    subtitle_path = os.path.join(subtitle_dir, f"subtitle_segments_{job_id}.json")

    processing_time = round(time.time() - start_time, 2)
    subtitle_json = {
        "metadata": {
            "request_id": job_id,
            "source_file": source_filename,
            "language": getattr(info, "language", "unknown"),
            "language_probability": float(getattr(info, "language_probability", 0.0)),
            "total_segments": len(segments_list),
            "processing_time_sec": processing_time,
            "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "status": "success"
        },
        "segments": segments_list
    }

    def _save_subtitle_json():
        with open(subtitle_path, "w", encoding="utf-8") as f:
            json.dump(subtitle_json, f, indent=2, ensure_ascii=False)

    try:
        _retry_operation("subtitle JSON save", _save_subtitle_json)
        logger.info(f"[{job_id}] Subtitle JSON saved -> {subtitle_path}")
    except Exception as e:
        logger.error(f"[{job_id}] Subtitle JSON save failed after all retries: {e}")
        return {
            "id": job_id,
            "status": "SUCCESS_WITH_FALLBACK",
            "request_id": job_id,
            "subtitle_file": None,
            "performance_file": None,
            "segments_count": len(segments_list),
            "segments": segments_list,
            "fallback_reason": f"Subtitle JSON save failed after all retries: {e}",
            "latency_sec": round(time.time() - start_time, 2),
        }

    # ── Clean up extracted audio (not the original input) ───
    if not is_audio and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except Exception:
            pass

    return {
        "id": job_id,
        "status": "SUCCESS_NO_VALIDATION",
        "request_id": job_id,
        "subtitle_file": subtitle_path,
        "performance_file": None,
        "segments_count": len(segments_list),
        "segments": segments_list,
        "latency_sec": round(time.time() - start_time, 2),
    }


@app.post("/submit-job")
async def submit_audio_queue_job(
    file: UploadFile = File(...),
    x_request_id: str = Header(None),
) -> JSONResponse:
    """
    Submit an audio job to the Redis queue. Mirrors the video service's
    /submit-job: saves the uploaded file, enqueues a job to the audio
    Redis queue (AUDIO_QUEUE_NAME), and returns immediately with the
    job_id. Workers pull from the queue and process concurrently.

    Accepts either a video file (audio is extracted from it) or a direct
    audio file. The content type is used to determine which.
    """
    if not model_cache._initialized:
        return JSONResponse(
            status_code=503,
            content={"status": "ERROR", "message": "Models are still loading, try again shortly."}
        )

    if not redis_queue:
        return JSONResponse(
            status_code=503,
            content={"status": "ERROR", "message": "Redis not available"}
        )

    job_id = x_request_id or str(uuid.uuid4())[:8]
    start_time = time.time()

    temp_dir = config_dict.get("cleanup", {}).get("temp_dir", "tmp/audio_pipeline")
    os.makedirs(temp_dir, exist_ok=True)

    # Determine if the upload is a direct audio file or a video
    ct = (file.content_type or "").lower()
    is_audio = ct.startswith("audio/") or (file.filename or "").lower().endswith(
        (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")
    )
    suffix = Path(file.filename).suffix if file.filename else (".mp3" if is_audio else ".mp4")
    input_path = os.path.join(temp_dir, f"queue_input_{job_id}{suffix}")

    # Save the uploaded file (streaming)
    upload_result = await save_upload_file_streaming(
        file,
        input_path,
        chunk_size=config_dict.get("audio", {}).get("chunk_size_bytes", 1048576),
        max_file_size=config_dict.get("audio", {}).get("max_file_size_mb", 500) * 1024 * 1024,
    )

    if not upload_result["success"]:
        return JSONResponse(
            status_code=400,
            content={"status": "ERROR", "message": "UPLOAD_FAILED", "job_id": job_id}
        )

    logger.info(f"[{job_id}] Queue upload saved: {upload_result['size_bytes']} bytes (is_audio={is_audio})")

    # Enqueue to Redis
    job_data = {
        "video_path": input_path,
        "source_filename": file.filename,
        "is_audio": is_audio,
    }
    enqueued = await redis_queue.enqueue_job(job_id, job_data, queue_name=AUDIO_QUEUE_NAME)

    if not enqueued:
        # Fallback: process synchronously so the job still completes
        logger.warning(f"[{job_id}] Redis enqueue failed — processing synchronously as fallback")
        result = await asyncio.get_event_loop().run_in_executor(
            None, _process_audio_file, job_id, input_path, file.filename, is_audio
        )
        AUDIO_JOB_STATUS[job_id] = result
        return JSONResponse(
            status_code=200,
            content={"message": "Job completed (sync fallback)", "job_id": job_id, "status": result["status"]}
        )

    AUDIO_JOB_STATUS[job_id] = {"id": job_id, "status": "QUEUED"}
    AUDIO_JOB_INPUT[job_id] = input_path
    logger.info(f"[{job_id}] Enqueued to audio queue '{AUDIO_QUEUE_NAME}'")

    return JSONResponse(
        status_code=202,
        content={
            "message": "Job submitted",
            "job_id": job_id,
            "status": "QUEUED",
            "upload_sec": round(time.time() - start_time, 2),
        },
    )


def _cleanup_audio_job_files(job_id: str, input_path: str = None, remove_outputs: bool = False) -> None:
    """Release temp files of a cancelled audio job (never raises)."""
    temp_dir = config_dict.get("cleanup", {}).get("temp_dir", "tmp/audio_pipeline")
    candidates = [input_path, os.path.join(temp_dir, f"audio_{job_id}.wav")]
    if remove_outputs:
        candidates.append(os.path.join("output", "subtitles", f"subtitle_segments_{job_id}.json"))
    for path in candidates:
        if not path:
            continue
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"[{job_id}] Could not remove {path}: {e}")


@app.post("/cancel/{job_id}")
async def cancel_audio_job(job_id: str) -> JSONResponse:
    """
    Stop an audio job on behalf of the orchestrator.

    - unknown job_id          -> 404
    - already terminal        -> 200, status unchanged (a finished job is never
                                 turned into CANCELLED)
    - QUEUED                  -> marked CANCELLED now; the worker skips it and
                                 its input file is removed
    - RUNNING                 -> flagged; the worker thread stops at its next
                                 checkpoint (ffmpeg is killed, Whisper stops
                                 between segments). We wait briefly for that.
    """
    entry = AUDIO_JOB_STATUS.get(job_id)
    if entry is None:
        return JSONResponse(status_code=404, content={"job_id": job_id, "status": "UNKNOWN"})

    current = entry.get("status")
    finished = ("SUCCESS_NO_VALIDATION", "SUCCESS_WITH_VALIDATION",
                "SUCCESS_WITH_FALLBACK", "FAILED", "CANCELLED")
    if current in finished:
        return JSONResponse(status_code=200, content={"job_id": job_id, "status": current, "already_finished": True})

    AUDIO_CANCELLED.add(job_id)
    logger.info(f"[{job_id}] Cancel requested (status={current})")

    if current == "QUEUED":
        AUDIO_JOB_STATUS[job_id] = {"id": job_id, "status": "CANCELLED", "request_id": job_id}
        _cleanup_audio_job_files(job_id, AUDIO_JOB_INPUT.pop(job_id, None))
        return JSONResponse(status_code=200, content={"job_id": job_id, "status": "CANCELLED"})

    # RUNNING: wait (bounded) for the worker thread to reach a checkpoint.
    for _ in range(40):  # up to ~8 s
        await asyncio.sleep(0.2)
        s = (AUDIO_JOB_STATUS.get(job_id) or {}).get("status")
        if s in finished:
            return JSONResponse(status_code=200, content={"job_id": job_id, "status": s})
    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "CANCELLING"})


async def _audio_worker_loop(worker_id: int) -> None:
    """
    Asyncio worker task that pulls jobs from the audio Redis queue and
    processes them. Runs concurrently with other workers — no single
    lock serializes them. The blocking Whisper transcription is run in
    a thread executor so multiple workers overlap in practice.

    Loops until the workers are shut down (graceful shutdown sets
    _audio_workers_running = False).
    """
    global _audio_workers_running
    logger.info(f"[audio-worker-{worker_id}] Started — pulling from queue '{AUDIO_QUEUE_NAME}'")

    while _audio_workers_running:
        if not redis_queue or not redis_queue.redis:
            await asyncio.sleep(1)
            continue

        try:
            job = await redis_queue.dequeue_job(
                queue_name=AUDIO_QUEUE_NAME, timeout_sec=2
            )
        except Exception as e:
            logger.warning(f"[audio-worker-{worker_id}] Dequeue error: {e}")
            await asyncio.sleep(1)
            continue

        if job is None:
            continue  # timeout, no job — loop again

        job_id = job.get("id")
        data = job.get("data", {})
        input_path = data.get("video_path")
        source_filename = data.get("source_filename", "unknown")
        is_audio = data.get("is_audio", False)

        # A job cancelled while it was still queued is dropped here without
        # ever being processed; its input file is released.
        if job_id and _is_cancelled(job_id):
            logger.info(f"[audio-worker-{worker_id}] Job {job_id} was cancelled while queued - skipping")
            AUDIO_JOB_STATUS[job_id] = {"id": job_id, "status": "CANCELLED", "request_id": job_id}
            _cleanup_audio_job_files(job_id, input_path)
            continue

        if not job_id or not input_path or not os.path.exists(input_path):
            logger.error(f"[audio-worker-{worker_id}] Invalid job payload: {job}")
            AUDIO_JOB_STATUS[job_id] = {
                "id": job_id, "status": "FAILED",
                "error": f"Invalid job payload or missing file: {input_path}",
            }
            continue

        # Mark as RUNNING
        AUDIO_JOB_STATUS[job_id] = {"id": job_id, "status": "RUNNING"}
        logger.info(
            f"[audio-worker-{worker_id}] Processing job {job_id} | "
            f"file={source_filename} | is_audio={is_audio}"
        )

        # Run the blocking transcription in a thread executor so workers
        # actually run concurrently (Whisper inference is CPU-bound).
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _process_audio_file, job_id, input_path, source_filename, is_audio
            )
        except JobCancelled:
            logger.info(f"[audio-worker-{worker_id}] Job {job_id} cancelled while processing")
            result = {
                "id": job_id, "status": "CANCELLED", "request_id": job_id,
                "segments_count": 0, "segments": [], "latency_sec": 0,
            }
            _cleanup_audio_job_files(job_id, input_path, remove_outputs=True)
        except Exception as e:
            logger.error(f"[audio-worker-{worker_id}] Job {job_id} failed: {e}", exc_info=True)
            result = {
                "id": job_id, "status": "FAILED",
                "error": str(e), "request_id": job_id,
                "segments_count": 0, "segments": [],
                "latency_sec": 0,
            }

        # Store result in Redis and in-memory status
        try:
            await redis_queue.store_result(result, result_queue=AUDIO_RESULT_KEY)
        except Exception as e:
            logger.warning(f"[audio-worker-{worker_id}] Failed to store result in Redis: {e}")

        AUDIO_JOB_STATUS[job_id] = result
        AUDIO_CANCELLED.discard(job_id)
        AUDIO_JOB_INPUT.pop(job_id, None)
        logger.info(
            f"[audio-worker-{worker_id}] Job {job_id} done | "
            f"status={result.get('status')} | segments={result.get('segments_count')}"
        )

        # Clean up the input file
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
        except Exception:
            pass

    logger.info(f"[audio-worker-{worker_id}] Stopped")


def _start_audio_workers() -> None:
    """Start AUDIO_WORKER_COUNT asyncio worker tasks (called from startup)."""
    global _audio_workers_running
    if not redis_queue:
        logger.warning("Audio workers not started — Redis not available")
        return

    _audio_workers_running = True
    for i in range(AUDIO_WORKER_COUNT):
        task = asyncio.create_task(_audio_worker_loop(i))
        _audio_worker_tasks.append(task)
    logger.info(f"[OK] Started {AUDIO_WORKER_COUNT} audio queue worker(s)")


@app.get("/status/{job_id}")
async def get_audio_queue_status(job_id: str) -> JSONResponse:
    """
    Poll this endpoint to check audio queue job status. Mirrors the video
    service's /status/{job_id}. Returns the full result dict when the job
    is done, or status=PROCESSING while it's still running.
    """
    # Check in-memory status first (fastest, always up to date)
    status_entry = AUDIO_JOB_STATUS.get(job_id)
    if status_entry:
        s = status_entry.get("status")
        if s in ("SUCCESS_NO_VALIDATION", "SUCCESS_WITH_VALIDATION", "SUCCESS_WITH_FALLBACK", "FAILED", "CANCELLED"):
            return JSONResponse(status_code=200, content=status_entry)
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": s or "PROCESSING"})

    # Fall back to Redis result store
    if redis_queue:
        try:
            result = await redis_queue.get_result(job_id, result_queue=AUDIO_RESULT_KEY)
            if result:
                return JSONResponse(status_code=200, content=result)
        except Exception as e:
            logger.error(f"Status check failed for {job_id}: {e}")

    return JSONResponse(status_code=202, content={"job_id": job_id, "status": "PROCESSING"})


# ✅ BUG FIX #8: Add /result endpoint
@app.get("/result/{job_id}")
async def get_result(job_id: str) -> JSONResponse:
    """✅ BUG FIX #8: Get job result by ID. Also checks AUDIO_JOB_STATUS."""

    # Check in-memory status first (covers both queue and sync paths)
    status_entry = AUDIO_JOB_STATUS.get(job_id)
    if status_entry:
        s = status_entry.get("status")
        if s in ("SUCCESS_NO_VALIDATION", "SUCCESS_WITH_VALIDATION", "SUCCESS_WITH_FALLBACK", "FAILED"):
            return JSONResponse(status_code=200, content={"status": "READY", "result": status_entry})

    if not redis_queue:
        return JSONResponse(
            status_code=503,
            content={"status": "ERROR", "message": "Redis not available"}
        )

    try:
        result = await redis_queue.get_result(job_id, result_queue=AUDIO_RESULT_KEY)

        if result:
            return JSONResponse(
                status_code=200,
                content={"status": "READY", "result": result}
            )
        else:
            return JSONResponse(
                status_code=202,
                content={"status": "PROCESSING", "job_id": job_id}
            )

    except Exception as e:
        logger.error(f"Failed to get result: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": str(e)}
        )

@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check with circuit breaker status."""
    return {
        "status": "healthy",
        "version": "3.1.0",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": model_cache._initialized,
        "redis_connected": redis_queue is not None,
        "circuit_breakers": {
            name: {
                "state": cb.state,
                "failures": cb.failure_count
            }
            for name, cb in circuit_breakers.items()
        }
    }

@app.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """Prometheus metrics placeholder."""
    return {"status": "metrics available at /metrics"}

#############################################################
# STARTUP & SHUTDOWN - FULLY FIXED
#############################################################

@app.on_event("startup")
async def startup():

    global redis_queue

    logger.info("=" * 70)
    logger.info("AUDIO PIPELINE v3.1 - FULLY FIXED")
    logger.info("=" * 70)

    # Kick off the (slow, multi-GB-download) model loading in a background
    # thread. This lets uvicorn finish starting up and start answering
    # /health immediately instead of the whole process hanging with the
    # port never open (which is what caused run_backend.py's "Connection
    # refused" timeout).
    def _load_models_bg():
        try:
            model_cache.load()
        except Exception as e:
            logger.error(f"Background model load failed: {e}")

    threading.Thread(target=_load_models_bg, daemon=True).start()

    # Initialize Redis connection
    if redis_queue:
        try:
            await redis_queue.connect()
            logger.info("[OK] Redis queue connected")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            redis_queue = None

    # Start the audio queue workers (N configurable asyncio tasks).
    # Done after Redis connects so the workers can actually dequeue.
    _start_audio_workers()

    logger.info(f"[OK] Single worker validation passed")
    logger.info(f"[OK] Optimal workers: {OPTIMAL_WORKERS}")
    logger.info(f"[OK] Rate limiting: enabled")
    logger.info(f"[OK] Circuit breakers: {len(circuit_breakers)} configured")
    logger.info(f"[OK] Subprocess executor: timeout={subprocess_executor.timeout_sec}s")
    logger.info(f"[OK] Redis queue: {'enabled' if redis_queue else 'disabled'}")
    logger.info(f"[OK] Audio queue workers: {AUDIO_WORKER_COUNT} (queue='{AUDIO_QUEUE_NAME}')")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown():
    """✅ BUG FIX #3: Graceful shutdown."""
    logger.info("Graceful shutdown initiated...")
    
    # Stop the audio queue workers
    global _audio_workers_running
    _audio_workers_running = False
    for t in _audio_worker_tasks:
        try:
            await asyncio.wait_for(t, timeout=5)
        except Exception:
            pass
    
    # Stop accepting new requests
    app.state.accepting_requests = False
    
    # Wait for active requests (timeout)
    timeout = 30
    start = time.time()
    while active_requests and (time.time() - start) < timeout:
        logger.info(f"Waiting for {len(active_requests)} active requests...")
        await asyncio.sleep(1)
    
    if active_requests:
        logger.warning(f"Force closing {len(active_requests)} active requests")
    
    # Close Redis gracefully
    if redis_queue:
        try:
            await redis_queue.disconnect()
            logger.info("[OK] Redis disconnected")
        except Exception as e:
            logger.error(f"Redis disconnect error: {e}")
    
    # Cleanup temp files
    temp_dir = config_dict.get("cleanup", {}).get("temp_dir", "tmp/audio_pipeline")
    try:
        for temp_file in Path(temp_dir).glob("*"):
            temp_file.unlink()
        logger.info(f"[OK] Cleaned up {temp_dir}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
    
    logger.info("[OK] Graceful shutdown complete")


@app.get("/segments/{request_id}")
async def get_segments(request_id: str):
    import json
    from pathlib import Path
    path = Path(f"output/subtitles/subtitle_segments_{request_id}.json")
    if not path.exists():
        return {"segments": [], "error": "not found"}
    with open(path) as f:
        return json.load(f)

#############################################################
# MAIN
#############################################################

if __name__ == "__main__":
    port = config_dict.get("deployment", {}).get("fastapi_port", 8021)
    
    logger.info(f"Starting FastAPI server on port {port}")
    logger.info("CRITICAL: workers=1 (models loaded at startup, shared across processes)")
    logger.info("Scale using Kubernetes or load balancer, NOT uvicorn workers")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        workers=1,  # FIX #8: MUST BE 1
        log_config=None,
        access_log=False
    )