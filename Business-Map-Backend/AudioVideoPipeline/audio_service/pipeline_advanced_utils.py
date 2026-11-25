#############################################################
# PIPELINE v3.1 - ADVANCED UTILITIES - FULLY FIXED
# All Bugs #1-10 Fixed + All Features Implemented
#############################################################

import os
import asyncio
import subprocess
import logging
import time
import json
import multiprocessing
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

#############################################################
# FIX #1: STREAMING FILE UPLOAD (Memory-Safe)
#############################################################

async def save_upload_file_streaming(
    upload_file,
    destination: str,
    chunk_size: int = 1048576,  # 1MB
    max_file_size: int = 500 * 1024 * 1024
) -> Dict[str, Any]:
    """Save uploaded file in chunks. BUG FIX #4: Creates temp dir."""
    
    total_size = 0
    chunks_written = 0
    
    try:
        # ✅ BUG FIX #4: Ensure directory exists
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        with open(destination, "wb") as buffer:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                
                total_size += len(chunk)
                if total_size > max_file_size:
                    raise ValueError(f"FILE_TOO_LARGE")
                
                buffer.write(chunk)
                chunks_written += 1
        
        logger.info(f"Upload complete: {total_size / (1024*1024):.1f}MB")
        return {
            "success": True,
            "path": destination,
            "size_bytes": total_size,
            "chunks": chunks_written
        }
    
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        if os.path.exists(destination):
            try:
                os.remove(destination)
            except:
                pass
        raise

#############################################################
# FIX #2: SUBPROCESS WITH TIMEOUT + ERROR HANDLING
#############################################################

class JobCancelled(Exception):
    """Raised inside a worker thread when the job was cancelled by the user.

    It is an ordinary Exception subclass so it propagates through the
    run_in_executor() future, but retry helpers must re-raise it instead of
    treating it as a transient failure (see _retry_operation).
    """


