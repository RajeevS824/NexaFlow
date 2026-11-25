###############################################################
# ORCHESTRATOR — CLIENT
# Low-level HTTP calls to audio service and video service
###############################################################

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import httpx
import yaml

logger = logging.getLogger("OrchestratorClient")

# ==================================================
# CONFIG
# ==================================================
import os

# PORTABLE PATH: works unchanged on Colab, Kaggle, or a local machine.
# Resolution order:
#   1. CONFIG_PATH environment variable, if set (most explicit)
#   2. <repo>/AudioVideoPipeline/Configuration/config.yaml, derived from
#      this file's own location (client.py lives in .../Orchestrator/)
_DEFAULT_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent / "Configuration" / "config.yaml"
)

def _load_config(path: str = None) -> dict:
    path = path or os.environ.get("CONFIG_PATH", _DEFAULT_CONFIG_PATH)

    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config from {path}: {e}")

        return {
            "services": {
                "audio": {"url": "http://localhost:8021", "timeout_sec": 300},
                "video": {"url": "http://localhost:8022", "timeout_sec": 600},
            },
            "orchestrator": {
                "poll_interval_sec": 3,
                "poll_timeout_sec": 60,  # safe fallback, NOT 600
            },
        }
config = _load_config()


AUDIO_URL        = config["services"]["audio"]["url"]
VIDEO_URL        = config["services"]["video"]["url"]
AUDIO_TIMEOUT    = config["services"]["audio"]["timeout_sec"]
VIDEO_TIMEOUT    = config["services"]["video"]["timeout_sec"]
POLL_INTERVAL    = config["orchestrator"]["poll_interval_sec"]
# Env var always wins, same pattern as DB_PASSWORD/OPENROUTER_API_KEY —
# lets you bump this per-machine (e.g. much higher on a slow CPU-only
# box) without editing config.yaml.
POLL_TIMEOUT     = int(os.environ.get("ORCHESTRATOR_POLL_TIMEOUT_SEC") or config["orchestrator"]["poll_timeout_sec"])

logger.info(f"CONFIG LOADED FROM: {config}")
logger.info(f"POLL_TIMEOUT = {config['orchestrator']['poll_timeout_sec']}")
# ==================================================
# AUDIO CLIENT
# ==================================================

async def submit_audio_job(video_path: str, audio_path: str = None) -> dict:
    """
    POST /process to audio service.
    If audio_path is given, sends the audio file directly (skips extraction).
    Otherwise sends the video file as before (audio service extracts audio itself).
    Returns the full JSON response (contains subtitle_file path and segments).
    """
    source_path = Path(audio_path) if audio_path else Path(video_path)
    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source_path}")

    content_type = "audio/mpeg" if audio_path else "video/mp4"
    logger.info(f"Submitting audio job: {source_path.name} (direct_audio={bool(audio_path)})")
    logger.debug(f"Audio request | url={AUDIO_URL}/process | file={source_path} | "
                 f"size_bytes={source_path.stat().st_size} | content_type={content_type}")

    async with httpx.AsyncClient(timeout=AUDIO_TIMEOUT) as client:
        with open(source_path, "rb") as f:
            response = await client.post(
                f"{AUDIO_URL}/process",
                files={"file": (source_path.name, f, content_type)},
            )

    response.raise_for_status()
    result = response.json()
    logger.info(f"Audio job done | status={result.get('status')} | segments={result.get('segments_count')}")
    logger.debug(f"Audio response payload: {result}")
    
    # Fetch full segments from audio service
    # Fetch full segments using NEW client
    request_id = result.get("request_id")
    if request_id:
        try:
            async with httpx.AsyncClient(timeout=30) as seg_client:
                seg_response = await seg_client.get(
                    f"{AUDIO_URL}/segments/{request_id}"
                )
                segments_data = seg_response.json()
                result["segments"] = segments_data.get("segments", [])
                logger.info(f"Fetched {len(result['segments'])} segments for {request_id}")
                logger.debug(f"Segments payload: {result['segments']}")
        except Exception as e:
            logger.warning(f"Could not fetch segments: {e}")
            result["segments"] = []

    return result

# ==================================================
# AUDIO QUEUE CLIENT (new — uses the audio Redis queue)
# ==================================================
# The Orchestrator talks to the audio service via HTTP (its /submit-job
# and /status/{job_id} endpoints), NOT by touching Redis directly. This
# keeps the audio service the single owner of its queue and workers, and
# means the Orchestrator needs no Redis client of its own. The audio
# service internally uses RedisQueueHandler to enqueue/dequeue.

async def submit_audio_queue_job(video_path: str, audio_path: str = None) -> str:
    """
    POST /submit-job to the audio service. Saves the file, enqueues a job
    to the audio Redis queue, and returns the job_id immediately. Workers
    in the audio service pull from the queue and process concurrently.

    If audio_path is given, sends the audio file directly (skips
    extraction). Otherwise sends the video file (audio service extracts
    audio from it). Returns the job_id string.
    """
    source_path = Path(audio_path) if audio_path else Path(video_path)
    if not source_path.exists():
        raise FileNotFoundError(f"File not found: {source_path}")

    content_type = "audio/mpeg" if audio_path else "video/mp4"
    logger.info(f"Submitting audio queue job: {source_path.name} (direct_audio={bool(audio_path)})")
    logger.debug(f"Audio queue request | url={AUDIO_URL}/submit-job | file={source_path} | "
                 f"size_bytes={source_path.stat().st_size} | content_type={content_type}")

    async def _do_submit():
        async with httpx.AsyncClient(timeout=120) as client:
            with open(source_path, "rb") as f:
                response = await client.post(
                    f"{AUDIO_URL}/submit-job",
                    files={"file": (source_path.name, f, content_type)},
                )
        response.raise_for_status()
        data = response.json()
        job_id = data["job_id"]
        logger.info(f"Audio queue job submitted | job_id={job_id}")
        logger.debug(f"Audio submit response payload: {data}")
        return job_id

    job_id = await _do_submit()
    return job_id


