###############################################################
# VIDEO SERVICE — APP
# FastAPI server: upload video → Redis queue → JSON result
# Mirrors audio service API shape exactly
###############################################################

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import uvicorn

# Load repo-root .env (if present) when this service is started directly
# rather than via run_backend.py, which already loads it once for all
# subprocesses.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

from model import load_model, is_model_ready, get_load_error
from frames import extract_frames, list_frame_files
from prompts import build_messages
from summary import semantic_similarity, generate_summary, SEMANTIC_DUPLICATE_THRESHOLD
from model import run_inference, MAX_NEW_TOKENS_ACTION

###############################################################
# CONFIG
###############################################################

# PORTABLE PATH: works unchanged on Colab, Kaggle, or a local machine.
# Resolution order:
#   1. VIDEO_CONFIG or CONFIG_PATH environment variable, if set
#   2. <repo>/AudioVideoPipeline/Configuration/config.yaml, derived from
#      this file's own location (app.py lives in .../video_service/)
_DEFAULT_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent / "Configuration" / "config.yaml"
)
CONFIG_PATH = os.environ.get("VIDEO_CONFIG") or os.environ.get("CONFIG_PATH") or _DEFAULT_CONFIG_PATH


def load_config(path: str = CONFIG_PATH) -> dict:
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        return {
            "redis": {
                "host":       "localhost",
                "port":       6379,
                "db":         0,
                "enabled":    True,
                "queue_name": "video_jobs",
            },
            "deployment": {
                "fastapi_port": 8022,
                "workers":      1,
            },
            "pipeline": {
                "window_step": 1,
            },
            "logging": {
                "level": "INFO",
                "dir":   "logs",
            },
            "cleanup": {
                "temp_dir": "tmp/video_pipeline",
            },
        }


config = load_config()

###############################################################
# LOGGING
###############################################################

# Shared log file: audio_service, video_service, and orchestrator all
# append to this ONE file (in addition to each still printing to its own
# console/stdout, which is what run_backend.py separately captures into
# the root-level video_service.log / audio_service.log / orchestrator.log
# files). This makes AudioVideoPipeline/Orchestrator/logs/orchestrator.log
# a single combined, interleaved-by-real-time view across all 3 services.
SHARED_LOG_PATH = Path(__file__).resolve().parent.parent / "Orchestrator" / "logs" / "orchestrator.log"
SHARED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=config.get("logging", {}).get("level", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(SHARED_LOG_PATH),
    ],
)
logger = logging.getLogger("VideoService")

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

###############################################################
# REDIS QUEUE HANDLER
###############################################################

import redis.asyncio as aioredis

redis_client = None
_results_store: dict = {}

async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        raise RuntimeError("Redis not connected")
    return redis_client


###############################################################
# FASTAPI APP
###############################################################

app = FastAPI(title="Video Pipeline Service", version="1.0.0")

active_requests: set = set()

# Live asyncio.Task per video job, so POST /cancel/{job_id} can really stop
# the frame-inference loop instead of only flagging it.
JOB_TASKS: dict = {}

###############################################################
# PIPELINE CORE
###############################################################

WINDOW_STEP = config.get("pipeline", {}).get("window_step", 1)
TEMP_DIR = Path(config.get("video_cleanup", {}).get("temp_dir", "tmp/video_pipeline"))


