"""
paths.py — Centralized path helpers for the output directory structure.

All output paths are derived from OUTPUT_ROOT (configurable via env var).
The directory structure is:

    output/<model_name>/<job_id>/
        extractedoutput/             (all generated CSV files)
        logs/                        (job-level pipeline log)
        request/request.json
        page_1/
            images/          (enhanced + annotated images for page 1)
            log/             (per-page log files, split by log type)
            response/        (raw.json, response.json)
            tables_image/    (extracted table crop images)
            tables_html/     (generated table HTML files)
        page_2/
            ...
"""

from pathlib import Path
from app.core.config import OUTPUT_ROOT


def model_dir(model_name: str) -> Path:
    """Return the model root directory: output/<model_name>/"""
    return Path(OUTPUT_ROOT) / model_name


def job_dir(model_name: str, job_id: str) -> Path:
    """Return the root directory for a job: output/<model_name>/<job_id>/"""
    return model_dir(model_name) / job_id


def extracted_output_dir(model_name: str, job_id: str) -> Path:
    """Return the extracted-output directory for a job:
    output/<model_name>/<job_id>/extractedoutput/"""
    return job_dir(model_name, job_id) / "extractedoutput"


def logs_dir(model_name: str, job_id: str) -> Path:
    """Return the job-level logs directory:
    output/<model_name>/<job_id>/logs/"""
    return job_dir(model_name, job_id) / "logs"


def request_dir(model_name: str, job_id: str) -> Path:
    """Return the request directory for a job:
    output/<model_name>/<job_id>/request/"""
    return job_dir(model_name, job_id) / "request"


def request_file(model_name: str, job_id: str) -> Path:
    """Return the request.json path:
    output/<model_name>/<job_id>/request/request.json"""
    return request_dir(model_name, job_id) / "request.json"


def page_dir(model_name: str, job_id: str, page_num: int) -> Path:
    """Return the directory for a specific page:
    output/<model_name>/<job_id>/page_<N>/"""
    return job_dir(model_name, job_id) / f"page_{page_num}"


def page_images_dir(model_name: str, job_id: str, page_num: int) -> Path:
    """Return the images directory for a page:
    output/<model_name>/<job_id>/page_<N>/images/"""
    return page_dir(model_name, job_id, page_num) / "images"


def page_log_dir(model_name: str, job_id: str, page_num: int) -> Path:
    """Return the log directory for a page:
    output/<model_name>/<job_id>/page_<N>/log/"""
    return page_dir(model_name, job_id, page_num) / "log"


def page_response_dir(model_name: str, job_id: str, page_num: int) -> Path:
    """Return the response directory for a page:
    output/<model_name>/<job_id>/page_<N>/response/"""
    return page_dir(model_name, job_id, page_num) / "response"


def page_tables_html_dir(model_name: str, job_id: str, page_num: int) -> Path:
    """Return the tables_html directory for a page:
    output/<model_name>/<job_id>/page_<N>/tables_html/"""
    return page_dir(model_name, job_id, page_num) / "tables_html"


def page_tables_image_dir(model_name: str, job_id: str, page_num: int) -> Path:
    """Return the tables_image directory for a page:
    output/<model_name>/<job_id>/page_<N>/tables_image/"""
    return page_dir(model_name, job_id, page_num) / "tables_image"


def relative_image_path(model_name: str, job_id: str, page_num: int, filename: str) -> str:
    """Return a relative path string like
    '<model_name>/<job_id>/page_<N>/images/<filename>'
    suitable for storing in the database and constructing frontend URLs."""
    return f"{model_name}/{job_id}/page_{page_num}/images/{filename}"


def relative_response_path(model_name: str, job_id: str, page_num: int, filename: str = "response.json") -> str:
    """Return a relative path string like
    '<model_name>/<job_id>/page_<N>/response/<filename>'."""
    return f"{model_name}/{job_id}/page_{page_num}/response/{filename}"