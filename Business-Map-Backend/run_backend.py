# """
# run_backend.py
# ===============
# Single entry point for running the whole backend LOCALLY (Windows/macOS/
# Linux) — replaces the old Kaggle-notebook launcher.

#     python run_backend.py

# It will, in order:
#   1. Load secrets/config from a local .env file (see .env.example) into
#      environment variables — OPENROUTER_API_KEY, EMAIL_SENDER_PASSWORD,
#      DB_* variables, etc.
#   2. Check that Redis and ffmpeg are installed and reachable (does NOT
#      try to apt-get install anything — this is not a container/notebook).
#   3. Start the audio service   (port 8001)
#   4. Start the video service   (port 8002)
#   5. Start the orchestrator    (port 8000) — this is the one the
#      frontend talks to, at http://localhost:8000

# Execution order for a single video job is controlled inside
# AudioVideoPipeline/Orchestrator/integrated_pipeline.py (run_full_pipeline),
# not in this launcher — this launcher only brings the 3 HTTP services up
# and waits for them to become healthy.

# This script is idempotent-ish: re-running it after a crash will try to
# free the ports first. It is NOT meant to be imported — run it directly.
# """

# import os
# import shutil
# import signal
# import socket
# import subprocess
# import sys
# import time
# from pathlib import Path
# from typing import Optional

# # ==================================================================
# # 0. PATHS
# # ==================================================================
# REPO_ROOT      = Path(__file__).resolve().parent
# PIPELINE_ROOT  = REPO_ROOT / "AudioVideoPipeline"
# AUDIO_DIR      = PIPELINE_ROOT / "audio_service"
# VIDEO_DIR      = PIPELINE_ROOT / "video_service"
# ORCH_DIR       = PIPELINE_ROOT / "Orchestrator"
# CONFIG_PATH    = PIPELINE_ROOT / "Configuration" / "config.yaml"

# for p in (PIPELINE_ROOT, AUDIO_DIR, VIDEO_DIR, ORCH_DIR, CONFIG_PATH):
#     if not p.exists():
#         sys.exit(f"[run_backend] FATAL: expected path not found: {p}\n"
#                   f"Run this script from the repo root (next to AudioVideoPipeline/).")

# os.environ["CONFIG_PATH"] = str(CONFIG_PATH)


# # ==================================================================
# # 1. LOAD .env INTO ENVIRONMENT VARIABLES
# # ==================================================================
# def load_dotenv_file() -> None:
#     """
#     Load REPO_ROOT/.env (create it by copying .env.example) into
#     os.environ, so OPENROUTER_API_KEY, EMAIL_SENDER_PASSWORD, DB_*, etc.
#     reach the audio/video/orchestrator subprocesses started below (they
#     inherit os.environ via env=os.environ.copy() in start_service()).
#     """
#     try:
#         from dotenv import load_dotenv
#     except ImportError:
#         print("[run_backend] python-dotenv not installed — skipping .env loading "
#               "(pip install -r requirements.txt). Expecting secrets to already be "
#               "set as real environment variables.")
#         return

#     env_path = REPO_ROOT / ".env"
#     if not env_path.exists():
#         print(f"[run_backend] No .env file found at {env_path}. "
#               f"Copy .env.example to .env and fill in your values if you need "
#               f"OPENROUTER_API_KEY, EMAIL_SENDER_PASSWORD, or database credentials.")
#         return

#     load_dotenv(env_path)
#     print(f"[run_backend] Loaded environment variables from {env_path}")

#     missing = [k for k in ("OPENROUTER_API_KEY",) if not os.environ.get(k)]
#     if missing:
#         print(f"[run_backend] WARNING: missing recommended variables: {missing}. "
#               f"LLM report generation will fail until OPENROUTER_API_KEY is set in .env.")


# # ==================================================================
# # 2. SYSTEM DEPENDENCIES (redis-server, ffmpeg) — CHECK ONLY, no install
# # ==================================================================
# def check_system_deps() -> None:
#     problems = []

