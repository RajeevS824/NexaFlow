###############################################################
# ORCHESTRATOR — INTEGRATED PIPELINE
# Main controller API: accepts one video → runs audio + video
# simultaneously → saves audio.json + video.json + report.docx
###############################################################

import asyncio
import logging
import os
import re
import subprocess
import threading
import time
import uuid
import random
import string
import requests
from datetime import datetime
from pathlib import Path

import yaml
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse

# Load repo-root .env (if present) when this service is started directly
# rather than via run_backend.py, which already loads it once for all
# subprocesses.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

from client import (
    submit_audio_job,
    submit_audio_queue_job,
    poll_audio_result,
    submit_video_job,
    poll_video_result,
    check_audio_health,
    check_video_health,
    cancel_audio_job,
    cancel_video_job,
)
from job_manager import (
    LLM_PROVIDER_BASE_URLS,
    fetch_provider_models,
    get_application_llm_api_key,
    make_job_name,
    save_audio_result,
    save_video_result,
    run_workflow_analysis,
    make_output_paths,
    PipelineCancelled,
)
import database  # optional durable job storage — see database.py; every
                  # call below is a safe no-op if DB_ENABLED=false
import log_exporter
from bm_auth import require_user, get_current_user_id

###############################################################
# CONFIG
###############################################################

# PORTABLE PATH: works unchanged on Colab, Kaggle, or a local machine.
# Resolution order:
#   1. CONFIG_PATH environment variable, if set (most explicit)
#   2. <repo>/AudioVideoPipeline/Configuration/config.yaml, derived from
#      this file's own location (integrated_pipeline.py lives in
#      .../Orchestrator/)
CONFIG_PATH = os.environ.get(
    "CONFIG_PATH",
    str(Path(__file__).resolve().parent.parent / "Configuration" / "config.yaml"),
)


def load_config(path: str = CONFIG_PATH) -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger_raw = logging.getLogger("OrchestratorPipeline")
        logger_raw.warning(f"Failed to load config from {path}: {e}")
        return {
            "orchestrator": {
                "fastapi_port": 8020,
                "run_audio":    True,
                "run_video":    True,
            },
            "logging": {"level": "INFO", "dir": "logs"},
            "cleanup": {"temp_dir": "tmp/orchestrator"},
        }


config = load_config()

###############################################################
# LOGGING
###############################################################

LOG_DIR = Path(config.get("logging", {}).get("dir", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=config.get("logging", {}).get("level", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "orchestrator.log"),
    ],
)
logger = logging.getLogger("OrchestratorPipeline")

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
# The orchestrator's own health check calls the audio and video services with
# httpx, which logs "HTTP Request: GET http://localhost:802x/health ... 200 OK".
logging.getLogger("httpx").addFilter(_HealthCheckLogFilter())

###############################################################
# LOG CONFIGURATION (Settings page)
###############################################################
# Separate from the fixed developer log above (logs/orchestrator.log,
# level controlled by config.yaml) — this is a SECOND, dynamically
# reconfigurable file handler whose level, destination folder, on/off
# state, and max size the user controls from the Settings page.
# Currently a single shared configuration (see DEFAULT_SETTINGS_USER_ID
# below) rather than truly per-user, since real user identification
# isn't wired up yet on this page.

from logging.handlers import RotatingFileHandler

DEFAULT_SETTINGS_USER_ID = 1  # single shared settings row, see database.UserLogSettings

class _ExactLevelFilter(logging.Filter):
    """
    Matches the spec literally: selecting "Info" stores ONLY INFO
    records (not INFO-and-above, which is Python logging's usual
    threshold behavior) — same for Error/Debug.
    """
    _LEVEL_SETS = {
        "INFO":  {"INFO"},
        "ERROR": {"ERROR"},
        "DEBUG": {"DEBUG"},
    }

    def __init__(self, level_name: str):
        super().__init__()
        self.allowed = self._LEVEL_SETS.get(level_name.upper(), {"INFO", "ERROR", "DEBUG"})

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelname in self.allowed


_active_user_log_handler = {"handler": None}

def apply_user_log_config(folder_path: str, level: str, enabled: bool = True,
                           max_size_mb: int = 50) -> dict:
    """
    (Re)attaches this process's configurable log file handler, replacing
    any previously active one. Returns
    {"folder_path": ..., "warning": str|None} — folder_path may differ
    from the requested one if it fell back to the default (e.g.
    permission denied, invalid drive).

    If enabled=False, any existing handler is removed and nothing new
    is attached — no file gets written for this config at all (the
    fixed developer log above is unaffected either way).
    """
    if _active_user_log_handler["handler"] is not None:
        logging.getLogger().removeHandler(_active_user_log_handler["handler"])
        _active_user_log_handler["handler"] = None

    if not enabled:
        logger.info("User log config applied: logging disabled — no file will be written.")
        return {"folder_path": folder_path, "warning": None}

    warning = None
    target_folder = folder_path

    try:
        os.makedirs(target_folder, exist_ok=True)
        # Confirm it's actually writable, not just creatable — makedirs
        # succeeds even for some paths a later write would fail on.
        test_file = Path(target_folder) / ".suppi_write_test"
        test_file.write_text("")
        test_file.unlink()
    except OSError as e:
        warning = (f"Could not use log folder '{folder_path}' ({e}); "
                   f"falling back to the default log folder instead.")
        logger.warning(warning)
        target_folder = database.default_log_folder()
        os.makedirs(target_folder, exist_ok=True)

    # Whatever level was picked (including DEBUG-only), the root
    # logger's own gate must allow DEBUG through, or records get dropped
    # before any handler — including this one — ever sees them. This
    # does NOT change what the fixed developer log above actually
    # writes: that handler still has its own .setLevel() from
    # config.yaml, independently narrowing what IT emits.
    logging.getLogger().setLevel(logging.DEBUG)

    handler = RotatingFileHandler(
        Path(target_folder) / "user_activity.log",
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=3,
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)s] [%(processName)s] [PID:%(process)d] "
            "[File:%(filename)s] [Function:%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    handler.addFilter(_ExactLevelFilter(level))
    logging.getLogger().addHandler(handler)
    _active_user_log_handler["handler"] = handler

    logger.info(f"User log config applied: level={level} folder={target_folder} "
                f"max_size_mb={max_size_mb}"
                + (f" (fallback from {folder_path})" if warning else ""))
    return {"folder_path": target_folder, "warning": warning}



app = FastAPI(title="Integrated Pipeline Orchestrator", version="1.0.0")
from fastapi.middleware.cors import CORSMiddleware

# CORS — allow the NexaFlow frontend origin(s). Read from the shared root
# .env's ALLOWED_ORIGINS (same variable the nexaflow-backend and
# Document-Parser-Backend read), not a hardcoded localhost.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

from fastapi.staticfiles import StaticFiles
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory="output"), name="files")

# ── Storage Used (Dashboard summary card) ──────────────────────────
# Only output/ counts toward "Storage Used" — uploaded video/audio in
# TEMP_DIR is deleted right after each job finishes (see the `finally`
# block in run_full_pipeline_bg below), so it's ephemeral scratch space,
# not something the user has accumulated. output/ holds the actual
# deliverables (reports, transcripts, generated files) and is what a
# "Storage Used" number should reflect — same idea as a cloud-storage
# quota only counting your saved files, not a temp upload buffer.
#
# Cached for a few seconds so N dashboard viewers polling every 5s don't
# each trigger a full filesystem walk on every request.
_storage_cache = {"bytes": 0, "at": 0.0}
_STORAGE_CACHE_TTL_SEC = 10

def _get_storage_used_gb() -> float:
    now = time.time()
    if now - _storage_cache["at"] > _STORAGE_CACHE_TTL_SEC:
        total = 0
        for root, _dirs, files in os.walk(OUTPUT_DIR):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass  # file deleted mid-scan — skip it, not fatal
        _storage_cache["bytes"] = total
        _storage_cache["at"] = now
    return round(_storage_cache["bytes"] / (1024 ** 3), 3)

RUN_AUDIO = config.get("orchestrator", {}).get("run_audio", True)
RUN_VIDEO = config.get("orchestrator", {}).get("run_video", True)
TEMP_DIR  = Path(config.get("cleanup", {}).get("temp_dir", "tmp/orchestrator"))

###############################################################
# PIPELINE CORE
###############################################################

