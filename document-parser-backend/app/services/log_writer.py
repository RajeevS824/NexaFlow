"""
log_writer.py — Structured pipeline logging service.

INFO  mode (is_logtolocal=true, log_type=INFO):
    8-column CSV  ->  <log_path>/INFO/<filename>_<jobid>/pipeline.csv
    THIS MODE IS UNCHANGED FROM THE PREVIOUS IMPLEMENTATION.

DEBUG mode (is_logtolocal=true, log_type=DEBUG):
    9-column CSV ->
        <log_path>/DEBUG/<filename>_<jobid>/pipeline.csv
        <log_path>/DEBUG/<filename>_<jobid>/Page_stream_segmentation.csv
        <log_path>/DEBUG/<filename>_<jobid>/page_N/page_pipeline.csv

ERROR mode (is_logtolocal=true, log_type=ERROR):
    Same structure as DEBUG, but only error-level events are written.

checked=False (any log_type):
    Logs are forwarded to the server-side Python logger only.
"""

import csv
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================
# INFO column schema (8 columns) — UNCHANGED
# ============================================================

INFO_LOG_HEADER = [
    "Job ID", "Page No", "Date Time", "Level",
    "Process", "Description", "Status", "Error",
]

# Backward-compat alias
TABLE_LOG_HEADER = INFO_LOG_HEADER


# ============================================================
# DEBUG / ERROR column schema (9 columns)
# ============================================================

DEBUG_LOG_HEADER = [
    "Job ID",         # 1  UUID of the job
    "Page No",        # 2  Page number (0 = job-level)
    "Date Time",      # 3  Timestamp YYYY-MM-DD HH:MM:SS
    "Level",          # 4  DEBUG / INFO / WARNING / ERROR
    "Process",        # 5  High-level pipeline step label
    "Description",    # 6  Human-readable message
    "Output Summary", # 7  Brief description of outputs / result
    "Status",         # 8  Completed / Failed / Skipped / Processing
    "Error",          # 9  Exception / traceback text
]


# ============================================================
# Pipe-delimited helpers (server-side Output/log — INFO only)
# ============================================================

_TABLE_COLUMN_WIDTHS = [
    36,  # Job ID (UUID length)
    8,   # Page No
    19,  # Date Time ("YYYY-MM-DD HH:MM:SS")
    8,   # Level
    22,  # Process
    200, # Description
    10,  # Status
    0,   # Error (last column, unpadded)
]


def _format_table_row(row: dict, pad: str = " | ") -> str:
    page_no_val = str(row.get("page_no", "") or "")
    if page_no_val == "0":
        page_no_val = ""
    parts = [
        str(row.get("job_id", "") or ""),
        page_no_val,
        str(row.get("date_time", "") or ""),
        str(row.get("level", "") or "").upper(),
        str(row.get("process", "") or ""),
        str(row.get("description", "") or ""),
        str(row.get("status", "") or ""),
        str(row.get("error", "") or ""),
    ]
    padded = [
        val.ljust(width) if width else val
        for val, width in zip(parts, _TABLE_COLUMN_WIDTHS)
    ]
    return pad.join(padded)


def _format_table_header(sep: str = " | ") -> str:
    padded_headers = [
        h.ljust(width) if width else h
        for h, width in zip(INFO_LOG_HEADER, _TABLE_COLUMN_WIDTHS)
    ]
    hdr = sep.join(padded_headers)
    sep_line = sep.join(
        "-" * (width if width else len(h))
        for h, width in zip(INFO_LOG_HEADER, _TABLE_COLUMN_WIDTHS)
    )
    return f"{hdr}\n{sep_line}"


# ============================================================
# CSV row formatters
# ============================================================

def _format_csv_row(row: dict) -> list:
    """8-column INFO row (kept for backward compat)."""
    return [
        str(row.get("job_id", "") or ""),
        str(row.get("page_no", "") or ""),
        str(row.get("date_time", "") or ""),
        str(row.get("level", "") or "").upper(),
        str(row.get("process", "") or ""),
        str(row.get("description", "") or ""),
        str(row.get("status", "") or ""),
        str(row.get("error", "") or ""),
    ]


def _format_debug_csv_row(row: dict) -> list:
    """9-column DEBUG/ERROR row."""
    return [
        str(row.get("job_id", "") or ""),
        str(row.get("page_no", "") or ""),
        str(row.get("date_time", "") or ""),
        str(row.get("level", "") or "").upper(),
        str(row.get("process", "") or ""),
        str(row.get("description", "") or ""),
        str(row.get("output_summary", "") or ""),
        str(row.get("status", "") or ""),
        str(row.get("error", "") or ""),
    ]


def _job_id_short(job_id: str) -> str:
    return job_id or "00000000-0000-0000-0000-000000000000"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _init_csv(path: Path, header: list):
    """Create a CSV with header if it does not exist."""
    if not path.exists():
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerow(header)


def _append_csv(path: Path, row: list):
    """Append a single row to a CSV file."""
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerow(row)


# ============================================================
# StructuredLogWriter
# ============================================================