async def run_pipeline(job_id: str, video_path: str) -> dict:
    """
    Full frame-extraction → per-frame inference → dedup → summary pipeline.
    Returns the final result dict.
    """
    frames_dir = TEMP_DIR / job_id / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    logger.info(f"[{job_id}] Pipeline started: {video_path}")

    # ── 1. Extract frames ──────────────────────────────────────
    meta = await asyncio.get_event_loop().run_in_executor(
        None, extract_frames, video_path, str(frames_dir)
    )

    frame_files = list_frame_files(str(frames_dir))
    n_frames    = len(frame_files)
    anchor_indices = list(range(0, n_frames, WINDOW_STEP))

    logger.info(f"[{job_id}] {n_frames} frames | {len(anchor_indices)} anchors")
    logger.debug(f"[{job_id}] Frame extraction metadata: {meta}")
    logger.debug(f"[{job_id}] Anchor indices: {anchor_indices}")

    # ── 2. Per-frame inference + semantic deduplication ────────
    all_records: list = []
    errors            = 0
    last_action       = ""

    for anchor_idx in anchor_indices:
        anchor_path = frame_files[anchor_idx]

        try:
            messages, window_idxs = build_messages(anchor_idx, frame_files, n_frames)
            window_paths          = [frame_files[i] for i in window_idxs]

            raw_output   = await asyncio.get_event_loop().run_in_executor(
                None, run_inference, messages, MAX_NEW_TOKENS_ACTION
            )
            final_action = raw_output.strip()

            logger.info(f"[{job_id}] Anchor {anchor_idx:04d} → {final_action}")
            logger.debug(f"[{job_id}] Anchor {anchor_idx:04d} | window={window_idxs} | "
                         f"raw_output={raw_output!r}")

            if last_action:
                sem = await asyncio.get_event_loop().run_in_executor(
                    None, semantic_similarity, final_action, last_action
                )
                sim          = sem["semantic_score"]
                is_duplicate = sem["is_duplicate"]
                sem_reason   = sem["reason"]
                sem_method   = sem["method"]
            else:
                sim, is_duplicate = 0.0, False
                sem_reason        = "First action — no previous to compare."
                sem_method        = "semantic_model"

            if not is_duplicate:
                last_action = final_action

            logger.debug(f"[{job_id}] Anchor {anchor_idx:04d} | semantic_score={sim:.3f} | "
                         f"is_duplicate={is_duplicate} | reason={sem_reason!r} | method={sem_method}")

            record = {
                "anchor_frame_index":   anchor_idx,
                "anchor_frame_file":    anchor_path.name,
                "anchor_image_path":    str(anchor_path.resolve()),
                "timestamp_sec":        round(anchor_idx * 1.0, 2),
                "window_frame_indices": window_idxs,
                "window_frame_files":   [f.name for f in window_paths],
                "raw_model_output":     raw_output,
                "final_action":         final_action,
                "is_duplicate":         is_duplicate,
                "semantic_score":       round(sim, 3),
                "semantic_reason":      sem_reason,
                "semantic_method":      sem_method,
                "status":               "success",
            }

        except Exception as e:
            logger.error(f"[{job_id}] Error on anchor {anchor_idx}: {e}", exc_info=True)
            record = {
                "anchor_frame_index":   anchor_idx,
                "anchor_frame_file":    anchor_path.name,
                "anchor_image_path":    str(anchor_path.resolve()),
                "timestamp_sec":        round(anchor_idx * 1.0, 2),
                "window_frame_indices": [],
                "window_frame_files":   [],
                "raw_model_output":     None,
                "final_action":         None,
                "is_duplicate":         False,
                "semantic_score":       0.0,
                "semantic_reason":      None,
                "semantic_method":      None,
                "status":               "error",
                "error":                str(e),
            }
            errors += 1

        all_records.append(record)

    # ── 3. Generate consolidated timeline ─────────────────────
    unique_records = [
        r for r in all_records
        if not r.get("is_duplicate") and r["status"] == "success"
    ]

    timeline: list = []
    try:
        timeline = await asyncio.get_event_loop().run_in_executor(
            None, generate_summary, unique_records
        )
    except Exception as e:
        logger.error(f"[{job_id}] Summary failed: {e}", exc_info=True)

    # ── 4. Build result ────────────────────────────────────────
    result = {
        "id":     job_id,
        "status": "READY",
        "result": {
            "metadata": {
                "video":                  video_path,
                "total_frames":           meta["total_frames"],
                "fps":                    meta["fps"],
                "duration_sec":           meta["duration_sec"],
                "anchors_processed":      len(anchor_indices),
                "unique_actions":         len(unique_records),
                "duplicates_skipped":     len(anchor_indices) - len(unique_records) - errors,
                "errors":                 errors,
                "window_step":            WINDOW_STEP,
                "semantic_threshold":     SEMANTIC_DUPLICATE_THRESHOLD,
            },
            "consolidated_timeline": timeline,
            "frame_records":         all_records,
        },
        "processed_at": time.time(),
        "latency_sec":  round(time.time() - start_time, 2),
    }

    logger.info(
        f"[{job_id}] Pipeline done | "
        f"unique={len(unique_records)} | errors={errors} | "
        f"latency={result['latency_sec']}s"
    )
    return result