async def run_full_pipeline(
    job_id: str,
    job_name: str,
    video_path: str,
    audio_path: str = None,
    username: str = "",
    recipient_email: str = "",
    progress_cb=None,                          # progress callback
    no_audio: bool = False,                    # ← ADDED: user confirmed "Continue" with no audio source
    llm_user_id: int = DEFAULT_SETTINGS_USER_ID,  # ← whose Settings -> LLM Configuration to use
) -> dict:
    """
    Run audio and video services in parallel, save outputs, run LLM analysis.

    Audio-source priority (see job_manager / frontend for the detection step):
      1. separate_audio_uploaded -> audio_path is set -> always use uploaded audio.
      2. else if video has an embedded audio track -> audio service extracts it
         from the video itself (audio_path is None, video sent to /process).
      3. else (no_audio=True) -> audio stage is skipped entirely; output is
         generated using only video frames, with a notice in the report.

    Flow:
      video_path (+ optional audio_path)
        ├─► audio service /process       (sends audio_path if given, else video_path)
        └─► video service /submit-job    (async, poll until READY)
      audio result → output/audio_json/<job_name>_audio.json
      video result → output/video_json/<job_name>_video.json
      both/video-only → output/reports/<job_name>_workflow_steps_clean.docx
                         output/reports/<job_name>_workflow_validation.docx
    If recipient_email is provided, output files are emailed to that address.

    PROGRESS PHASES (emitted via progress_cb(percent, phase)) — the frontend
    maps these phase words to fixed 20%-per-step progress bar positions:
      "validating"  — job queued, before any processing starts (set by the
                       background wrapper, see run_full_pipeline_bg)
      "audio_done"  — emitted the instant the audio service finishes,
                       independent of whatever the video service is doing
      "video_done"  — emitted the instant the video service finishes,
                       independent of whatever the audio service is doing
      "generating"  — emitted right before the LLM report-generation step
                       starts (after both audio and video are done)
    Audio and video run concurrently (asyncio.wait/FIRST_COMPLETED below),
    so whichever finishes first emits its "*_done" phase immediately rather
    than waiting for both to complete.
    """

    # ── helper to emit progress safely ─────────────────
    def _emit(p, phase):
        if progress_cb:
            progress_cb(p, phase)
    # ──────────────────────────────────────────────────────────

    start        = time.time()
    audio_result = None
    video_result = None
    errors       = []

    # ── ADDED: determine whether the audio stage should run at all ────
    # Case 3 (no separate audio + no embedded audio, user clicked Continue)
    # skips audio processing entirely — never fails the pipeline.
    run_audio_stage = RUN_AUDIO and not no_audio

    logger.info(
        f"[{job_id}] Pipeline started | job={job_name} | direct_audio={bool(audio_path)} "
        f"| no_audio={no_audio} | run_audio_stage={run_audio_stage} | email={bool(recipient_email)}"
    )

    # ── Run AUDIO and VIDEO concurrently. Audio (Whisper) is pinned to
    # CPU-only via CUDA_VISIBLE_DEVICES="" when the audio service process is
    # launched (see run_backend.py), while video (Qwen3-VL) uses the GPU
    # exclusively — the two models never touch the same accelerator, so
    # there is no VRAM contention and no reason to serialize them. Each
    # stage's "*_done" progress phase still fires independently the instant
    # that stage finishes (via asyncio.wait FIRST_COMPLETED below), same as
    # before: 30% "processing" -> "audio_done"/"video_done" as each
    # completes (order not guaranteed now that they race) -> 90% "generating".
    # A failure in one service is recorded in `errors` without cancelling or
    # waiting on the other. ─────────────────────────────────────────────────
    _emit(30, "processing")

    # ── Combined pipeline status tracking ───────────────────────
    # The audio job and video job are both registered under this same
    # pipeline job_id. pipeline_status reflects the combined state:
    #   queued -> audio_queued/video_queued -> audio_running/video_running
    #   -> partially_complete -> completed / failed
    # "completed" requires BOTH audio and video to have succeeded.
    pipeline_status = "queued"
    audio_terminal = False
    video_terminal = False

    def _update_pipeline_status():
        """Recompute the combined pipeline_status from audio/video state."""
        nonlocal pipeline_status
        a_done = audio_result is not None or (not run_audio_stage)
        v_done = video_result is not None or (not RUN_VIDEO)
        a_failed = any(e["service"] == "audio" for e in errors)
        v_failed = any(e["service"] == "video" for e in errors)
        if a_failed or v_failed:
            pipeline_status = "failed"
        elif a_done and v_done:
            pipeline_status = "completed"
        elif a_done or v_done:
            pipeline_status = "partially_complete"
        elif audio_terminal and not a_done:
            pipeline_status = "audio_running"
        elif video_terminal and not v_done:
            pipeline_status = "video_running"
        elif audio_terminal:
            pipeline_status = "audio_queued"
        elif video_terminal:
            pipeline_status = "video_queued"
        return pipeline_status

    async def _submit_tracked(kind: str, submit_coro, cancel_fn) -> str:
        """Submit a job to the audio/video service and remember the id the
        service gave us under JOB_DOWNSTREAM[job_id][kind], so a later cancel
        can stop exactly that downstream job. If this task is cancelled while
        the submission is still in flight, let the submission finish and
        cancel the job it created, so nothing is left running unowned."""
        submit = asyncio.ensure_future(submit_coro)
        try:
            downstream_id = await asyncio.shield(submit)
        except asyncio.CancelledError:
            try:
                downstream_id = await asyncio.wait_for(submit, timeout=60)
                await cancel_fn(downstream_id)
            except Exception:
                pass
            raise
        JOB_DOWNSTREAM.setdefault(job_id, {})[kind] = downstream_id
        return downstream_id

    async def _audio_flow():
        # Use the audio Redis queue: submit returns a job_id, then poll
        # until terminal. The audio service's N workers process this
        # concurrently with other audio jobs.
        audio_job_id = await _submit_tracked(
            "audio", submit_audio_queue_job(video_path, audio_path), cancel_audio_job
        )
        return await poll_audio_result(audio_job_id)

    async def _video_flow():
        vid_job_id = await _submit_tracked(
            "video", submit_video_job(video_path), cancel_video_job
        )
        return await poll_video_result(vid_job_id)

    tasks: dict = {}
    if run_audio_stage:
        tasks[asyncio.ensure_future(_audio_flow())] = "audio"
    else:
        _emit(50, "audio_done")  # skipped (Case 3) — still advance the bar

    if RUN_VIDEO:
        tasks[asyncio.ensure_future(_video_flow())] = "video"

    pending = set(tasks.keys())
    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                kind = tasks[task]
                try:
                    result = task.result()
                except Exception as e:
                    logger.error(f"[{job_id}] {kind} service error: {e}")
                    errors.append({"service": kind, "error": str(e)})
                    result = None

                if kind == "audio":
                    audio_result = result
                    audio_terminal = True
                    _emit(50, "audio_done")
                else:
                    video_result = result
                    video_terminal = True
                    _emit(65, "video_done")

                # Recompute and log the combined pipeline status each time a
                # stage reaches a terminal state.
                ps = _update_pipeline_status()
                logger.info(f"[{job_id}] Combined pipeline status: {ps} (audio={'done' if audio_result or not run_audio_stage else 'pending'}, video={'done' if video_result or not RUN_VIDEO else 'pending'})")
    except asyncio.CancelledError:
        # The orchestrator task was cancelled (user cancel / logout): stop the
        # audio and video poll loops instead of leaving them running.
        for _child in tasks:
            _child.cancel()
        await asyncio.gather(*tasks.keys(), return_exceptions=True)
        raise
    # ──────────────────────────────────────────────────────────────────────

    # ── Save individual JSONs ─────────────────────────────────
    audio_json_path = None
    video_json_path = None

    if audio_result:
        try:
            audio_json_path = save_audio_result(job_name, audio_result)
        except Exception as e:
            logger.error(f"[{job_id}] Save audio JSON failed: {e}")
            errors.append({"service": "audio_save", "error": str(e)})

    if video_result:
        try:
            video_json_path = save_video_result(job_name, video_result)
        except Exception as e:
            logger.error(f"[{job_id}] Save video JSON failed: {e}")
            errors.append({"service": "video_save", "error": str(e)})

    # ── ADDED: if audio stage was skipped, synthesize an empty audio
    # JSON so the report generator can still run video-only and clearly
    # flag the output as visual-only (no audio source available). This
    # never causes the backend to fail — it's the expected Case 3 path.
    if not run_audio_stage and video_json_path and not audio_json_path:
        try:
            audio_json_path = save_audio_result(job_name, {
                "status":         "SKIPPED_NO_AUDIO_SOURCE",
                "request_id":     None,
                "segments_count": 0,
                "latency_sec":    0,
                "segments":       [],
            })
            logger.info(f"[{job_id}] No audio source available — proceeding with video frames only")
        except Exception as e:
            logger.error(f"[{job_id}] Save placeholder audio JSON failed: {e}")
            errors.append({"service": "audio_save", "error": str(e)})

    # ── NEW: video failed (model not ready / crashed) but audio succeeded
    # → synthesize an empty video JSON so the report generator can still
    # run audio-only, instead of skipping the report entirely.
    if audio_json_path and not video_json_path and RUN_VIDEO:
        try:
            video_json_path = save_video_result(job_name, {
                "id": job_id, "status": "SKIPPED_VIDEO_UNAVAILABLE",
                "result": {"metadata": {}, "consolidated_timeline": [], "frame_records": []},
            })
            logger.info(f"[{job_id}] Video unavailable — proceeding with audio only")
        except Exception as e:
            logger.error(f"[{job_id}] Save placeholder video JSON failed: {e}")
            errors.append({"service": "video_save", "error": str(e)})

    # ── Run LLM workflow analysis if both JSONs available ─────
    # Get expected output paths up front so the API response always
    # includes them even if something downstream fails.
    paths             = make_output_paths(job_name)
    steps_clean_path  = None
    validation_path   = None

    if audio_json_path and video_json_path:
        _emit(65, "generating")
        try:
            logger.info(f"[{job_id}] Running LLM workflow analysis...")
            # ── Explicitly tell the report generator whether this run is
            # Case 3 (no separate audio uploaded AND no embedded audio track,
            # user confirmed "Continue"). This is passed down directly from
            # the pause/resume decision above (`run_audio_stage`) rather than
            # being re-inferred later from "audio segments happen to be
            # empty" — that inference is unreliable (e.g. a real audio track
            # that Whisper transcribes as zero segments, i.e. silence, would
            # be misread as Case 3) and would put the Case 3 note on runs
            # that don't belong to it.
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_workflow_analysis(
                    job_name,
                    audio_json_path,
                    video_json_path,
                    username,
                    recipient_email,
                    case3=not run_audio_stage,
                    cancel_check=(CANCEL_EVENTS[job_id].is_set if job_id in CANCEL_EVENTS else None),
                    # Which Settings -> LLM Configuration to use (default
                    # .env credentials, or this browser's own custom key —
                    # see llm_user_id param / the per-browser client id
                    # generated in the frontend, since there's no real
                    # login system yet — see DEFAULT_SETTINGS_USER_ID).
                    user_id=llm_user_id,
                ),
            )
            _emit(90, "saving")
            steps_clean_path = paths["section_a_clean"]
            validation_path  = paths["section_b"]
            logger.info(f"[{job_id}] Workflow reports saved")
        except PipelineCancelled:
            raise asyncio.CancelledError()
        except Exception as e:
            logger.error(f"[{job_id}] LLM analysis failed: {e}")
            errors.append({"service": "llm_analysis", "error": str(e)})

    latency = round(time.time() - start, 2)
    status  = "SUCCESS" if not errors else ("PARTIAL" if (audio_result or video_result) else "FAILED")

    logger.info(f"[{job_id}] Pipeline done | status={status} | latency={latency}s")

    return {
        "job_id":       job_id,
        "job_name":     job_name,
        "status":       status,
        "latency_sec":  latency,
        "outputs": {
            "workflow_steps_clean": str(steps_clean_path) if steps_clean_path else None,
            "workflow_validation":  str(validation_path)  if validation_path  else None,
        },
        "audio_status":     audio_result.get("status") if audio_result else ("SKIPPED_NO_AUDIO_SOURCE" if not run_audio_stage else "SKIPPED"),
        "video_status":     video_result.get("status") if video_result else "SKIPPED",
        "pipeline_status":  _update_pipeline_status(),
        "errors":           errors,
        "processed_at":     datetime.now().isoformat(),
    }