#     if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
#         problems.append(
#             "ffmpeg/ffprobe not found on PATH.\n"
#             "    Windows : winget install Gyan.FFmpeg   (then open a NEW terminal)\n"
#             "              or download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH\n"
#             "    macOS   : brew install ffmpeg\n"
#             "    Linux   : sudo apt-get install ffmpeg"
#         )

#     if shutil.which("redis-server") is None and not _redis_reachable():
#         problems.append(
#             "Redis is not installed/running (used by the video service's job queue).\n"
#             "    Windows : easiest is Docker: docker run -d -p 6379:6379 redis\n"
#             "              (native Windows builds: https://github.com/tporadowski/redis/releases,\n"
#             "              or use WSL2 and install redis-server there)\n"
#             "    macOS   : brew install redis && brew services start redis\n"
#             "    Linux   : sudo apt-get install redis-server && sudo systemctl start redis-server"
#         )

#     if problems:
#         print("\n[run_backend] MISSING SYSTEM DEPENDENCIES:\n")
#         for i, p in enumerate(problems, 1):
#             print(f"  {i}. {p}\n")
#         sys.exit("[run_backend] Install the above, then re-run `python run_backend.py`.")


# def _redis_reachable(host: str = "localhost", port: int = 6379) -> bool:
#     try:
#         with socket.create_connection((host, port), timeout=1):
#             return True
#     except OSError:
#         return False


# def start_redis_if_needed() -> Optional[subprocess.Popen]:
#     """
#     If nothing is already listening on 6379, try to start a local
#     redis-server process (works if it's installed natively, e.g. via WSL,
#     Homebrew, or a Windows Redis build). If Redis is already reachable
#     (e.g. started via Docker or a system service beforehand), do nothing.
#     """
#     if _redis_reachable():
#         print("[run_backend] Redis already running on localhost:6379 — reusing it.")
#         return None

#     if shutil.which("redis-server") is None:
#         # check_system_deps() already exited if this were fatal; getting
#         # here means _redis_reachable() was false but redis-server also
#         # wasn't found — check_system_deps() should have caught this, but
#         # guard anyway.
#         return None

#     print("[run_backend] Starting local redis-server on port 6379...")
#     proc = subprocess.Popen(
#         ["redis-server", "--port", "6379"],
#         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
#     )
#     _wait_for_port("localhost", 6379, timeout=30)
#     return proc


# # ==================================================================
# # 3. GENERIC HELPERS
# # ==================================================================
# def _wait_for_port(host: str, port: int, timeout: int = 120) -> None:
#     deadline = time.time() + timeout
#     while time.time() < deadline:
#         try:
#             with socket.create_connection((host, port), timeout=2):
#                 return
#         except OSError:
#             time.sleep(1)
#     raise TimeoutError(f"Port {port} on {host} did not open within {timeout}s")


# def _wait_for_http_health(url: str, timeout: int, require_field: str = None) -> None:
#     """
#     Poll `url` until it returns HTTP 200. If `require_field` is given, also
#     parse the JSON body and require that field to be truthy (used for
#     audio_service's /health, which returns 200 as soon as the port is
#     open, with a separate `models_loaded` flag that flips to true once the
#     background model download/load finishes).
#     """
#     import json
#     import urllib.request
#     deadline = time.time() + timeout
#     last_err = None
#     while time.time() < deadline:
#         try:
#             with urllib.request.urlopen(url, timeout=5) as resp:
#                 if resp.status == 200:
#                     if require_field is None:
#                         return
#                     body = json.loads(resp.read())
#                     if body.get(require_field):
#                         return
#                     last_err = f"{require_field}={body.get(require_field)!r} (still loading)"
#         except Exception as e:
#             last_err = e
#         time.sleep(3)
#     raise TimeoutError(f"{url} did not become healthy within {timeout}s (last error: {last_err})")