async def process_and_store(job_id: str, video_path: str) -> None:
    """Background task: run pipeline then push result to Redis."""
    try:
        try:
            result = await run_pipeline(job_id, video_path)
        except Exception as e:
            logger.error(f"[{job_id}] Pipeline fatal error: {e}", exc_info=True)
            result = {
                "id": job_id,
                "status": "FAILED",
                "error": str(e),
                "processed_at": time.time(),
            }

        # Record the final result in memory BEFORE the Redis push (which is
        # an await point where a cancel could land), so a job that already
        # finished is never turned into CANCELLED by a late cancel request.
        _results_store[job_id] = result

        try:
            r = await get_redis()
            await r.rpush("video_results", json.dumps(result))
            logger.info(f"[{job_id}] Result stored in Redis")
        except Exception as e:
            logger.error(f"[{job_id}] Failed to store result in Redis: {e}")

    except asyncio.CancelledError:
        # POST /cancel/{job_id}: stop immediately. If the pipeline had
        # already finished, keep that result instead of overwriting it.
        existing = _results_store.get(job_id) or {}
        if existing.get("status") in (None, "PROCESSING"):
            _results_store[job_id] = {
                "id": job_id,
                "status": "CANCELLED",
                "processed_at": time.time(),
            }
            logger.info(f"[{job_id}] Video job cancelled by user request")
            # Release the extracted frames / temp folder for this job.
            shutil.rmtree(TEMP_DIR / job_id, ignore_errors=True)
        raise

    finally:
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass

###############################################################
# ROUTES
###############################################################

@app.post("/submit-job")
async def submit_job(video: UploadFile = File(...)) -> JSONResponse:
    job_id     = str(uuid.uuid4())
    start_time = time.time()

    temp_video_dir = TEMP_DIR / job_id
    temp_video_dir.mkdir(parents=True, exist_ok=True)

    suffix     = Path(video.filename).suffix or ".mp4"
    video_path = str(temp_video_dir / f"video_{job_id}{suffix}")

    try:
        chunk_size = 1_048_576
        total_size = 0
        max_size   = 500 * 1024 * 1024

        with open(video_path, "wb") as f:
            while True:
                chunk = await video.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size:
                    raise HTTPException(status_code=413, detail="Video file exceeds 500 MB limit")
                f.write(chunk)

        logger.info(f"[{job_id}] Upload saved: {total_size / (1024 * 1024):.1f} MB")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Upload failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": str(e), "job_id": job_id},
        )

    try:
        r = await get_redis()
        job_payload = json.dumps({
            "id":        job_id,
            "data":      {"video_path": video_path},
            "timestamp": datetime.now().isoformat(),
            "status":    "QUEUED",
        })
        await r.lpush(config["redis"]["queue_name"], job_payload)
    except Exception as e:
        logger.warning(f"[{job_id}] Redis enqueue failed (processing anyway): {e}")

    _results_store[job_id] = {"id": job_id, "status": "PROCESSING"}
    task = asyncio.create_task(process_and_store(job_id, video_path))
    JOB_TASKS[job_id] = task
    task.add_done_callback(lambda _t, _jid=job_id: JOB_TASKS.pop(_jid, None))

    return JSONResponse(
        status_code=202,
        content={
            "message":    "Job submitted",
            "job_id":     job_id,
            "status":     "QUEUED",
            "upload_sec": round(time.time() - start_time, 2),
        },
    )


@app.get("/frames/{job_id}/{filename}")
async def get_frame(job_id: str, filename: str):
    """
    Serve a frame image by job_id and filename.
    Orchestrator calls this to fetch frames for Word doc embedding.
    """
    frame_path = TEMP_DIR / job_id / "frames" / filename
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail=f"Frame not found: {filename}")
    return FileResponse(str(frame_path), media_type="image/jpeg")