###############################################################
# JOB STORE (in-memory — fine for demo/testing only)
###############################################################

JOBS: dict = {}

# JOB_META holds creation-time metadata (created_at, uploader, original
# filename) that must survive the JOBS[job_id] = {...} full-dict
# replacements that happen as a job moves QUEUED -> RUNNING -> terminal.
# Populated once in /run, never overwritten, so it's a safe join key
# for GET /jobs below.
JOB_META: dict = {}

# ── Job ID generation ────────────────────────────────────────────
# Short, human-friendlier IDs instead of a raw UUID — 4 random uppercase
# letters + 4 random digits, e.g. "PSMC1234". Collision odds are already
# vanishingly small (26^4 * 10^4 ≈ 4.6 billion possible IDs), but each
# candidate is still checked against in-memory JOBS and the database
# (if enabled) before use, with a fresh random draw on any collision —
# so a repeat is provably impossible, not just statistically unlikely.
_ID_LETTERS = string.ascii_uppercase
_ID_DIGITS  = string.digits

def _generate_job_id() -> str:
    for _ in range(50):  # extremely generous — real collisions won't happen
        candidate = "".join(random.choices(_ID_LETTERS, k=4)) + "".join(random.choices(_ID_DIGITS, k=4))
        if candidate in JOBS:
            continue
        if database.DB_ENABLED and database.job_id_exists(candidate):
            continue
        return candidate
    raise RuntimeError("Could not generate a unique job ID after 50 attempts")

# JOB_TASKS holds the live asyncio.Task for every job currently RUNNING in
# the background, keyed by job_id. This is what makes real cancellation
# possible (see POST /cancel/{job_id} below) — without a handle to the
# task, the FastAPI BackgroundTasks mechanism gives us no way to stop
# in-flight work. Entries are removed as soon as the task finishes,
# whether it completes, errors, or is cancelled.
JOB_TASKS: dict = {}

# Cancellation bookkeeping (see _cancel_job_core below):
#   CANCEL_EVENTS   job_id -> threading.Event, set the moment a cancel is
#                   requested; polled by worker threads (report generation).
#   JOB_DOWNSTREAM  job_id -> {"audio": <audio svc job id>, "video": <video
#                   svc job id>} so the cancel can stop those jobs too.
#   CANCEL_LOCKS    job_id -> asyncio.Lock so two cancels of the same job
#                   (e.g. logout + page unload) are serialized, not racing.
CANCEL_EVENTS: dict = {}
JOB_DOWNSTREAM: dict = {}
CANCEL_LOCKS: dict = {}
CANCEL_TIMEOUT_SEC = 30
_ACTIVE_STATUSES = ("QUEUED", "RUNNING", "NEEDS_AUDIO_CONFIRMATION")
_FINAL_STATUSES = ("SUCCESS", "PARTIAL", "FAILED", "ERROR", "CANCELLED")