async def poll_audio_result(job_id: str) -> dict:
    """
    Poll GET /status/{job_id} on the audio service until the job reaches a
    terminal state (SUCCESS_NO_VALIDATION / SUCCESS_WITH_VALIDATION /
    SUCCESS_WITH_FALLBACK / FAILED) or timeout. Returns the full result
    dict. Mirrors poll_video_result's shape and timeout handling.
    """
    deadline = time.time() + POLL_TIMEOUT
    attempt = 0
    last_status = None
    terminal = ("SUCCESS_NO_VALIDATION", "SUCCESS_WITH_VALIDATION",
                "SUCCESS_WITH_FALLBACK", "FAILED", "CANCELLED")

    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            attempt += 1
            try:
                response = await client.get(f"{AUDIO_URL}/status/{job_id}")
                data = response.json()
                status = data.get("status")

                logger.debug(f"Audio poll #{attempt} | job_id={job_id} | status={status} | payload={data}")
                if status != last_status:
                    logger.info(f"Audio job {job_id} status changed: {last_status} -> {status} (poll #{attempt})")
                    last_status = status

                if status in terminal:
                    return data

            except httpx.HTTPStatusError as e:
                logger.warning(f"Audio poll HTTP error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Audio job {job_id} did not complete within {POLL_TIMEOUT}s")


# ==================================================
# VIDEO CLIENT
# ==================================================

async def submit_video_job(video_path: str) -> str:
    """
    POST /submit-job to video service.
    Returns job_id string.
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    logger.info(f"Submitting video job: {path.name}")
    logger.debug(f"Video request | url={VIDEO_URL}/submit-job | file={path} | size_bytes={path.stat().st_size}")

    async with httpx.AsyncClient(timeout=60) as client:
        with open(path, "rb") as f:
            response = await client.post(
                f"{VIDEO_URL}/submit-job",
                files={"video": (path.name, f, "video/mp4")},
            )

    response.raise_for_status()
    data   = response.json()
    job_id = data["job_id"]
    logger.info(f"Video job submitted | job_id={job_id}")
    logger.debug(f"Video submit response payload: {data}")
    return job_id


async def poll_video_result(job_id: str) -> dict:
    """
    Poll GET /status/{job_id} until status == READY or timeout.
    Returns the full result dict.
    """
    deadline = time.time() + POLL_TIMEOUT
    attempt  = 0
    last_status = None

    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            attempt += 1
            try:
                response = await client.get(f"{VIDEO_URL}/status/{job_id}")
                data     = response.json()
                status   = data.get("status")

                # Every poll at DEBUG (verbose, full payload) — but only
                # log at INFO when the status actually changes, so normal
                # operation doesn't spam the log with an identical line
                # every 3 seconds for a job that can run a long time.
                logger.debug(f"Video poll #{attempt} | job_id={job_id} | status={status} | payload={data}")
                if status != last_status:
                    logger.info(f"Video job {job_id} status changed: {last_status} -> {status} (poll #{attempt})")
                    last_status = status

                if status == "READY":
                    return data
                if status == "FAILED":
                    raise RuntimeError(f"Video job failed: {data.get('error')}")
                if status == "CANCELLED":
                    raise RuntimeError("Video job was cancelled")

            except httpx.HTTPStatusError as e:
                logger.warning(f"Poll HTTP error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Video job {job_id} did not complete within {POLL_TIMEOUT}s")


# ==================================================
# CANCELLATION (best-effort downstream stop)
# ==================================================
# The orchestrator asks the audio / video service to stop the job it
# submitted for a pipeline run. Both helpers return True when the service
# acknowledged the cancel, and never raise -- the caller records a
# warning if a service could not be reached and carries on.

async def cancel_audio_job(job_id: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{AUDIO_URL}/cancel/{job_id}")
        ok = r.status_code == 200
        logger.info(f"Audio cancel requested | job_id={job_id} | http={r.status_code}")
        return ok
    except Exception as e:
        logger.warning(f"Audio cancel request failed for {job_id}: {e}")
        return False


async def cancel_video_job(job_id: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{VIDEO_URL}/cancel/{job_id}")
        ok = r.status_code == 200
        logger.info(f"Video cancel requested | job_id={job_id} | http={r.status_code}")
        return ok
    except Exception as e:
        logger.warning(f"Video cancel request failed for {job_id}: {e}")
        return False


# ==================================================
# HEALTH CHECKS
# ==================================================

async def check_audio_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{AUDIO_URL}/health")
            return r.status_code == 200
    except Exception as e:
        logger.warning(f"Audio health check failed: {e}")
        return False


async def check_video_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{VIDEO_URL}/health")
            return r.status_code == 200
    except Exception as e:
        logger.warning(f"Video health check failed: {e}")
        return False