@app.get("/status/{job_id}")
async def get_status(job_id: str) -> JSONResponse:
    cached = _results_store.get(job_id)
    if cached and cached.get("status") != "PROCESSING":
        return JSONResponse(status_code=200, content=cached)
    try:
        if redis_client is None:
            return JSONResponse(status_code=202, content={"job_id": job_id, "status": "PROCESSING"})

        r = redis_client
        results = await r.lrange("video_results", 0, -1)

        for item in results:
            job = json.loads(item)
            if job.get("id") == job_id:
                return JSONResponse(status_code=200, content=job)

        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "PROCESSING"})

    except Exception as e:
        logger.error(f"Status check failed for {job_id}: {e}")
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": str(e)})


@app.get("/result/{job_id}")
async def get_result(job_id: str) -> JSONResponse:
    return await get_status(job_id)


@app.post("/cancel/{job_id}")
async def cancel_video_job(job_id: str) -> JSONResponse:
    """
    Stop a video job on behalf of the orchestrator.

    - unknown job_id     -> 404
    - already finished   -> 200, result untouched (never changes a finished
                            job to CANCELLED)
    - PROCESSING         -> the asyncio task is cancelled, so no further frames
                            are sent to the model (a frame already inside the
                            inference thread finishes, then is discarded), and
                            the job's frames / temp folder are removed.
    """
    entry = _results_store.get(job_id)
    if entry is None:
        return JSONResponse(status_code=404, content={"job_id": job_id, "status": "UNKNOWN"})

    if entry.get("status") != "PROCESSING":
        return JSONResponse(
            status_code=200,
            content={"job_id": job_id, "status": entry.get("status"), "already_finished": True},
        )

    task = JOB_TASKS.get(job_id)
    if task is not None and not task.done():
        task.cancel()
        await asyncio.wait([task], timeout=15)

    final = (_results_store.get(job_id) or {}).get("status")
    if final == "PROCESSING":
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "CANCELLING"})
    return JSONResponse(status_code=200, content={"job_id": job_id, "status": final})


@app.get("/health")
async def health() -> dict:
    redis_ok = False
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status":    "healthy",
        "version":   "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "redis":     redis_ok,
    }


###############################################################
# STARTUP & SHUTDOWN
###############################################################

@app.on_event("startup")
async def startup() -> None:
    global redis_client

    logger.info("=" * 60)
    logger.info("VIDEO PIPELINE SERVICE v1.0 — starting")
    logger.info("=" * 60)

    try:
        load_model()
    except Exception as e:
        logger.error(f"Model load FAILED - aborting startup: {e}")
        raise RuntimeError(
            f"Video service will not start - Qwen3-VL failed to load: {e}"
        ) from e

    if not is_model_ready():
        err = get_load_error() or 'unknown model load failure'
        logger.error(f"Model load FAILED - aborting startup: {err}")
        raise RuntimeError(
            f"Video service will not start - Qwen3-VL failed to load: {err}"
        )

    logger.info('[OK] Qwen3-VL model loaded')

    redis_cfg = config.get("redis", {})
    if redis_cfg.get("enabled", True):
        try:
            redis_client = await aioredis.from_url(
                f"redis://{redis_cfg.get('host', 'localhost')}:{redis_cfg.get('port', 6379)}/{redis_cfg.get('db', 0)}",
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            await redis_client.ping()
            logger.info("[OK] Redis connected")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            redis_client = None

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"[OK] Temp dir: {TEMP_DIR}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Graceful shutdown initiated...")
    if redis_client:
        try:
            await redis_client.close()
            logger.info("[OK] Redis disconnected")
        except Exception as e:
            logger.error(f"Redis disconnect error: {e}")
    logger.info("[OK] Shutdown complete")


###############################################################
# MAIN
###############################################################

if __name__ == "__main__":
    port = config.get("video_deployment", {}).get("fastapi_port", 8022)
    logger.info(f"Starting Video Service on port {port}")
    logger.info("workers=1 — model held in process memory")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        log_config=None,
        access_log=False,
    )