async def run_full_pipeline_bg(
    job_id: str,
    job_name: str,
    video_path: str,
    audio_path: str = None,
    username: str = "",
    recipient_email: str = "",
    no_audio: bool = False,                    # ← ADDED
    llm_user_id: int = DEFAULT_SETTINGS_USER_ID,
) -> None:
    """Background wrapper around run_full_pipeline; stores result in JOBS."""
    JOBS[job_id] = {"status": "RUNNING", "progress": 10, "phase": "validating", "job_id": job_id, "job_name": job_name}
    # (database row already exists — created synchronously in /run or
    # /confirm-audio when the job was first submitted/confirmed, so that
    # cancellation before this point still has a row to update)
    _job_start_time = time.time()

    # ── callback that writes progress into JOBS ─────────
    def _progress_cb(p, phase):
        JOBS[job_id]["progress"] = p
        JOBS[job_id]["phase"]    = phase
        database.update_job_progress(job_id, p, phase)
        logger.debug(f"[{job_id}] Progress update: {p}% | phase={phase}")
    # ───────────────────────────────────────────────────────────

    try:
        result = await run_full_pipeline(
            job_id, job_name, video_path, audio_path, username, recipient_email,
            progress_cb=_progress_cb,
            no_audio=no_audio,                  # ← ADDED
            llm_user_id=llm_user_id,
        )
        JOBS[job_id] = result
        database.finalize_job(
            job_id, result.get("status", "SUCCESS"),
            error=result.get("error"),
            latency_sec=time.time() - _job_start_time,
        )
    except asyncio.CancelledError:
        # Raised inside this task when POST /cancel/{job_id} calls
        # task.cancel(). The endpoint itself is responsible for writing the
        # final "CANCELLED" status into JOBS (it does so right after
        # awaiting this task) and into the database, so here we just let
        # cleanup run via `finally` below and re-raise so the task
        # genuinely ends up cancelled rather than looking like it
        # finished normally.
        logger.info(f"[{job_id}] Background pipeline cancelled by user request")
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Background pipeline error: {e}", exc_info=True)
        JOBS[job_id] = {"status": "FAILED", "job_id": job_id, "job_name": job_name, "error": str(e)}
        database.finalize_job(job_id, "FAILED", error=str(e), latency_sec=time.time() - _job_start_time)
    finally:
        try:
            Path(video_path).unlink(missing_ok=True)
        except Exception:
            pass
        if audio_path:
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass
        JOB_TASKS.pop(job_id, None)
        _ev = CANCEL_EVENTS.get(job_id)
        if not (_ev and _ev.is_set()):
            # Normal end of a job: nothing left to cancel. When a cancel is in
            # progress, _cancel_job_core still needs these and removes them.
            CANCEL_EVENTS.pop(job_id, None)
            JOB_DOWNSTREAM.pop(job_id, None)

        # ── Auto-export a clean CSV log for this job ──────────────
        # Runs on every job completion (success, failure, or cancellation)
        # regardless of what happened above — the try/except inside
        # export_job_csv means this never raises and never blocks cleanup.
        try:
            final_status = JOBS.get(job_id, {}).get("status", "UNKNOWN")
            log_settings = (database.get_or_create_log_settings(DEFAULT_SETTINGS_USER_ID)
                            if database.DB_ENABLED
                            else {"folder_path": database.default_log_folder(), "enabled": True})
            # Only write the CSV if logging is enabled for this user.
            if log_settings.get("enabled", True):
                log_exporter.export_job_csv(
                    job_id=job_id,
                    job_name=job_name,
                    log_file=LOG_DIR / "orchestrator.log",
                    output_folder=log_settings["folder_path"],
                    final_status=final_status,
                )
        except Exception as e:
            logger.error(f"[{job_id}] CSV export failed: {e}")


def _launch_job(job_id: str, job_name: str, video_path: str, audio_path, username: str, recipient_email: str,
                 no_audio: bool, llm_user_id: int = DEFAULT_SETTINGS_USER_ID) -> None:
    """
    Start run_full_pipeline_bg as a real, cancellable asyncio.Task (instead
    of FastAPI's fire-and-forget BackgroundTasks, which gives no handle to
    cancel later) and remember it in JOB_TASKS so POST /cancel/{job_id} can
    stop it mid-flight.
    """
    CANCEL_EVENTS[job_id] = threading.Event()
    task = asyncio.create_task(
        run_full_pipeline_bg(job_id, job_name, video_path, audio_path, username, recipient_email, no_audio, llm_user_id)
    )
    JOB_TASKS[job_id] = task

###############################################################
# ROUTES
###############################################################

from fastapi import BackgroundTasks, Form

###############################################################
# AUDIO TRACK DETECTION (real backend inspection via ffprobe)
###############################################################