class StructuredLogWriter:
    """
    Writes structured log entries to the appropriate destination.

    INFO  + checked=True  -> <log_path>/INFO/<filename>_<jobid>/pipeline.csv
                             (8-column schema, UNCHANGED)
    DEBUG + checked=True  -> <log_path>/DEBUG/<filename>_<jobid>/
                             pipeline.csv  (9-col, all steps)
                             Page_stream_segmentation.csv  (9-col)
                             page_N/page_pipeline.csv  (9-col, per page)
    ERROR + checked=True  -> same structure as DEBUG, errors only
    Any   + checked=False -> server-side logger (no local CSV written)
    """

    def __init__(
        self,
        log_path: str,
        log_type: str,
        checked: bool,
        job_id: str,
        filename: str = "document",
        output_dir: Optional[str] = None,
    ):
        self.log_path = Path(log_path)
        self.log_type = log_type.upper()
        self.checked = checked
        self.job_id = job_id
        self.filename = filename
        self.short_job_id = _job_id_short(job_id)
        self.output_dir = Path(output_dir) if output_dir else None

        self._server_side: bool = False
        self._log_dir: Optional[Path] = None
        self._pipeline_log_path: Optional[Path] = None
        self._seg_log_path: Optional[Path] = None
        self._page_log_cache: dict = {}  # page_no -> Path
        self._output_page_logs: dict = {}  # page_no -> Path (server-side only)

        # ---- Determine log destination ----------------------------------------
        # ALL logs are stored on the server regardless of the checked flag
        # (is_logtolocal). The browser cannot write to a client-local path,
        # so the client-provided log_path is never used. The log_type still
        # controls which log file is written (info.log / debug.log / error.log).
        self._server_side = True
        if self.output_dir:
            # Job-level pipeline log: output/<model>/<job>/logs/pipeline.log
            self._output_job_log = self.output_dir / "logs" / "pipeline.log"
            self._output_job_log.parent.mkdir(parents=True, exist_ok=True)
            self._init_output_pipeline_log(self._output_job_log)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_pipeline_log(self):
        """(INFO) Initialize pipeline.csv with header."""
        if self._pipeline_log_path and not self._pipeline_log_path.exists():
            _init_csv(self._pipeline_log_path, INFO_LOG_HEADER)

    def _init_output_pipeline_log(self, path: Path):
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                f.write(_format_table_header())
                f.write("\n")

    def _get_output_page_log(self, page_no: int) -> Optional[Path]:
        """Return output/<model>/<job>/page_N/log/<mode>.log path (server-side
        mode only). The file name is determined by the configured log_type:
          info.log  — log_type=INFO  (all entries)
          debug.log — log_type=DEBUG (all entries, most verbose)
          error.log — log_type=ERROR (error entries only)
        All entries that pass the log_type filter are written to this single
        file, preserving the full chronological order within each mode."""
        if not self.output_dir or page_no <= 0 or not self._server_side:
            return None

        # File name is driven by the configured mode, not individual entry level
        log_type = self.log_type.upper()
        if log_type == "ERROR":
            file_key = "error"
        elif log_type == "DEBUG":
            file_key = "debug"
        else:
            file_key = "info"

        if page_no in self._output_page_logs:
            return self._output_page_logs[page_no]

        log_file_name = f"{file_key}.log"
        path = self.output_dir / f"page_{page_no}" / "log" / log_file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_output_pipeline_log(path)
        self._output_page_logs[page_no] = path
        return path

    def _write_to_file(self, filepath: Path, row: dict):
        _append_csv(filepath, _format_csv_row(row))

    def _write_to_output_file(self, filepath: Path, row: dict):
        line = _format_table_row(row)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _log_to_server(self, row: dict):
        from app.core.logger import logger as _srv
        level = row.get("level", "INFO").upper()
        msg = _format_table_row(row)
        if level == "ERROR":
            _srv.error(msg)
        elif level in ("WARN", "WARNING"):
            _srv.warning(msg)
        elif level == "DEBUG":
            _srv.debug(msg)
        else:
            _srv.info(msg)

    def _get_page_log(self, page_no: int) -> Optional[Path]:
        """Return page_N/pipeline.csv path, creating it if needed."""
        if not self.checked or self.log_type not in ("DEBUG", "ERROR"):
            return None
        if page_no in self._page_log_cache:
            return self._page_log_cache[page_no]
        page_dir = self._log_dir / f"page_{page_no}"
        page_dir.mkdir(parents=True, exist_ok=True)
        path = page_dir / "pipeline.csv"
        _init_csv(path, DEBUG_LOG_HEADER)
        self._page_log_cache[page_no] = path
        return path

    # ------------------------------------------------------------------
    # Public API — main log() method
    # ------------------------------------------------------------------

    def log(
        self,
        page_no: int,
        level: str,
        process: str,
        description: str,
        output_summary: str = "",
        status: str = "Completed",
        error: str = "",
    ):
        level_upper = level.upper()

        if self.log_type == "ERROR" and level_upper != "ERROR":
            return

        if self.log_type == "INFO" and level_upper == "DEBUG":
            return

        row = {
            "job_id": self.job_id,
            "page_no": page_no,
            "date_time": _now(),
            "level": level_upper,
            "process": process,
            "description": description,
            "output_summary": output_summary,
            "status": status,
            "error": error,
        }

        if self._server_side:
            self._log_to_server(row)
            if self._output_job_log:
                self._write_to_output_file(self._output_job_log, row)
            if page_no > 0:
                out_page_log = self._get_output_page_log(page_no)
                if out_page_log:
                    self._write_to_output_file(out_page_log, row)
            return

        if self.log_type == "INFO":
            if self._pipeline_log_path:
                _append_csv(self._pipeline_log_path, _format_csv_row(row))
        else:
            if self._pipeline_log_path:
                _append_csv(self._pipeline_log_path, _format_debug_csv_row(row))

            if process == "Page Stream Segmentation" and self._seg_log_path:
                _append_csv(self._seg_log_path, _format_debug_csv_row(row))

            if page_no > 0:
                page_csv = self._get_page_log(page_no)
                if page_csv:
                    _append_csv(page_csv, _format_debug_csv_row(row))

    def bind_step(self, process: str, page_no: int = 0):
        return StepLogger(self, process, page_no)

    def get_kv_logger(self, page_no: int = 0) -> Optional["StepLogger"]:
        return self.bind_step("kv_extraction", page_no=page_no)

    def get_table_logger(self, page_no: int = 0) -> Optional["StepLogger"]:
        return self.bind_step("table_colextraction", page_no=page_no)

    def get_tbl_logger(self, page_no: int = 0) -> Optional["StepLogger"]:
        return self.get_table_logger(page_no=page_no)

    def log_segmentation(
        self,
        level: str = "DEBUG",
        phase: str = "",
        description: str = "",
        status: str = "Completed",
        decision: str = "",
        input_summary: str = "",
        output_summary: str = "",
        error: str = "",
        duration: str = "",
        **kwargs,
    ):
        desc = description
        if phase:
            desc = f"[{phase}] {desc}"
        if decision:
            desc = f"{desc} | Decision: {decision}"
        if duration:
            desc = f"{desc} ({duration}s)"

        summary = output_summary or input_summary

        self.log(
            page_no=0,
            level=level,
            process="Page Stream Segmentation",
            description=desc,
            output_summary=summary,
            status=status,
            error=error,
        )