# def start_service(name: str, cwd: Path, module: str, port: int, extra_env: dict = None) -> subprocess.Popen:
#     """Launch `python -m uvicorn <module>:app --host 0.0.0.0 --port <port>` in cwd."""
#     env = os.environ.copy()
#     if extra_env:
#         env.update(extra_env)

#     log_path = REPO_ROOT / f"{name}.log"
#     log_file = open(log_path, "w")

#     print(f"[run_backend] Starting {name} (port {port}, cwd={cwd})... logs -> {log_path}")
#     proc = subprocess.Popen(
#         [sys.executable, "-m", "uvicorn", f"{module}:app",
#          "--host", "0.0.0.0", "--port", str(port), "--log-level", "info"],
#         cwd=str(cwd),
#         env=env,
#         stdout=log_file,
#         stderr=subprocess.STDOUT,
#     )
#     return proc


# # ==================================================================
# # 4. MAIN
# # ==================================================================
# def main():
#     load_dotenv_file()
#     check_system_deps()

#     procs = []

#     def _cleanup(*_):
#         print("\n[run_backend] Shutting down all services...")
#         for p in procs:
#             try:
#                 p.terminate()
#             except Exception:
#                 pass
#         sys.exit(0)

#     signal.signal(signal.SIGINT, _cleanup)
#     if hasattr(signal, "SIGTERM"):
#         signal.signal(signal.SIGTERM, _cleanup)

#     # -- Redis --------------------------------------------------------
#     redis_proc = start_redis_if_needed()
#     if redis_proc:
#         procs.append(redis_proc)

#     # -- Audio service (port 8001) ------------------------------------
#     # CUDA_VISIBLE_DEVICES="" forces this process to run entirely on CPU —
#     # Whisper's own device-selection code (`"cuda" if torch.cuda.is_available()
#     # else "cpu"`) then picks CPU automatically since no CUDA device is
#     # visible to it. This keeps the audio service off the GPU entirely so
#     # it never competes with the video service (Qwen3-VL) for VRAM, which
#     # is what makes it safe to run audio and video concurrently (see
#     # integrated_pipeline.py). If your machine has no GPU at all, this has
#     # no practical effect either way.
#     audio_proc = start_service(
#         "audio_service", AUDIO_DIR, "pipeline_v3_1_production", 8001,
#         extra_env={"CUDA_VISIBLE_DEVICES": ""},
#     )
#     procs.append(audio_proc)
#     print("[run_backend] Waiting for audio service to load models (first run downloads "
#           "~2.5GB of models — large-v3  — can take 10-20+ min "
#           "depending on your connection)...")
#     _wait_for_http_health("http://localhost:8001/health", timeout=1800, require_field="models_loaded")
#     print("[run_backend] Audio service is healthy.")

#     # -- Video service (port 8002) -------------------------------------
#     video_proc = start_service("video_service", VIDEO_DIR, "app", 8002)
#     procs.append(video_proc)
#     print("[run_backend] Waiting for video service to load Qwen3-VL (can take a few minutes "
#           "the first time it downloads the model)...")
#     _wait_for_http_health("http://localhost:8002/health", timeout=900)
#     print("[run_backend] Video service is healthy.")

#     # -- Orchestrator (port 8000) ---------------------------------------
#     orch_proc = start_service("orchestrator", ORCH_DIR, "integrated_pipeline", 8000)
#     procs.append(orch_proc)
#     print("[run_backend] Waiting for orchestrator to come up...")
#     _wait_for_http_health("http://localhost:8000/health", timeout=120)
#     print("[run_backend] Orchestrator is healthy.")

#     print("\n" + "=" * 70)
#     print("BACKEND IS LIVE AT: http://localhost:8000")
#     print("=" * 70)
#     print(
#         "Next step: start the frontend (in a separate terminal):\n"
#         "  cd Frontend/project_final\n"
#         "  npm install\n"
#         "  npm run dev\n"
#         "\n"
#         "Frontend/project_final/.env should have:\n"
#         "  VITE_BACKEND_URL=http://localhost:8000\n"
#         "(this is already the default in .env.example — no ngrok/tunnel needed locally)\n"
#     )