class SubprocessExecutor:
    """Execute subprocesses safely with timeout."""
    
    def __init__(self, timeout_sec: int = 30, max_retries: int = 3, log_output: bool = True):
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.log_output = log_output
    
    def _run_once(self, cmd: list, working_dir: Optional[str],
                  cancel_check: Optional[Callable[[], bool]]):
        """One subprocess attempt. Without a cancel_check this is exactly the
        previous subprocess.run() call. With one, the child is polled and
        killed as soon as the job is cancelled."""
        if cancel_check is None:
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_sec,
                check=False,
                text=True,
                cwd=working_dir
            )

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=working_dir
        )
        deadline = time.monotonic() + self.timeout_sec
        try:
            while True:
                if cancel_check():
                    raise JobCancelled("subprocess cancelled by user")
                try:
                    out, err = proc.communicate(timeout=0.5)
                    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(cmd, self.timeout_sec)
        finally:
            if proc.poll() is None:
                proc.kill()
                try:
                    proc.communicate()
                except Exception:
                    pass

    def run(self, cmd: list, working_dir: Optional[str] = None,
            cancel_check: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """Run command with timeout and retry logic.

        cancel_check (optional): callable returning True when the job has been
        cancelled. When given, a running child process is killed and
        JobCancelled is raised; retries are not attempted after a cancel."""
        
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            if cancel_check is not None and cancel_check():
                raise JobCancelled("subprocess cancelled by user")
            try:
                logger.info(f"Subprocess attempt {attempt}/{self.max_retries}: {' '.join(cmd)}")
                
                result = self._run_once(cmd, working_dir, cancel_check)
                
                if result.returncode == 0:
                    if self.log_output and result.stdout:
                        logger.debug(f"Subprocess stdout: {result.stdout[:200]}")
                    return {
                        "success": True,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "return_code": 0,
                        "attempt": attempt
                    }
                else:
                    error_msg = result.stderr[:500] if result.stderr else "Unknown error"
                    last_error = f"SUBPROCESS_FAILED ({result.returncode}): {error_msg}"
                    logger.warning(f"Attempt {attempt} failed: {last_error}")
                    
                    if attempt < self.max_retries:
                        backoff = 2 ** attempt
                        logger.info(f"Retrying in {backoff}s...")
                        time.sleep(backoff)
            
            except JobCancelled:
                raise

            except subprocess.TimeoutExpired:
                last_error = f"SUBPROCESS_TIMEOUT ({self.timeout_sec}s)"
                logger.warning(f"Attempt {attempt} timeout: {last_error}")
                
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
            
            except Exception as e:
                last_error = f"SUBPROCESS_ERROR: {str(e)}"
                logger.error(f"Attempt {attempt} error: {last_error}")
                raise
        
        return {
            "success": False,
            "error": last_error,
            "return_code": 1,
            "attempts": self.max_retries
        }

#############################################################
# FIX #3: DYNAMIC WORKER COUNT
#############################################################

def get_optimal_worker_count(
    min_workers: int = 2,
    max_workers: int = 32,
    multiplier: float = 2.0
) -> int:
    """Calculate optimal workers based on CPU."""
    
    cpu_count = multiprocessing.cpu_count()
    optimal = min(int(cpu_count * multiplier), max_workers)
    optimal = max(optimal, min_workers)
    
    logger.info(f"Optimal workers: {optimal} (cpu_count={cpu_count})")
    return optimal

#############################################################
# FIX #4: DETERMINISTIC DEMUCS OUTPUT PARSING
#############################################################

def get_demucs_vocals_path(output_dir: str) -> str:
    """Extract vocals.wav deterministically (sort by mtime)."""
    
    output_path = Path(output_dir)
    
    if not output_path.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")
    
    # Sort by modification time, take most recent
    dirs = sorted(
        [d for d in output_path.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )
    
    if not dirs:
        raise FileNotFoundError(f"No model directories in {output_dir}")
    
    model_dir = dirs[0]
    track_dirs = sorted([d for d in model_dir.iterdir() if d.is_dir()])
    
    if not track_dirs:
        raise FileNotFoundError(f"No track directories in {model_dir}")
    
    track_dir = track_dirs[0]
    vocals_path = track_dir / "vocals.wav"
    
    if not vocals_path.exists():
        raise FileNotFoundError(f"vocals.wav not found in {track_dir}")
    
    logger.info(f"Found vocals: {vocals_path}")
    return str(vocals_path)

#############################################################
# FIX #5: RATE LIMITING - FIXED (Memory bounded)
#############################################################

class RateLimiter:
    """Token bucket with memory bounds. BUG FIX #2: No memory leak."""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_allowed: int = 10,
        max_identifiers: int = 100000
    ):
        self.requests_per_minute = requests_per_minute
        self.max_identifiers = max_identifiers
        self.tokens: Dict[str, list] = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def check_limit(self, identifier: str) -> Dict[str, Any]:
        """Check if request allowed."""
        
        async with self.lock:
            now = time.time()
            window_start = now - 60
            
            # ✅ BUG FIX #2: Memory cleanup
            if len(self.tokens) > self.max_identifiers:
                logger.warning(f"Rate limiter at capacity, clearing old entries")
                sorted_ids = sorted(
                    self.tokens.keys(),
                    key=lambda x: min(self.tokens[x]) if self.tokens[x] else 0
                )
                for id_to_remove in sorted_ids[:len(sorted_ids) // 4]:
                    del self.tokens[id_to_remove]
            
            # Clean old tokens
            self.tokens[identifier] = [t for t in self.tokens[identifier] if t > window_start]
            
            token_count = len(self.tokens[identifier])
            allowed = token_count < self.requests_per_minute
            
            if allowed:
                self.tokens[identifier].append(now)
                remaining = self.requests_per_minute - token_count - 1
                reset_in = 60 - (now - self.tokens[identifier][0]) if self.tokens[identifier] else 60
            else:
                remaining = 0
                reset_in = 60 - (now - self.tokens[identifier][0])
            
            return {
                "allowed": allowed,
                "remaining": max(0, remaining),
                "reset_in_sec": max(0, reset_in),
                "tokens": token_count
            }

#############################################################
# FIX #6: SAFE LOGGING SETUP
#############################################################

def setup_logger_safe(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None
) -> logging.Logger:
    """Setup logger without duplication."""
    
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(level)
    
    if logger_instance.handlers:
        return logger_instance
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    console_handler.setFormatter(formatter)
    logger_instance.addHandler(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger_instance.addHandler(file_handler)
    
    return logger_instance

#############################################################
# FIX #7: CIRCUIT BREAKER PATTERN
#############################################################

class CircuitBreaker:
    """Circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_sec: int = 60
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
    
    def record_success(self) -> None:
        """Record success."""
        if self.state == "HALF_OPEN":
            logger.info(f"Circuit {self.name}: HALF_OPEN → CLOSED")
            self.state = "CLOSED"
        self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            logger.warning(f"Circuit {self.name}: CLOSED → OPEN ({self.failure_count} failures)")
            self.state = "OPEN"
    
    def check(self) -> bool:
        """Check if operation allowed."""
        
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout_sec:
                logger.info(f"Circuit {self.name}: OPEN → HALF_OPEN")
                self.state = "HALF_OPEN"
                self.failure_count = 0
                return True
            return False
        
        return True  # HALF_OPEN

#############################################################
# FIX #8: SINGLE WORKER VALIDATION
#############################################################

def validate_single_worker_config(workers: int) -> None:
    """Validate workers=1 only."""
    
    if workers > 1:
        raise ValueError(
            f"CRITICAL: FastAPI workers must be 1, got {workers}. "
            f"Scale using Kubernetes instead."
        )
    
    logger.info("✓ Single worker validation passed")

#############################################################
# FIX #9: REDIS QUEUE HANDLER - FULLY FIXED
# BUG FIX #1: Added connect() initialization
# BUG FIX #6: Uses modern redis.asyncio
# BUG FIX #9: Implements result retrieval
#############################################################

class RedisQueueHandler:
    """Redis queue handler with proper async/await."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.redis = None
    
    async def connect(self) -> None:
        """Connect to Redis. ✅ BUG FIX #1: Now properly called."""
        try:
            import redis.asyncio as redis_lib
            
            self.redis = await redis_lib.from_url(
                f"redis://{self.host}:{self.port}/{self.db}",
                password=self.password,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            
            await self.redis.ping()
            logger.info(f"✓ Redis connected: {self.host}:{self.port}")
        
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            try:
                await self.redis.close()
                logger.info("✓ Redis disconnected")
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
    
    async def enqueue_job(
        self,
        job_id: str,
        job_data: Dict[str, Any],
        queue_name: str = "audio_jobs"
    ) -> bool:
        """Enqueue job."""
        
        if not self.redis:
            logger.error("Redis not connected")
            return False
        
        try:
            job_json = json.dumps({
                "id": job_id,
                "data": job_data,
                "timestamp": datetime.now().isoformat(),
                "status": "QUEUED"
            })
            
            await self.redis.lpush(queue_name, job_json)
            logger.info(f"Enqueued job {job_id}")
            return True
        
        except Exception as e:
            logger.error(f"Enqueue failed: {e}")
            return False
    
    async def dequeue_job(
        self,
        queue_name: str = "audio_jobs",
        timeout_sec: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Dequeue job."""
        
        if not self.redis:
            return None
        
        try:
            result = await self.redis.brpop(queue_name, timeout=timeout_sec)
            
            if result:
                job_json = result[1] if isinstance(result, tuple) else result
                job = json.loads(job_json)
                logger.info(f"Dequeued job {job.get('id')}")
                return job
            
            return None
        
        except Exception as e:
            logger.error(f"Dequeue failed: {e}")
            return None
    
    async def store_result(
        self,
        result: Dict[str, Any],
        result_queue: str = "audio_results"
    ) -> bool:
        """✅ BUG FIX #9: Store result in Redis."""
        
        if not self.redis:
            return False
        
        try:
            await self.redis.rpush(result_queue, json.dumps(result))
            logger.info(f"Stored result for job {result.get('id')}")
            return True
        except Exception as e:
            logger.error(f"Store result failed: {e}")
            return False
    
    async def get_result(
        self,
        job_id: str,
        result_queue: str = "audio_results"
    ) -> Optional[Dict[str, Any]]:
        """✅ BUG FIX #9: Retrieve result by job ID."""
        
        if not self.redis:
            return None
        
        try:
            # Get all results and find matching job
            results = await self.redis.lrange(result_queue, 0, -1)
            for result_json in results:
                result = json.loads(result_json)
                if result.get("id") == job_id:
                    return result
            return None
        
        except Exception as e:
            logger.error(f"Get result failed: {e}")
            return None

#############################################################
# FIX #10: CONFIG VALIDATION
#############################################################

def validate_config(config_dict: Dict[str, Any]) -> List[str]:
    """Validate configuration on startup."""
    
    errors = []
    
    required_keys = [
        "models.whisper.name",
        "audio.max_duration_sec",
        "latency_sla.max_inference_sec",
        "deployment.workers"
    ]
    
    for key in required_keys:
        keys = key.split(".")
        value = config_dict
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        
        if value is None:
            errors.append(f"MISSING_CONFIG: {key}")
    
    # Validate workers
    if config_dict.get("deployment", {}).get("workers", 0) > 1:
        errors.append("INVALID_CONFIG: deployment.workers must be 1")
    
    if errors:
        logger.error(f"Config validation failed: {errors}")
    else:
        logger.info("✓ Configuration validation passed")
    
    return errors