class StepLogger:
    """Wrapper that exposes standard logging methods bound to a process name."""

    def __init__(self, writer: StructuredLogWriter, process: str, page_no: int = 0):
        self._writer = writer
        self._process = process
        self._page_no = page_no

    def for_page(self, page_no: int) -> "StepLogger":
        return StepLogger(self._writer, self._process, page_no)

    def log(
        self,
        level: str,
        description: str,
        output_summary: str = "",
        status: str = "Completed",
        error: str = "",
        page_no: Optional[int] = None,
    ):
        p = page_no if page_no is not None else self._page_no
        self._writer.log(
            page_no=p,
            level=level,
            process=self._process,
            description=description,
            output_summary=output_summary,
            status=status,
            error=error,
        )

    def set_process(self, process: str):
        self._process = process

    def _emit(self, level: str, msg: str):
        self._writer.log(
            page_no=self._page_no,
            level=level,
            process=self._process,
            description=msg,
            status="Completed" if level not in ("ERROR", "CRITICAL") else "Failed",
        )

    def debug(self, msg, *args, **kwargs):
        self._emit("DEBUG", str(msg) % args if args else str(msg))

    def info(self, msg, *args, **kwargs):
        self._emit("INFO", str(msg) % args if args else str(msg))

    def warning(self, msg, *args, **kwargs):
        self._emit("WARNING", str(msg) % args if args else str(msg))

    def error(self, msg, *args, **kwargs):
        self._emit("ERROR", str(msg) % args if args else str(msg))

    def exception(self, msg, *args, **kwargs):
        tb = traceback.format_exc()
        full = (str(msg) % args if args else str(msg)) + "\n" + tb
        self._emit("ERROR", full)

    def setLevel(self, *a, **kw): pass
    def addHandler(self, *a, **kw): pass
    def removeHandler(self, *a, **kw): pass

    @property
    def handlers(self):
        return []


def create_log_writer_from_settings(
    user_id: str,
    job_id: str,
    filename: str = "document",
    output_dir: Optional[str] = None,
) -> StructuredLogWriter:
    """
    Load user settings from DB and create a StructuredLogWriter.
    Falls back to server-side logging if settings can't be loaded.
    """
    from app.repositories.setting_repository import SettingRepository

    settings = SettingRepository.get_by_user_id(user_id)

    if not settings:
        return StructuredLogWriter(
            log_path="C:\\Program Files\\ONG\\logs",
            log_type="INFO",
            checked=False,
            job_id=job_id,
            filename=filename,
            output_dir=output_dir,
        )

    return StructuredLogWriter(
        log_path=settings["log_path"],
        log_type=settings["log_type"],
        checked=settings["checked"],
        job_id=job_id,
        filename=filename,
        output_dir=output_dir,
    )