#     print("[run_backend] All services running. Press Ctrl+C to stop.")

#     try:
#         while True:
#             time.sleep(10)
#             for name, p in (("audio_service", audio_proc), ("video_service", video_proc), ("orchestrator", orch_proc)):
#                 if p.poll() is not None:
#                     print(f"[run_backend] WARNING: {name} exited with code {p.returncode}. Check {name}.log")
#     except KeyboardInterrupt:
#         _cleanup()


# if __name__ == "__main__":
#     main()



















"""
run_backend.py
===============
Single entry point for running the whole backend LOCALLY (Windows/macOS/
Linux) — replaces the old Kaggle-notebook launcher.

    python run_backend.py

It will, in order:
  1. Load secrets/config from a local .env file (see .env.example) into
     environment variables — OPENROUTER_API_KEY, EMAIL_SENDER_PASSWORD,
     DB_* variables, etc.
  2. Check that Redis and ffmpeg are installed and reachable (does NOT
     try to apt-get install anything — this is not a container/notebook).
  3. Start the audio service   (port 8021)
  4. Start the video service   (port 8022)
  5. Start the orchestrator    (port 8020) — this is the one the
     frontend talks to, at http://localhost:8020

Execution order for a single video job is controlled inside
AudioVideoPipeline/Orchestrator/integrated_pipeline.py (run_full_pipeline),
not in this launcher — this launcher only brings the 3 HTTP services up
and waits for them to become healthy.

This script is idempotent-ish: re-running it after a crash will try to
free the ports first. It is NOT meant to be imported — run it directly.
"""

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ==================================================================
# 0. PATHS
# ==================================================================
REPO_ROOT      = Path(__file__).resolve().parent
PIPELINE_ROOT  = REPO_ROOT / "AudioVideoPipeline"
AUDIO_DIR      = PIPELINE_ROOT / "audio_service"
VIDEO_DIR      = PIPELINE_ROOT / "video_service"
ORCH_DIR       = PIPELINE_ROOT / "Orchestrator"
CONFIG_PATH    = PIPELINE_ROOT / "Configuration" / "config.yaml"

for p in (PIPELINE_ROOT, AUDIO_DIR, VIDEO_DIR, ORCH_DIR, CONFIG_PATH):
    if not p.exists():
        sys.exit(f"[run_backend] FATAL: expected path not found: {p}\n"
                  f"Run this script from the repo root (next to AudioVideoPipeline/).")

os.environ["CONFIG_PATH"] = str(CONFIG_PATH)


