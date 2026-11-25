#!/usr/bin/env python3
"""
start_all.py - start every NextFlow backend with one command.

Place this file in the project root, next to:
    Core-App-Backend/   document-parser-backend/   Business-Map-Backend/   .env

Usage:
    python start_all.py                  # start everything
    python start_all.py --local-only     # bind Core + Document Parser to 127.0.0.1
    python start_all.py --only core      # start just one (core, docparser, businessmap)
    python start_all.py --skip businessmap
    python start_all.py --dry-run        # show what would run, start nothing

Ports (unchanged):
    6379 Redis                8001 Core-App-Backend      8000 Document Parser
    8020 Business Map orchestrator (also starts audio 8021 and video 8022)

Logs go to ./logs/. Press Ctrl+C once to stop everything.
"""
import argparse
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
IS_WIN = os.name == "nt"

# pyenv = optional environment variable to point a service at its own Python/venv,
# e.g. set DOCPARSER_PYTHON=C:\envs\docparser\Scripts\python.exe
SERVICES = {
    "core": dict(
        label="Core-App-Backend", cwd=ROOT / "Core-App-Backend", kind="uvicorn",
        module="app.main:app", port=8001, ports=[8001],
        health="http://127.0.0.1:8001/health", timeout=180, pyenv="CORE_PYTHON",
    ),
    "docparser": dict(
        label="Document Parser", cwd=ROOT / "document-parser-backend", kind="uvicorn",
        module="app.main:app", port=8000, ports=[8000],
        health="http://127.0.0.1:8000/health", timeout=900, pyenv="DOCPARSER_PYTHON",
    ),
    "businessmap": dict(
        label="Business Map (orchestrator + audio + video)", cwd=ROOT / "Business-Map-Backend",
        kind="script", script="run_backend.py", port=8020, ports=[8020, 8021, 8022],
        health="http://127.0.0.1:8020/health", timeout=3700, pyenv="BUSINESSMAP_PYTHON",
    ),
}


