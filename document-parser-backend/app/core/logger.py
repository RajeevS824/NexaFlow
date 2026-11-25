import logging
import os
from pathlib import Path


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = None
LOG_FILE = None

# LOG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# LOG FORMAT
# ---------------------------------------------------------

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(module)s | "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------
# LOGGER
# ---------------------------------------------------------

logger = logging.getLogger("document_pipeline")
logger.setLevel(logging.DEBUG)

# Prevent duplicate handlers during FastAPI reload
if not logger.handlers:

    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.DEBUG)
    # console_handler.setFormatter(
    #     logging.Formatter(
    #         LOG_FORMAT,
    #         datefmt=DATE_FORMAT
    #     )
    # )
    # logger.addHandler(console_handler)

    logger.propagate = False



# ---------------------------------------------------------
# CLEAN LOGS FOR NEW PROCESS (KEEP MODEL LOADING ONLY)
# ---------------------------------------------------------

def setup_log_file(log_dir):

    global LOG_DIR, LOG_FILE

    LOG_DIR = Path(log_dir)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    LOG_FILE = LOG_DIR / "pipeline.log"

    # remove old file handlers
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)

    file_handler = logging.FileHandler(
        LOG_FILE,
        mode="a",
        encoding="utf-8"
    )

    file_handler.setLevel(logging.DEBUG)

    file_handler.setFormatter(
        logging.Formatter(
            LOG_FORMAT,
            datefmt=DATE_FORMAT
        )
    )

    logger.addHandler(file_handler)

    logger.info("=" * 80)
    logger.info("NEW PROCESS STARTED")
    logger.info("=" * 80)


    
# ---------------------------------------------------------
# OPTIONAL WORKSPACE CLEANUP
# CALL THIS INSIDE PIPELINE, NOT ON IMPORT
# ---------------------------------------------------------

def prepare_workspace(output_dir: str | Path):
    """
    Creates required output folders for a pipeline run.

    Example:
        prepare_workspace("./output")
    """

    output_dir = Path(output_dir)

    (output_dir / "logs").mkdir(
        parents=True,
        exist_ok=True
    )

    (output_dir / "json").mkdir(
        parents=True,
        exist_ok=True
    )

    (output_dir / "table").mkdir(
        parents=True,
        exist_ok=True
    )

    (output_dir / "images").mkdir(
        parents=True,
        exist_ok=True
    )

    logger.info(
        f"Workspace prepared → {output_dir}"
    )


class ListHandler(logging.Handler):
    """Collects log records into a list instead of writing immediately."""
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)

def make_buffered_logger(name: str) -> tuple[logging.Logger, ListHandler]:
    """
    Returns a (logger, handler) pair.
    The logger writes only to the ListHandler — nothing goes to disk yet.
    Call flush_buffered_logger() when ready to persist.
    """
    buf_handler = ListHandler()
    buf_handler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)  
    )
    buf_logger = logging.getLogger(name)
    buf_logger.handlers = [buf_handler]   # replace any inherited handlers
    buf_logger.propagate = False           # don't leak to root logger
    buf_logger.setLevel(logging.DEBUG)
    return buf_logger, buf_handler

def flush_buffered_logger(handler: ListHandler, target_logger: logging.Logger):
    """
    Replay all buffered records into target_logger (your real file logger).
    Call this from the main thread after parallel tasks complete.
    """
    for record in handler.records:
        target_logger.handle(record)
    handler.records.clear()