# ==================================================================
# 1. LOAD .env INTO ENVIRONMENT VARIABLES
# ==================================================================
def load_dotenv_file() -> None:
    """
    Load REPO_ROOT/.env (create it by copying .env.example) into
    os.environ, so OPENROUTER_API_KEY, EMAIL_SENDER_PASSWORD, DB_*, etc.
    reach the audio/video/orchestrator subprocesses started below (they
    inherit os.environ via env=os.environ.copy() in start_service()).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("[run_backend] python-dotenv not installed — skipping .env loading "
              "(pip install -r requirements.txt). Expecting secrets to already be "
              "set as real environment variables.")
        return

    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        print(f"[run_backend] No .env file found at {env_path}. "
              f"Copy .env.example to .env and fill in your values if you need "
              f"OPENROUTER_API_KEY, EMAIL_SENDER_PASSWORD, or database credentials.")
        return

    load_dotenv(env_path)
    print(f"[run_backend] Loaded environment variables from {env_path}")

    missing = [k for k in ("OPENROUTER_API_KEY",) if not os.environ.get(k)]
    if missing:
        print(f"[run_backend] WARNING: missing recommended variables: {missing}. "
              f"LLM report generation will fail until OPENROUTER_API_KEY is set in .env.")


# ==================================================================
# 2. SYSTEM DEPENDENCIES (redis-server, ffmpeg) — CHECK ONLY, no install
# ==================================================================
def check_system_deps() -> None:
    problems = []

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        problems.append(
            "ffmpeg/ffprobe not found on PATH.\n"
            "    Windows : winget install Gyan.FFmpeg   (then open a NEW terminal)\n"
            "              or download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH\n"
            "    macOS   : brew install ffmpeg\n"
            "    Linux   : sudo apt-get install ffmpeg"
        )

    if shutil.which("redis-server") is None and not _redis_reachable():
        problems.append(
            "Redis is not installed/running (used by the video service's job queue).\n"
            "    Windows : easiest is Docker: docker run -d -p 6379:6379 redis\n"
            "              (native Windows builds: https://github.com/tporadowski/redis/releases,\n"
            "              or use WSL2 and install redis-server there)\n"
            "    macOS   : brew install redis && brew services start redis\n"
            "    Linux   : sudo apt-get install redis-server && sudo systemctl start redis-server"
        )

    if problems:
        print("\n[run_backend] MISSING SYSTEM DEPENDENCIES:\n")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}\n")
        sys.exit("[run_backend] Install the above, then re-run `python run_backend.py`.")


def _redis_reachable(host: str = "localhost", port: int = 6379) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def start_redis_if_needed() -> Optional[subprocess.Popen]:
    """
    If nothing is already listening on 6379, try to start a local
    redis-server process (works if it's installed natively, e.g. via WSL,
    Homebrew, or a Windows Redis build). If Redis is already reachable
    (e.g. started via Docker or a system service beforehand), do nothing.
    """
    if _redis_reachable():
        print("[run_backend] Redis already running on localhost:6379 — reusing it.")
        return None

    if shutil.which("redis-server") is None:
        # check_system_deps() already exited if this were fatal; getting
        # here means _redis_reachable() was false but redis-server also
        # wasn't found — check_system_deps() should have caught this, but
        # guard anyway.
        return None

    print("[run_backend] Starting local redis-server on port 6379...")
    proc = subprocess.Popen(
        ["redis-server", "--port", "6379"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _wait_for_port("localhost", 6379, timeout=30)
    return proc


# ==================================================================
# 3. GENERIC HELPERS
# ==================================================================
def _wait_for_port(host: str, port: int, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"Port {port} on {host} did not open within {timeout}s")


def _wait_for_http_health(url: str, timeout: int, require_field: str = None) -> None:
    """
    Poll `url` until it returns HTTP 200. If `require_field` is given, also
    parse the JSON body and require that field to be truthy (used for
    audio_service's /health, which returns 200 as soon as the port is
    open, with a separate `models_loaded` flag that flips to true once the
    background model download/load finishes).
    """
    import json
    import urllib.request
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    if require_field is None:
                        return
                    body = json.loads(resp.read())
                    if body.get(require_field):
                        return
                    last_err = f"{require_field}={body.get(require_field)!r} (still loading)"
        except Exception as e:
            last_err = e
        time.sleep(3)
    raise TimeoutError(f"{url} did not become healthy within {timeout}s (last error: {last_err})")


def start_service(name: str, cwd: Path, module: str, port: int, extra_env: dict = None) -> subprocess.Popen:
    """Launch `python -m uvicorn <module>:app --host 0.0.0.0 --port <port>` in cwd."""
    env = os.environ.copy()
    # Force unbuffered stdout/stderr so progress (e.g. model download %)
    # shows up in the log file in real time instead of being buffered in
    # memory until the process exits (Python fully buffers stdout when
    # it isn't attached to a real terminal, which a redirected log file
    # is not).
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)

    log_path = REPO_ROOT / f"{name}.log"
    log_file = open(log_path, "w", buffering=1)

    print(f"[run_backend] Starting {name} (port {port}, cwd={cwd})... logs -> {log_path}")
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "uvicorn", f"{module}:app",
         "--host", "0.0.0.0", "--port", str(port), "--log-level", "info"],
        cwd=str(cwd),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return proc


# ==================================================================
# 4. MAIN
# ==================================================================
def _cleanup_procs(procs: list) -> None:
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass


def main():
    load_dotenv_file()
    check_system_deps()

    procs = []

    def _cleanup(*_):
        print("\n[run_backend] Shutting down all services...")
        _cleanup_procs(procs)
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _cleanup)

    # -- Redis --------------------------------------------------------
    redis_proc = start_redis_if_needed()
    if redis_proc:
        procs.append(redis_proc)

    # -- Audio service (port 8001) ------------------------------------
    # CUDA_VISIBLE_DEVICES="" forces this process to run entirely on CPU —
    # Whisper's own device-selection code (`"cuda" if torch.cuda.is_available()
    # else "cpu"`) then picks CPU automatically since no CUDA device is
    # visible to it. This keeps the audio service off the GPU entirely so
    # it never competes with the video service (Qwen3-VL) for VRAM, which
    # is what makes it safe to run audio and video concurrently (see
    # integrated_pipeline.py). If your machine has no GPU at all, this has
    # no practical effect either way.
    try:
        audio_proc = start_service(
            "audio_service", AUDIO_DIR, "pipeline_v3_1_production", 8021,
            extra_env={"CUDA_VISIBLE_DEVICES": ""},
        )
        procs.append(audio_proc)
        print("[run_backend] Waiting for audio service to load models (first run downloads "
              "~2.5GB of models — large-v3 —can take 10-20+ min "
              "on a slow connection; subsequent runs reuse the local models/ folder and start "
              "in seconds). Live progress: Get-Content audio_service.log -Wait -Tail 20")
        _wait_for_http_health("http://localhost:8021/health", timeout=3600, require_field="models_loaded")
        print("[run_backend] Audio service is healthy.")

        # -- Video service (port 8022) -------------------------------------
        video_proc = start_service("video_service", VIDEO_DIR, "app", 8022)
        procs.append(video_proc)
        print("[run_backend] Waiting for video service to load Qwen3-VL (can take a few minutes "
              "the first time it downloads the model)...")
        _wait_for_http_health("http://localhost:8022/health", timeout=1800)
        print("[run_backend] Video service is healthy.")

        # -- Orchestrator (port 8020) ---------------------------------------
        orch_proc = start_service("orchestrator", ORCH_DIR, "integrated_pipeline", 8020)
        procs.append(orch_proc)
        print("[run_backend] Waiting for orchestrator to come up...")
        _wait_for_http_health("http://localhost:8020/health", timeout=200)
        print("[run_backend] Orchestrator is healthy.")
    except Exception:
        print("[run_backend] Startup failed — shutting down any services that did start "
              "(so they don't linger as orphaned processes) before exiting.")
        _cleanup_procs(procs)
        raise

    print("\n" + "=" * 70)
    print("BACKEND IS LIVE AT: http://localhost:8020")
    print("=" * 70)
    print(
        "Next step: start the frontend (in a separate terminal):\n"
        "  cd Frontend/project_final\n"
        "  npm install\n"
        "  npm run dev\n"
        "\n"
        "Frontend/project_final/.env should have:\n"
        "  VITE_BUSINESS_MAP_API_BASE_URL=http://localhost:8020\n"
        "(this is already the default in .env.example — no ngrok/tunnel needed locally)\n"
    )

    print("[run_backend] All services running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(10)
            for name, p in (("audio_service", audio_proc), ("video_service", video_proc), ("orchestrator", orch_proc)):
                if p.poll() is not None:
                    print(f"[run_backend] WARNING: {name} exited with code {p.returncode}. Check {name}.log")
    except KeyboardInterrupt:
        _cleanup()


if __name__ == "__main__":
    main()