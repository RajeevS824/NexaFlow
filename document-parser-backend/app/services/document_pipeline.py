"""
document_pipeline.py

Pipeline wrapper module for executing the main document processing pipeline.
"""

from app.services.document_service import process_document


def run_pipeline(
    request_file,
    output_dir,
    cancel_check=None
):
    """
    Execute complete pipeline
    using request-specific workspace.
    """

    return process_document(
        request_file=request_file,
        output_dir=output_dir,
        cancel_check=cancel_check
    )