async def video_has_audio_track(video_path: str) -> bool:
    """
    Inspect the actual uploaded video file with ffprobe to determine whether
    it contains an audio stream. This is the ONLY source of truth for audio
    detection — the frontend never decides this. Runs only on the backend,
    only after the file has been fully uploaded and validated, and only
    after the user clicks Generate.

    Returns True if at least one audio stream is present, False otherwise.
    Never raises: any ffprobe failure (corrupt file, missing binary, etc.)
    is treated conservatively as "no audio detected", which still routes
    through the normal Case 3 (confirmation) flow rather than crashing.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            video_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode != 0:
            logger.warning(f"ffprobe exited {proc.returncode} for {video_path}: {stderr.decode(errors='ignore')[:300]}")
            return False

        has_audio = bool(stdout.decode(errors="ignore").strip())
        logger.info(f"ffprobe audio-track check for {video_path}: has_audio={has_audio}")
        return has_audio

    except FileNotFoundError:
        logger.error("ffprobe binary not found — cannot inspect video for audio streams")
        return False
    except Exception as e:
        logger.error(f"ffprobe audio-track check failed for {video_path}: {e}")
        return False


###############################################################
# SILENCE DETECTION (added — treats a silent embedded track the
# same as a missing one)
###############################################################

async def is_audio_silent(video_path: str) -> bool:
    """
    Run ffmpeg's `silencedetect` filter over the audio stream and compute
    what fraction of the TOTAL video duration is silence. If >= 95% of the
    duration is silent, the audio track is considered effectively unusable
    (e.g. a video exported with no sound actually recorded, but the
    container still carries an empty/near-empty audio stream).

    Safe-fallback: if ffmpeg/ffprobe fails or isn't installed, assume audio
    is NOT silent — a detection failure must never block processing.
    """
    try:
        # 1. Total duration of the file (needed to compute the silence ratio)
        dur_proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            video_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        dur_stdout, dur_stderr = await asyncio.wait_for(dur_proc.communicate(), timeout=30)

        if dur_proc.returncode != 0:
            logger.warning(
                f"ffprobe duration check failed for {video_path}: "
                f"{dur_stderr.decode(errors='ignore')[:300]}"
            )
            return False

        try:
            total_duration = float(dur_stdout.decode(errors="ignore").strip())
        except ValueError:
            logger.warning(f"Could not parse duration for {video_path}")
            return False

        if total_duration <= 0:
            return False

        # 2. Run silencedetect over the audio stream
        silence_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", video_path,
            "-af", "silencedetect=noise=-50dB:d=0.5",
            "-f", "null", "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, silence_stderr = await asyncio.wait_for(silence_proc.communicate(), timeout=60)
        log_text = silence_stderr.decode(errors="ignore")

        # 3. Sum every "silence_duration: X" reported by the filter
        silence_total = 0.0
        for match in re.finditer(r"silence_duration:\s*([\d.]+)", log_text):
            try:
                silence_total += float(match.group(1))
            except ValueError:
                continue

        silence_ratio = silence_total / total_duration
        logger.info(
            f"Silence check for {video_path}: silence={silence_total:.2f}s / "
            f"total={total_duration:.2f}s ({silence_ratio * 100:.1f}%)"
        )
        return silence_ratio >= 0.95

    except FileNotFoundError:
        logger.error("ffmpeg/ffprobe binary not found — cannot run silence detection")
        return False
    except Exception as e:
        logger.error(f"Silence detection failed for {video_path}: {e}")
        return False


async def has_usable_audio(video_path: str) -> bool:
    """
    Combines the audio-track-existence check with the silence check.

    An embedded audio track only counts as "usable" if it (a) exists AND
    (b) is not effectively silent. A track that exists but is silent is
    treated exactly like a missing track — both route through the same
    NEEDS_AUDIO_CONFIRMATION pause/resume flow. Does not modify
    `video_has_audio_track()` or the pause/resume state machine at all —
    it only extends the decision of what counts as usable audio.
    """
    has_track = await video_has_audio_track(video_path)
    if not has_track:
        return False

    silent = await is_audio_silent(video_path)
    if silent:
        logger.info(
            f"Embedded audio track found for {video_path} but it is silent "
            f"(>=95% of duration) — treating as no usable audio"
        )
        return False

    return True


@app.post("/run")
async def run_pipeline(
    video: UploadFile = File(...),
    audio: UploadFile = File(None),
    username: str = Form(""),
    email: str = Form(""),
    llmUserId: str = Form(""),
    verified_user_id: int = Depends(require_user),
    background_tasks: BackgroundTasks = None,
) -> JSONResponse:
    """
    Accept a video file (and optionally a separate audio file), save them,
    and determine which audio source to use — ONLY after the upload is
    complete and validated. The "No Audio Detected" popup must never be
    decided client-side; this endpoint is the single source of truth.

    Audio source decision (performed here, after validation):
      1. If `audio` is provided, it is always used — the video's embedded
         audio track (if any) is ignored. Processing starts immediately.
      2. Else, the uploaded video is inspected with ffprobe AND checked for
         silence. If it contains an audio stream that is NOT effectively
         silent, that audio is extracted and used. Processing starts
         immediately.
      3. Else (no separate audio AND no usable audio track in the video —
         either missing entirely, or present but silent), this endpoint
         does NOT start full processing. It returns
         status="NEEDS_AUDIO_CONFIRMATION" so the frontend can show the
         "No Audio Detected" popup. The job is held in JOBS awaiting a
         call to POST /confirm-audio/{job_id} with the user's choice.

    If `email` is provided, output files are emailed to that address on completion.
    """
    job_id   = _generate_job_id()
    job_name = make_job_name(video.filename)

    # Accept llmUserId for older clients, but use only the authenticated
    # identity when selecting saved provider credentials.
    llm_user_id = verified_user_id

    JOB_META[job_id] = {
        "created_at":     datetime.now().isoformat(),
        "username":       username or "anonymous",
        "video_filename": video.filename,
        "llm_user_id":    llm_user_id,
        "user_id":        get_current_user_id(),
    }

    logger.info(
        f"[{job_id}] Received: {video.filename} | audio={audio.filename if audio else None} "
        f"| job_name={job_name} | email={bool(email)}"
    )
    logger.debug(f"[{job_id}] Full request: username={username!r} email={email!r} "
                 f"video_content_type={video.content_type} "
                 f"audio_content_type={audio.content_type if audio else None}")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    suffix     = Path(video.filename).suffix or ".mp4"
    video_path = str(TEMP_DIR / f"{job_id}{suffix}")

    audio_path = None
    if audio is not None and audio.filename:
        audio_suffix = Path(audio.filename).suffix or ".mp3"
        audio_path   = str(TEMP_DIR / f"{job_id}_audio{audio_suffix}")

    try:
        chunk_size = 1_048_576
        total_size = 0
        if database.DB_ENABLED:
            _upload_cfg = database.get_or_create_upload_settings(DEFAULT_SETTINGS_USER_ID)
            video_max_mb = _upload_cfg["max_upload_size_mb"]
            audio_max_mb = _upload_cfg["max_audio_upload_size_mb"]
        else:
            video_max_mb = audio_max_mb = database.DEFAULT_UPLOAD_SIZE_MB
        video_max_size = video_max_mb * 1024 * 1024
        audio_max_size = audio_max_mb * 1024 * 1024

        with open(video_path, "wb") as f:
            while True:
                chunk = await video.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > video_max_size:
                    f.close()  # must close before unlink -- Windows locks open file handles
                    Path(video_path).unlink(missing_ok=True)  # don't keep the partial/oversized file
                    return JSONResponse(
                        status_code=413,
                        content={
                            "success": False,
                            "message": f"File size exceeds your configured upload limit of {video_max_mb} MB.",
                        },
                    )
                f.write(chunk)

        logger.info(f"[{job_id}] Video upload saved: {total_size / (1024*1024):.1f} MB")

        if audio_path:
            audio_size = 0
            with open(audio_path, "wb") as f:
                while True:
                    chunk = await audio.read(chunk_size)
                    if not chunk:
                        break
                    audio_size += len(chunk)
                    if audio_size > audio_max_size:
                        f.close()
                        Path(video_path).unlink(missing_ok=True)
                        Path(audio_path).unlink(missing_ok=True)
                        return JSONResponse(
                            status_code=413,
                            content={
                                "success": False,
                                "message": f"File size exceeds your configured audio upload limit of {audio_max_mb} MB.",
                            },
                        )
                    f.write(chunk)
            logger.info(f"[{job_id}] Audio upload saved: {audio_size / (1024*1024):.1f} MB")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{job_id}] Upload failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": str(e), "job_id": job_id},
        )

    # ── Validation complete. Now decide the audio source — this is the
    # only place that decision is made, and only now (post-upload). ──
    JOB_META[job_id]["size_bytes"] = total_size + (audio_size if audio_path else 0)
    separate_audio_uploaded = bool(audio_path)

    if separate_audio_uploaded:
        # Case 1: always use the uploaded audio file. No inspection needed.
        logger.info(f"[{job_id}] Case 1: separate audio file uploaded — using it directly")
        JOBS[job_id] = {"status": "QUEUED", "job_id": job_id, "job_name": job_name, "phase": "validating"}
        database.create_job(job_id, job_name, username=username, email=email,
                             video_filename=video.filename, audio_filename=audio.filename if audio else "",
                             video_size_bytes=JOB_META[job_id]["size_bytes"])
        _launch_job(job_id, job_name, video_path, audio_path, username, email, False, llm_user_id)
        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "job_name": job_name, "status": "QUEUED"},
        )

    # No separate audio — inspect the actual video file for USABLE audio
    # (must have an audio stream AND that stream must not be effectively
    # silent — see has_usable_audio()).
    video_has_audio = await has_usable_audio(video_path)

    if video_has_audio:
        # Case 2: video has its own embedded, non-silent audio track — extract and use it.
        logger.info(f"[{job_id}] Case 2: video contains a usable embedded audio track — extracting it")
        JOBS[job_id] = {"status": "QUEUED", "job_id": job_id, "job_name": job_name, "phase": "validating"}
        database.create_job(job_id, job_name, username=username, email=email,
                             video_filename=video.filename, audio_filename="",
                             video_size_bytes=JOB_META[job_id]["size_bytes"])
        _launch_job(job_id, job_name, video_path, None, username, email, False, llm_user_id)
        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "job_name": job_name, "status": "QUEUED"},
        )

    # Case 3: neither a separate audio file nor a usable embedded audio
    # track (missing entirely, or present but silent).
    # Do NOT start processing. Hold the job and ask the frontend to confirm.
    logger.info(f"[{job_id}] Case 3: no separate audio and no usable audio track detected — awaiting user confirmation")
    JOBS[job_id] = {
        "status":     "NEEDS_AUDIO_CONFIRMATION",
        "job_id":     job_id,
        "job_name":   job_name,
        "video_path": video_path,
        "username":   username,
        "email":      email,
        "llm_user_id": llm_user_id,
        "title":      "No Audio Detected",
        "message": (
            "No audio track was found in the uploaded video, and no separate "
            "audio file was uploaded. Would you like to continue processing "
            "using only the video frames?"
        ),
    }
    database.create_job(job_id, job_name, username=username, email=email,
                         video_filename=video.filename, audio_filename="",
                         video_size_bytes=JOB_META[job_id]["size_bytes"])
    return JSONResponse(
        status_code=200,
        content={
            "job_id":   job_id,
            "job_name": job_name,
            "status":   "NEEDS_AUDIO_CONFIRMATION",
            "title":    "No Audio Detected",
            "message": (
                "No audio track was found in the uploaded video, and no separate "
                "audio file was uploaded. Would you like to continue processing "
                "using only the video frames?"
            ),
        },
    )


@app.post("/confirm-audio/{job_id}", dependencies=[Depends(require_user)])
async def confirm_audio(job_id: str, proceed: bool = Form(...), background_tasks: BackgroundTasks = None) -> JSONResponse:
    """
    Resolve a job left in NEEDS_AUDIO_CONFIRMATION state (Case 3) after the
    user responds to the "No Audio Detected" popup.

    proceed=true  (Continue) → start processing using only video frames;
                                 the generated output will carry the
                                 "video frames only" notice.
    proceed=false (Cancel)   → stop the workflow immediately; nothing is
                                 processed; the temp video file is removed.
    """
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if job.get("status") != "NEEDS_AUDIO_CONFIRMATION":
        raise HTTPException(status_code=409, detail=f"Job is not awaiting audio confirmation (status={job.get('status')})")

    video_path = job["video_path"]

    if not proceed:
        logger.info(f"[{job_id}] User clicked Cancel — stopping workflow, no processing performed")
        try:
            Path(video_path).unlink(missing_ok=True)
        except Exception:
            pass
        JOBS[job_id] = {
            "job_id":  job_id,
            "job_name": job["job_name"],
            "status":  "CANCELLED",
            "message": "Processing was cancelled by the user.",
        }
        database.finalize_job(job_id, "CANCELLED")
        return JSONResponse(status_code=200, content=JOBS[job_id])

    logger.info(f"[{job_id}] User clicked Continue — processing using video frames only")
    JOBS[job_id] = {"status": "QUEUED", "job_id": job_id, "job_name": job["job_name"], "phase": "validating"}
    _launch_job(
        job_id, job["job_name"], video_path, None,
        job.get("username", ""), job.get("email", ""),
        True,                                    # no_audio=True → video-frames-only
        job.get("llm_user_id", DEFAULT_SETTINGS_USER_ID),
    )
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "job_name": job["job_name"], "status": "QUEUED"},
    )


async def _cancel_job_core(job_id: str) -> dict:
    """
    Real, race-safe cancellation of ONE job. Never raises.

    Order of operations:
      1. Serialize with any other cancel of the same job (per-job lock) and
         re-read the status under the lock, so a job that already reached a
         final state (SUCCESS/PARTIAL/FAILED/CANCELLED) is never changed.
      2. Signal worker threads (CANCEL_EVENTS) and cancel the orchestrator's
         asyncio task; that also cancels the audio / video poll loops.
      3. Ask the audio and video services to stop the downstream jobs they
         are running for this pipeline (concurrently, best effort).
      4. Re-check: if the pipeline finished on its own while we were
         cancelling, keep its result.
      5. Write the final status: CANCELLED for a user cancellation, FAILED if
         the pipeline could not be stopped / stopped with a technical error.
         Persisted via database.finalize_job. Downstream-stop problems are
         recorded as warnings without turning the job into FAILED.
    """
    lock = CANCEL_LOCKS.setdefault(job_id, asyncio.Lock())
    try:
        async with lock:
            job = JOBS.get(job_id)
            if job is None:
                return {"job_id": job_id, "outcome": "unknown"}
            status = job.get("status")
            if status in _FINAL_STATUSES:
                return {"job_id": job_id, "outcome": "already_finished", "status": status}

            job_name = job.get("job_name", "")
            warnings: list = []
            technical_error = None

            event = CANCEL_EVENTS.get(job_id)
            if event is not None:
                event.set()

            # Paused awaiting the "No Audio Detected" answer: nothing is running,
            # only the uploaded file needs to be released.
            if status == "NEEDS_AUDIO_CONFIRMATION":
                video_path = job.get("video_path")
                if video_path:
                    try:
                        Path(video_path).unlink(missing_ok=True)
                    except Exception as e:
                        warnings.append(f"could not remove temp video: {e}")

            task = JOB_TASKS.get(job_id)
            if task is not None and not task.done():
                task.cancel()
                _done, _pending = await asyncio.wait([task], timeout=CANCEL_TIMEOUT_SEC)
                if _pending:
                    technical_error = f"pipeline did not stop within {CANCEL_TIMEOUT_SEC}s"
                elif not task.cancelled() and task.exception() is not None:
                    technical_error = f"pipeline stopped with an error: {task.exception()}"

            # Stop what the audio / video services are doing for this job.
            downstream = dict(JOB_DOWNSTREAM.get(job_id, {}))
            stop_calls = []
            if downstream.get("audio"):
                stop_calls.append(("audio", cancel_audio_job(downstream["audio"])))
            if downstream.get("video"):
                stop_calls.append(("video", cancel_video_job(downstream["video"])))
            if stop_calls:
                outcomes = await asyncio.gather(*[c for _, c in stop_calls], return_exceptions=True)
                for (kind, _), ok in zip(stop_calls, outcomes):
                    if ok is not True:
                        warnings.append(f"{kind} service did not confirm the stop")

            # The pipeline may have completed by itself while we were waiting.
            current = JOBS.get(job_id) or {}
            if current.get("status") in _FINAL_STATUSES:
                return {"job_id": job_id, "outcome": "already_finished", "status": current.get("status")}

            final_status = "FAILED" if technical_error else "CANCELLED"
            error_text = technical_error
            if warnings:
                note = "cancellation warning: " + "; ".join(warnings)
                error_text = f"{technical_error}; {note}" if technical_error else note

            JOBS[job_id] = {
                "job_id":       job_id,
                "job_name":     job_name,
                "status":       final_status,
                "message":      "Processing was cancelled by the user." if final_status == "CANCELLED"
                                else "Processing could not be cancelled cleanly.",
                "processed_at": datetime.now().isoformat(),
            }
            if error_text:
                JOBS[job_id]["error"] = error_text
            database.finalize_job(job_id, final_status, error=error_text)

            JOB_TASKS.pop(job_id, None)
            JOB_DOWNSTREAM.pop(job_id, None)
            CANCEL_EVENTS.pop(job_id, None)
            logger.info(f"[{job_id}] Job {final_status.lower()} by user request"
                        + (f" | {error_text}" if error_text else ""))
            return {"job_id": job_id, "outcome": final_status.lower(), "status": final_status,
                    "warnings": warnings}
    except Exception as e:  # never let a cancel crash the caller (logout must still complete)
        logger.error(f"[{job_id}] Cancellation error: {e}", exc_info=True)
        try:
            JOBS[job_id] = {**(JOBS.get(job_id) or {"job_id": job_id}), "status": "FAILED",
                            "error": f"cancellation error: {e}",
                            "processed_at": datetime.now().isoformat()}
            database.finalize_job(job_id, "FAILED", error=f"cancellation error: {e}")
        except Exception:
            pass
        return {"job_id": job_id, "outcome": "error", "status": "FAILED", "error": str(e)}
    finally:
        CANCEL_LOCKS.pop(job_id, None)


def _assert_job_owner(job_id: str) -> None:
    """403 unless the authenticated user owns the job (jobs with no recorded
    owner, i.e. legacy restored rows, stay accessible as elsewhere)."""
    owner = JOB_META.get(job_id, {}).get("user_id")
    me = get_current_user_id()
    if owner is not None and me is not None and owner != me:
        raise HTTPException(status_code=403, detail="This job belongs to another user.")


@app.post("/cancel/{job_id}", dependencies=[Depends(require_user)])
async def cancel_job(job_id: str) -> JSONResponse:
    """
    Cancel a job that is currently queued, running, or paused awaiting
    audio confirmation. Called by the frontend when the user explicitly
    cancels, or confirms leaving the page while a job is active.

    - QUEUED / RUNNING          -> the orchestrator task, the audio/video
                                    poll loops, the downstream audio/video
                                    jobs and report generation are stopped
                                    (see _cancel_job_core); temp files are
                                    released.
    - NEEDS_AUDIO_CONFIRMATION  -> same outcome as clicking "Cancel" on the
                                    no-audio popup - nothing was processed.
    - already final             -> no-op, the current state is returned (a
                                    completed job is never turned into
                                    CANCELLED).
    Only the owner of the job may cancel it (403 otherwise).
    """
    if JOBS.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    _assert_job_owner(job_id)
    await _cancel_job_core(job_id)
    return JSONResponse(status_code=200, content=JOBS[job_id])


@app.post("/cancel-active", dependencies=[Depends(require_user)])
async def cancel_active_jobs() -> JSONResponse:
    """
    Cancel every active (QUEUED / RUNNING / NEEDS_AUDIO_CONFIRMATION) job of
    the authenticated user - and only that user's jobs. Used by Logout.

    Always answers 200 with a per-job report so the caller can finish
    logging out even if some jobs could not be cancelled cleanly:
      { "cancelled": [...], "already_finished": [...], "failed": [...] }
    """
    me = get_current_user_id()
    targets = [
        jid for jid, job in list(JOBS.items())
        if job.get("status") in _ACTIVE_STATUSES
        and me is not None
        and JOB_META.get(jid, {}).get("user_id") == me
    ]
    results = await asyncio.gather(*[_cancel_job_core(j) for j in targets])

    report = {"cancelled": [], "already_finished": [], "failed": []}
    for r in results:
        outcome = r.get("outcome")
        if outcome == "cancelled":
            report["cancelled"].append(r["job_id"])
        elif outcome == "already_finished":
            report["already_finished"].append(r["job_id"])
        else:
            report["failed"].append({"job_id": r["job_id"], "error": r.get("error") or r.get("status")})
    logger.info(f"[cancel-active] user={me} | {report}")
    return JSONResponse(status_code=200, content=report)


@app.get("/jobs", dependencies=[Depends(require_user)])
async def list_jobs(page: int = 1, page_size: int = 8, search: str = "") -> dict:
    """
    Paginated, most-recent-first list of every job this server process has
    seen, merged with creation-time metadata from JOB_META. Powers the
    Dashboard's Activity Feed and Data Table.
    """
    rows = []
    current_user = get_current_user_id()
    for job_id, job in JOBS.items():
        meta = JOB_META.get(job_id, {})
        # Scope to the authenticated user: each job is owned by the user id
        # recorded in JOB_META at upload time (see /run). Jobs with no
        # recorded owner (legacy DB-restored entries) are visible to all.
        if meta.get("user_id") is not None and meta.get("user_id") != current_user:
            continue
        rows.append({
            "job_id":       job_id,
            "job_name":     job.get("job_name", ""),
            "filename":     meta.get("video_filename") or job.get("job_name", ""),
            "uploader":     meta.get("username", "anonymous"),
            "status":       job.get("status", "UNKNOWN"),
            "progress":     job.get("progress"),
            "phase":        job.get("phase"),
            "latency_sec":  job.get("latency_sec"),
            "error":        job.get("error"),
            "created_at":   meta.get("created_at"),
            "processed_at": job.get("processed_at"),
            "size_bytes":   meta.get("size_bytes"),
        })

    if search:
        q = search.lower()
        rows = [
            r for r in rows
            if q in (r["filename"] or "").lower()
            or q in (r["uploader"] or "").lower()
            or q in (r["status"] or "").lower()
        ]

    # Most recent first. Falls back to "" for any legacy job created before
    # this patch (no JOB_META entry) so it just sorts to the bottom.
    rows.sort(key=lambda r: r["created_at"] or "", reverse=True)

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    return {
        "jobs":      page_rows,
        "total":     total,
        "page":      page,
        "page_size": page_size,
    }


@app.get("/stats", dependencies=[Depends(require_user)])
async def get_stats() -> dict:
    """
    Aggregate counts across every job this server process has ever seen
    (JOBS entries are never deleted, only updated in place, so len(JOBS)
    is a running total of uploads). Powers the Dashboard summary cards.
    """
    current_user = get_current_user_id()
    user_jobs = [
        job for job_id, job in JOBS.items()
        if (meta := JOB_META.get(job_id, {})).get("user_id") is None
        or meta.get("user_id") == current_user
    ]
    total_uploaded = len(user_jobs)
    processing = completed = cancelled = failed = 0

    for job in user_jobs:
        status = job.get("status")
        if status in ("QUEUED", "RUNNING", "NEEDS_AUDIO_CONFIRMATION"):
            processing += 1
        elif status in ("SUCCESS", "PARTIAL"):
            completed += 1
        elif status == "CANCELLED":
            cancelled += 1
        elif status in ("FAILED", "ERROR"):
            failed += 1

    return {
        "total_uploaded": total_uploaded,
        "processing":     processing,
        "completed":      completed,
        "cancelled":      cancelled,
        "failed":         failed,
        "storage_used_gb": _get_storage_used_gb(),
    }


###############################################################
# LOG CONFIGURATION (Settings page)
###############################################################

@app.get("/settings/log-config", dependencies=[Depends(require_user)])
async def get_log_config(userId: int = DEFAULT_SETTINGS_USER_ID) -> dict:
    """
    Returns the saved Log Configuration, creating a default row (level
    DEBUG, enabled, default folder — created on disk if missing) the
    first time it's ever loaded. userId is optional for now (defaults
    to a single shared settings row) — ready to become required/real
    once this page has actual per-user identification.
    """
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — log settings can't be persisted.")

    settings = database.get_or_create_log_settings(userId)
    apply_result = apply_user_log_config(
        settings["folder_path"], settings["level"], settings["enabled"], settings["max_size_mb"]
    )
    return {
        "user_id":     userId,
        "level":       settings["level"],
        "folder_path": apply_result["folder_path"],
        "enabled":     settings["enabled"],
        "max_size_mb": settings["max_size_mb"],
        "warning":     apply_result["warning"],
    }


@app.post("/settings/log-config", dependencies=[Depends(require_user)])
async def save_log_config(payload: dict) -> dict:
    """
    Body: {"userId": 1, "level": "DEBUG", "folder_path": "C:\\Logs",
            "enabled": true, "max_size_mb": 50}
    userId is optional (defaults to the single shared settings row).
    Saves to the database AND immediately applies it to this running
    backend process's active logging.
    """
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — log settings can't be persisted.")

    user_id     = payload.get("userId", DEFAULT_SETTINGS_USER_ID)
    level       = (payload.get("level") or "DEBUG").upper()
    folder_path = payload.get("folder_path")
    enabled     = bool(payload.get("enabled", True))
    max_size_mb = payload.get("max_size_mb", 50)

    if not folder_path:
        raise HTTPException(status_code=400, detail="folder_path is required")
    if level not in database.VALID_LOG_LEVELS:
        raise HTTPException(status_code=400, detail=f"level must be one of {sorted(database.VALID_LOG_LEVELS)}")
    if not isinstance(max_size_mb, int) or max_size_mb <= 0:
        raise HTTPException(status_code=400, detail="max_size_mb must be a positive integer")

    apply_result = apply_user_log_config(folder_path, level, enabled, max_size_mb)
    # Persist whatever folder actually ended up active (may be the
    # fallback default, not the one requested, if it wasn't writable) —
    # so what's saved always matches what's really in effect.
    database.save_log_settings(user_id, level, apply_result["folder_path"], enabled, max_size_mb)

    return {
        "user_id":     user_id,
        "level":       level,
        "folder_path": apply_result["folder_path"],
        "enabled":     enabled,
        "max_size_mb": max_size_mb,
        "warning":     apply_result["warning"],
    }


@app.post("/settings/log-config/reset", dependencies=[Depends(require_user)])
async def reset_log_config(payload: dict = None) -> dict:
    """Body: {"userId": 1} (optional). Resets level to DEBUG, enabled, default folder/size."""
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — log settings can't be persisted.")

    user_id = (payload or {}).get("userId", DEFAULT_SETTINGS_USER_ID)

    settings = database.reset_log_settings(user_id)
    apply_result = apply_user_log_config(
        settings["folder_path"], settings["level"], settings["enabled"], settings["max_size_mb"]
    )
    return {
        "user_id":     user_id,
        "level":       settings["level"],
        "folder_path": apply_result["folder_path"],
        "enabled":     settings["enabled"],
        "max_size_mb": settings["max_size_mb"],
        "warning":     apply_result["warning"],
    }


###############################################################
# UPLOAD CONFIGURATION (Settings page — max upload file size)
###############################################################

@app.get("/settings/upload-config", dependencies=[Depends(require_user)])
async def get_upload_config(userId: int = DEFAULT_SETTINGS_USER_ID) -> dict:
    """Returns the configured max upload sizes (video + audio), creating a default (500 MB each) row if none exists."""
    if not database.DB_ENABLED:
        return {
            "user_id": userId,
            "max_upload_size_mb": database.DEFAULT_UPLOAD_SIZE_MB,
            "max_audio_upload_size_mb": database.DEFAULT_UPLOAD_SIZE_MB,
        }

    settings = database.get_or_create_upload_settings(userId)
    return {
        "user_id": userId,
        "max_upload_size_mb": settings["max_upload_size_mb"],
        "max_audio_upload_size_mb": settings["max_audio_upload_size_mb"],
    }


@app.post("/settings/upload-config", dependencies=[Depends(require_user)])
async def save_upload_config(payload: dict) -> dict:
    """
    Body: {"userId": 1, "max_upload_size_mb": 3, "max_audio_upload_size_mb": 10} (userId optional).
    Rejects (400) anything outside 1-500 MB for either field — neither
    value is saved if either fails validation, per the spec.
    """
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — upload settings can't be persisted.")

    user_id       = payload.get("userId", DEFAULT_SETTINGS_USER_ID)
    max_mb        = payload.get("max_upload_size_mb")
    max_audio_mb  = payload.get("max_audio_upload_size_mb")

    for value, label in ((max_mb, "video"), (max_audio_mb, "audio")):
        if not isinstance(value, int) or not (database.MIN_UPLOAD_SIZE_MB <= value <= database.MAX_UPLOAD_SIZE_MB):
            raise HTTPException(
                status_code=400,
                detail=(f"Maximum {label} upload file size cannot exceed {database.MAX_UPLOAD_SIZE_MB} MB. "
                        f"Please enter a value between {database.MIN_UPLOAD_SIZE_MB} MB and {database.MAX_UPLOAD_SIZE_MB} MB."),
            )

    database.save_upload_settings(user_id, max_mb, max_audio_mb)
    return {"user_id": user_id, "max_upload_size_mb": max_mb, "max_audio_upload_size_mb": max_audio_mb}


@app.post("/settings/upload-config/reset", dependencies=[Depends(require_user)])
async def reset_upload_config(payload: dict = None) -> dict:
    """Body: {"userId": 1} (optional). Resets both limits back to 500 MB."""
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — upload settings can't be persisted.")

    user_id = (payload or {}).get("userId", DEFAULT_SETTINGS_USER_ID)
    settings = database.reset_upload_settings(user_id)
    return {
        "user_id": user_id,
        "max_upload_size_mb": settings["max_upload_size_mb"],
        "max_audio_upload_size_mb": settings["max_audio_upload_size_mb"],
    }


###############################################################
# LLM CONFIGURATION (Settings page — default vs. customer's own API key)
###############################################################

@app.get("/settings/llm-config")
async def get_llm_config(user_id: int = Depends(require_user)) -> dict:
    """
    Returns the saved LLM Configuration mode for this user, WITHOUT ever
    exposing the actual API key value — only whether the key is configured,
    plus a masked preview for display. Settings are scoped to the verified user.
    """
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — LLM settings can't be persisted.")

    return database.llm_config_response(user_id)


@app.post("/settings/llm-config")
async def save_llm_config(
    payload: dict,
    user_id: int = Depends(require_user),
) -> dict:
    """
    Body: {"mode": "default" | "custom", "provider": "...", "model": "...",
           "primary_api_key": "..."}

    primary_api_key is OPTIONAL — omit it (or send null) to leave the
    stored key unchanged. Send an empty string to explicitly clear it.

    Never returns the actual key values — see database.llm_config_response().
    """
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — LLM settings can't be persisted.")

    mode_value = payload.get("mode") or "default"
    if not isinstance(mode_value, str) or mode_value.lower() not in ("default", "custom"):
        raise HTTPException(status_code=400, detail="mode must be 'default' or 'custom'")
    mode = mode_value.lower()

    provider = payload.get("provider")
    model = payload.get("model")
    if mode == "custom":
        existing_settings = database.get_llm_settings(user_id) or {}
        existing_provider = existing_settings.get(
            "provider", database.DEFAULT_LLM_PROVIDER
        )
        if provider is None:
            provider = existing_provider
        if not isinstance(provider, str) or provider not in LLM_PROVIDER_BASE_URLS:
            raise HTTPException(status_code=400, detail="Unsupported LLM provider.")
        if model is None:
            if provider == existing_provider:
                model = existing_settings.get("model")
            elif provider == database.DEFAULT_LLM_PROVIDER:
                model = database.DEFAULT_LLM_MODEL
        if not isinstance(model, str) or not model.strip() or len(model) > 255:
            raise HTTPException(
                status_code=400,
                detail="model must be a non-empty string of at most 255 characters.",
            )
    else:
        provider = database.DEFAULT_LLM_PROVIDER
        model = database.DEFAULT_LLM_MODEL

    # Distinguish "field omitted" (leave unchanged) from "field sent" (may
    # be a new value, or "" to clear) by checking key presence, not truthiness.
    primary_api_key   = payload.get("primary_api_key")   if "primary_api_key"   in payload else None
    if primary_api_key is not None and not isinstance(primary_api_key, str):
        raise HTTPException(status_code=400, detail="primary_api_key must be a string or null.")

    try:
        database.save_llm_settings(
            user_id,
            use_custom_key=(mode == "custom"),
            provider=provider,
            model=model,
            primary_api_key=primary_api_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return database.llm_config_response(user_id)


@app.post("/settings/llm-config/reset")
async def reset_llm_config(user_id: int = Depends(require_user)) -> dict:
    """Resets the verified user's settings to the default OpenRouter key."""
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — LLM settings can't be persisted.")

    database.reset_llm_settings(user_id)
    return database.llm_config_response(user_id)