def load_env(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing variables."""
    if not path.is_file():
        print(f"[start_all] No .env at {path} - using existing environment variables only.")
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        # expand ${NAME} references (e.g. ${HOST_IP}) using variables defined earlier
        value = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), value)
        os.environ.setdefault(key.strip(), value)
    print(f"[start_all] Loaded {path}")


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def redis_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host if host not in ("0.0.0.0",) else "127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    check_host = "127.0.0.1" if host in ("0.0.0.0", "localhost") else host
    while time.time() < deadline:
        if redis_reachable(check_host, port):
            return True
        time.sleep(0.5)
    return False


def start_redis_if_needed(host: str, port: int) -> subprocess.Popen | None:
    check_host = "127.0.0.1" if host in ("0.0.0.0", "localhost") else host
    if redis_reachable(check_host, port):
        print(f"[start_all] Redis already running on {host}:{port} - reusing it.")
        return None

    loopback = host in ("localhost", "127.0.0.1", "0.0.0.0")
    if not loopback:
        sys.exit(f"[start_all] Redis not reachable at {host}:{port} and host is not local; "
                 f"start Redis manually, then re-run.")

    binary = shutil.which("redis-server")
    if binary is None:
        sys.exit("[start_all] redis-server not found on PATH. Install Redis "
                 "(see Business-Map-Backend/LOCAL_SETUP.md) or start it manually, then re-run.")

    LOG_DIR.mkdir(exist_ok=True)
    log = open(LOG_DIR / "redis.log", "a", buffering=1, encoding="utf-8")
    bind_host = "0.0.0.0" if host == "0.0.0.0" else host
    print(f"[start_all] Starting local redis-server on {bind_host}:{port}...")
    kwargs = {}
    if IS_WIN:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [binary, "--bind", bind_host, "--port", str(port), "--daemonize", "no"],
        stdout=log, stderr=subprocess.STDOUT, **kwargs,
    )
    if not wait_for_port(host, port, 30):
        stop(proc)
        sys.exit("[start_all] redis-server did not become ready on port "
                 f"{port} within 30s. See logs/redis.log.")
    print(f"[start_all] Started Redis (pid {proc.pid}) -> logs/redis.log")
    return proc


def build_command(svc: dict, host: str) -> list:
    py = os.environ.get(svc["pyenv"], sys.executable)
    if svc["kind"] == "uvicorn":
        return [py, "-u", "-m", "uvicorn", svc["module"], "--host", host,
                "--port", str(svc["port"]), "--workers", "1"]
    return [py, "-u", svc["script"]]


def start(name: str, host: str) -> subprocess.Popen:
    svc = SERVICES[name]
    LOG_DIR.mkdir(exist_ok=True)
    log = open(LOG_DIR / f"{name}.log", "a", buffering=1, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    kwargs = {}
    if IS_WIN:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(build_command(svc, host), cwd=str(svc["cwd"]), env=env,
                            stdout=log, stderr=subprocess.STDOUT, **kwargs)
    print(f"[start_all] Started {svc['label']} (pid {proc.pid}) -> logs/{name}.log")
    return proc


def stop(proc: subprocess.Popen) -> None:
    """Stop a service and all of its child processes."""
    if proc.poll() is not None and not IS_WIN:
        return
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
            for _ in range(30):
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def log_tail(name: str, lines: int = 15) -> str:
    try:
        text = (LOG_DIR / f"{name}.log").read_text(encoding="utf-8", errors="ignore")
        return "\n".join(text.splitlines()[-lines:])
    except OSError:
        return "(no log)"


def is_healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Start all NextFlow backends.")
    ap.add_argument("--only", help="comma list: core,docparser,businessmap,redis")
    ap.add_argument("--skip", help="comma list to leave out")
    ap.add_argument("--local-only", action="store_true",
                    help="bind Core and Document Parser to 127.0.0.1 (use behind a reverse proxy)")
    ap.add_argument("--max-restarts", type=int, default=3,
                    help="auto-restart a crashed service this many times (default 3)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    allowed = list(SERVICES) + ["redis"]
    names = list(SERVICES)
    if args.only:
        names = [n.strip() for n in args.only.split(",")]
    if args.skip:
        names = [n for n in names if n not in {s.strip() for s in args.skip.split(",")}]
    bad = [n for n in names if n not in allowed]
    if bad:
        sys.exit(f"[start_all] Unknown service(s): {bad}. Choose from {allowed}")

    host = "127.0.0.1" if args.local_only else "0.0.0.0"
    load_env(ROOT / ".env")

    service_names = [n for n in names if n in SERVICES]
    redis_requested = "redis" in names
    redis_host = os.environ.get("REDIS_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    except ValueError:
        redis_port = 6379
    redis_enabled = os.environ.get("REDIS_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
    need_redis = redis_enabled and (redis_requested or "businessmap" in service_names)

    if need_redis and redis_host in ("localhost", "127.0.0.1", "0.0.0.0"):
        check = "127.0.0.1" if redis_host in ("localhost", "0.0.0.0") else redis_host
        if port_in_use(redis_port) and not redis_reachable(check, redis_port):
            sys.exit(f"[start_all] Port {redis_port} is already in use but Redis is not responding. "
                     f"Stop the process using that port first.")

    for n in service_names:
        svc = SERVICES[n]
        if not svc["cwd"].is_dir():
            sys.exit(f"[start_all] Folder not found: {svc['cwd']} (run from the project root)")
        busy = [p for p in svc["ports"] if port_in_use(p)]
        if busy and not args.dry_run:
            sys.exit(f"[start_all] Port(s) {busy} already in use for {svc['label']}. "
                     f"Stop the old process first.")

    if args.dry_run:
        if need_redis:
            print(f"{'redis':12} host={redis_host:16} port={redis_port} "
                  f"cmd=redis-server --bind {redis_host} --port {redis_port} --daemonize no")
        for n in service_names:
            print(f"{n:12} cwd={SERVICES[n]['cwd'].name:24} cmd={' '.join(build_command(SERVICES[n], host))}")
        return 0

    procs, restarts = {}, {n: 0 for n in service_names}
    redis_proc = None
    redis_restarts = 0

    def shutdown(*_):
        nonlocal redis_proc
        print("\n[start_all] Stopping all services...")
        for p in list(procs.values()):
            stop(p)
        if redis_proc is not None and redis_proc.poll() is None:
            stop(redis_proc)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # Start Redis before the Python services so the Business Map queue is ready.
    if need_redis and not args.dry_run:
        redis_proc = start_redis_if_needed(redis_host, redis_port)
        if redis_proc is not None:
            procs["redis"] = redis_proc

    for n in service_names:               # start everything in parallel, models load at the same time
        procs[n] = start(n, host)

    pending = {n: time.time() + SERVICES[n]["timeout"] for n in service_names}
    if service_names:
        print("[start_all] Waiting for services to become healthy "
              "(the first Business Map start can take 10-20+ minutes while models download)...")
    while pending:
        for n in list(pending):
            if procs[n].poll() is not None:
                print(f"[start_all] {SERVICES[n]['label']} exited during startup:\n{log_tail(n)}")
                shutdown()
            if is_healthy(SERVICES[n]["health"]):
                print(f"[start_all] OK  {SERVICES[n]['label']} is healthy on port {SERVICES[n]['port']}")
                del pending[n]
            elif time.time() > pending[n]:
                print(f"[start_all] {SERVICES[n]['label']} not healthy in time:\n{log_tail(n)}")
                shutdown()
        time.sleep(3)

    print("\n" + "=" * 62)
    print("ALL SERVICES ARE RUNNING")
    if need_redis:
        print(f"  {'Redis':46} {redis_host}:{redis_port}")
    for n in service_names:
        print(f"  {SERVICES[n]['label']:46} http://localhost:{SERVICES[n]['port']}")
    print("Press Ctrl+C to stop everything.")
    print("=" * 62)

    while True:                    # watchdog: restart a crashed service a limited number of times
        time.sleep(5)

        if need_redis and redis_proc is not None:
            if redis_proc.poll() is not None and redis_restarts < args.max_restarts:
                redis_restarts += 1
                print(f"[start_all] Redis stopped "
                      f"(restart {redis_restarts}/{args.max_restarts})")
                stop(redis_proc)
                time.sleep(2)
                redis_proc = start_redis_if_needed(redis_host, redis_port)
                if redis_proc is not None:
                    procs["redis"] = redis_proc
                    wait_for_port(redis_host, redis_port, 30)

        for n in service_names:
            if procs[n].poll() is None:
                continue
            if restarts[n] >= args.max_restarts:
                continue
            restarts[n] += 1
            print(f"[start_all] {SERVICES[n]['label']} stopped (restart {restarts[n]}/{args.max_restarts})")
            stop(procs[n])         # clear any leftover child processes first
            time.sleep(3)
            procs[n] = start(n, host)


if __name__ == "__main__":
    sys.exit(main())