@app.post("/settings/llm-config/models")
async def refresh_llm_models(
    payload: dict,
    user_id: int = Depends(require_user),
) -> dict:
    """Refresh available models via the selected provider's fixed API endpoint."""
    if not database.DB_ENABLED:
        raise HTTPException(status_code=503, detail="Database is disabled — LLM settings can't be loaded.")

    provider = payload.get("provider")
    if not isinstance(provider, str) or provider not in LLM_PROVIDER_BASE_URLS:
        raise HTTPException(status_code=400, detail="Unsupported LLM provider.")

    api_key = payload.get("api_key")
    if api_key is not None and not isinstance(api_key, str):
        raise HTTPException(status_code=400, detail="api_key must be a string.")

    settings = database.get_llm_settings(user_id) or {}
    if not api_key or not api_key.strip():
        if settings.get("use_custom_key"):
            api_key = settings.get("primary_api_key", "")
        elif provider == database.DEFAULT_LLM_PROVIDER:
            api_key = get_application_llm_api_key()

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="A provider API key is required to refresh its models.",
        )

    try:
        models = fetch_provider_models(provider, api_key)
    except (requests.RequestException, ValueError, RuntimeError) as e:
        logger.error(
            "LLM model refresh failed for provider=%s: %s",
            provider,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="The provider's model list could not be loaded.",
        ) from e

    return {"provider": provider, "models": models}


@app.get("/status/{job_id}", dependencies=[Depends(require_user)])
async def get_status(job_id: str) -> JSONResponse:
    """Poll this endpoint to check job progress/result."""
    result = JOBS.get(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return JSONResponse(status_code=200, content=result)

@app.get("/health")
async def health() -> dict:
    audio_ok, video_ok = await asyncio.gather(
        check_audio_health(),
        check_video_health(),
    )
    overall = "healthy" if (audio_ok and video_ok) else "degraded"
    return {
        "status":        overall,
        "orchestrator":  "healthy",
        "audio_service": "healthy" if audio_ok else "unreachable",
        "video_service": "healthy" if video_ok else "unreachable",
        "timestamp":     datetime.now().isoformat(),
    }


###############################################################
# STARTUP & SHUTDOWN
###############################################################

@app.on_event("startup")
async def startup() -> None:
    logger.info("=" * 60)
    logger.info("ORCHESTRATOR — INTEGRATED PIPELINE v1.0")
    logger.info(f"  run_audio = {RUN_AUDIO}")
    logger.info(f"  run_video = {RUN_VIDEO}")
    logger.info("=" * 60)

    if database.DB_ENABLED:
        try:
            database.init_db()
            logger.info(f"  Database: [UP] ({database.DB_SERVER}/{database.DB_NAME}, schema={database.DB_SCHEMA})")

            loaded = database.load_all_jobs()
            for row in loaded:
                job_id = row["job_id"]
                JOBS[job_id] = {
                    "job_id":      job_id,
                    "job_name":    row["job_name"],
                    "status":      row["status"],
                    "phase":       row["phase"],
                    "progress":    row["progress"],
                    "error":       row["error"],
                    "latency_sec": row["latency_sec"],
                    "processed_at": row["processed_at"],
                }
                JOB_META[job_id] = {
                    "video_filename": row["video_filename"],
                    "username":       row["username"],
                    "created_at":     row["created_at"],
                    "size_bytes":     row["video_size_bytes"],
                }
                # Anything that was still RUNNING/QUEUED when the server
                # last stopped can never actually resume (its in-memory
                # asyncio.Task is gone) — mark it FAILED so it doesn't
                # sit in the Dashboard forever showing "processing".
                if JOBS[job_id]["status"] in ("QUEUED", "RUNNING", "NEEDS_AUDIO_CONFIRMATION"):
                    JOBS[job_id]["status"] = "FAILED"
                    JOBS[job_id]["error"] = "Interrupted by server restart"
                    database.finalize_job(job_id, "FAILED", error="Interrupted by server restart")
            if loaded:
                logger.info(f"  Restored {len(loaded)} job(s) from database into Dashboard history.")
        except Exception as e:
            logger.error(f"  Database: [DOWN] init_db() failed: {e} — falling back to in-memory job tracking only")
    else:
        logger.info("  Database: disabled (DB_ENABLED=false) — using in-memory job tracking only")

    audio_ok, video_ok = await asyncio.gather(
        check_audio_health(),
        check_video_health(),
    )
    logger.info(f"  Audio service: {'[UP]' if audio_ok else '[DOWN]'}")
    logger.info(f"  Video service: {'[UP]' if video_ok else '[DOWN]'}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Orchestrator shutting down...")


###############################################################
# MAIN
###############################################################

if __name__ == "__main__":
    port = config.get("orchestrator", {}).get("fastapi_port", 8020)
    logger.info(f"Starting Orchestrator on port {port}")

    uvicorn.run(
        "integrated_pipeline:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        log_config=None,
        access_log=False,
    )
