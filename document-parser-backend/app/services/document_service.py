# document_service.py

import json
import logging
import os
import shutil
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import copy



from app.core.logger import logger, setup_log_file, make_buffered_logger, flush_buffered_logger
from app.core.global_state import get_current_user_id
from app.services.log_writer import create_log_writer_from_settings, StructuredLogWriter
from app.core.paths import (
    page_images_dir,
    page_response_dir,
    page_tables_html_dir,
    page_tables_image_dir,
    relative_image_path,
)

# OCR PIPELINE MODULES
from app.services.region_layout import process_layout
from app.services.table_det_rec import process_table_visuals
from app.services.docling import convert_document, run_table_pipeline_from_ocr_json

from app.services.response import annotate_invoice, response

from app.services.keyvalue_extraction import (
    main as run_keyvalue_extraction,
)

from app.services.table_colextraction import (
    main as run_table_extraction,
)

from app.services.image_enhancement import process_input_file
from app.services.rotation_correction import correct_rotation

from app.services.page_stream_segmentation import run_segmentation


# ============================================================
# JSON SAFETY NET
# ============================================================
# Defense-in-depth: the primary fix for numpy.float32 leaking into
# raw.json/response.json is in vision_backbones.py's LayoutDetector.detect()
# (cast to float() before round()). This default= handler is a fallback so
# that if ANY other model wrapper (region_layout.py, table_det_rec.py, etc.)
# ever returns a numpy scalar/array without casting it first, json.dump()
# converts it instead of crashing the whole request with a 500.
def _json_safe_default(o):
    import numpy as _np

    if isinstance(o, _np.generic):
        return o.item()
    if isinstance(o, _np.ndarray):
        return o.tolist()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


def _json_dump(obj, f):
    json.dump(obj, f, indent=4, ensure_ascii=False, default=_json_safe_default)



class PipelineCancelledException(Exception):
    """Raised when client disconnects or cancels the pipeline."""
    pass


def process_document(request_file, output_dir, cancel_check=None):
    """Main OCR Pipeline.

    Option A parallelism (per page):
      - Layout detection and Docling run concurrently
      - table_det_rec's process_table_visuals() (classification + cell
        detection) waits for Docling, which now returns tables already
        merged (html/column_wise/row_wise/cells + crop metadata in one
        list per table)
      - Docling's own OCR (PaddleOCR PP-OCRv5, run inside convert_document)
        provides the page's OCR tokens

    Remaining steps (raw/response + KV/table extraction + annotation)
    keep existing behavior.
    """

    # Track total execution time
    pipeline_start = time.perf_counter()

    logger.info("=" * 80)
    logger.info("DOCUMENT PROCESSING PIPELINE STARTED")
    logger.info("=" * 80)

    # ========================================================
    # STEP 0 : READ REQUEST.JSON
    # ========================================================
    logger.info("Loading request configuration")

    with open(request_file, "r", encoding="utf-8") as f:
        request_data = json.load(f)

    document_info = request_data["document"]

    file_name = document_info["file_name"]
    file_path = document_info["url"]
    table_rec = request_data.get("tables", {}).get("enabled", False)

    logger.info(f"Document Name : {file_name}")
    logger.info(f"Input File    : {file_path}")
    logger.info(f"Table OCR     : {table_rec}")

    # ========================================================
    # LOAD LOGGING SETTINGS FROM REQUEST (or fallback to DB)
    # ========================================================
    OUTPUT_DIR = Path(output_dir)
    JOB_ID     = OUTPUT_DIR.name
    # OUTPUT_DIR is Output/<model_name>/<job_id>/ — the parent directory
    # name is the model_name.
    MODEL_NAME = OUTPUT_DIR.parent.name

    user_id = request_data.get("user_id") or get_current_user_id()

    # All logs are always stored on the server. Only logging_type
    # (INFO/DEBUG/ERROR) is read from the request to decide which log
    # file is written. logging_path and is_logtolocal are ignored.
    logging_type = request_data.get("logging_type")

    if logging_type is not None:
        log_writer = StructuredLogWriter(
            log_path="",
            log_type=logging_type,
            checked=False,
            job_id=JOB_ID,
            filename=file_name,
            output_dir=str(OUTPUT_DIR),
        )
    else:
        # Fallback: load logging_type from database settings
        log_writer = create_log_writer_from_settings(
            user_id=user_id,
            job_id=JOB_ID,
            filename=file_name,
            output_dir=str(OUTPUT_DIR),
        )
    log_writer.log(
        page_no=0,
        level="INFO",
        process="document_service",
        description="DOCUMENT PROCESSING PIPELINE STARTED",
        status="Started",
    )
    log_writer.log(
        page_no=0,
        level="INFO",
        process="document_service",
        description=f"Document Name: {file_name}",
        status="Completed",
    )

    # Helper: emit a DEBUG entry only when log_type is DEBUG
    def _dlog(page_no: int, process: str, description: str, output_summary: str = "", status: str = "Completed", error: str = ""):
        if log_writer.log_type == "DEBUG":
            log_writer.log(
                page_no=page_no,
                level="DEBUG",
                process=process,
                description=description,
                output_summary=output_summary,
                status=status,
                error=error,
            )

    # ========================================================
    # CREATE OUTPUT DIRECTORIES
    # ========================================================

    # OUTPUT_DIR is Output/<job_id> (job_id is generated once per request by
    # the API layer -- see app/api/routes/document.py). Nothing here uses the
    # source file name or a timestamp for folder naming anymore.
    #
    # Final layout -- everything is per-page, only Request/ is job-level
    # because there is exactly one request.json per job:
    #   Output/<job_id>/
    #     Request/request.json
    #     page_1/
    #       images/          (enhanced + rotated + annotated image for page 1)
    #       log/             (pipeline log -- see note below)
    #       response/        (raw.json, response.json for page 1 only)
    #       tables_html/     (table HTML for tables on page 1)
    #       tables_image/    (table crop images for page 1)
    #     page_2/
    #       ...
    #
    # NOTE on "log": the pipeline logger is a single stream shared across
    # every step (config load, batch image enhancement, per-page layout/OCR,
    # cross-page KV/table extraction). It can't be cleanly split by page
    # while it's being written, so we log to a scratch file for the whole
    # run and copy the COMPLETE run log into every page's log/ folder at
    # the end. Each page_n/log/pipeline.log therefore contains the full
    # pipeline log, not just that page's slice of it.

    print("OUTPUT_DIR =", OUTPUT_DIR.resolve())

    # Scratch working dir -- deleted at the end of a successful run. Used to
    # hold the live log file and the combined (all-pages) raw/response JSON
    # that response()/kv/table-extraction need to operate across pages;
    # final per-page copies are written into page_n/response/ afterwards.
    TMP_DIR = OUTPUT_DIR / "_tmp"
    TMP_LOG_DIR = TMP_DIR / "Log"
    os.makedirs(TMP_LOG_DIR, exist_ok=True)

    setup_log_file(TMP_LOG_DIR)

    logger.info("=" * 80)
    logger.info("DOCUMENT PROCESSING PIPELINE STARTED")
    logger.info("=" * 80)

    JSON_DIR = TMP_DIR / "Response"

    # Staging folder for image_enhancement's initial batch output, before each
    # page's image is moved into the per-page images/ folder.
    STAGING_DIR = TMP_DIR / "_staging_images"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(JSON_DIR, exist_ok=True)
    os.makedirs(STAGING_DIR, exist_ok=True)

    # ========================================================
    # STEP 1 : IMAGE ENHANCEMENT
    # ========================================================
    logger.info("STEP 1 : Image Enhancement")
    if cancel_check and cancel_check():
        raise PipelineCancelledException("Pipeline cancelled by client disconnect")
    enhanced_image_paths = process_input_file(file_path, str(STAGING_DIR))
    logger.info(f"Enhanced Images Generated : {len(enhanced_image_paths)}")
    log_writer.log(
        page_no=0, level="INFO", process="image_enhancement",
        description=f"Image enhancement completed ({len(enhanced_image_paths)} page(s))",
        status="Completed",
        output_summary=f"{len(enhanced_image_paths)} enhanced image(s) generated",
    )
    for idx, img_path in enumerate(enhanced_image_paths, start=1):
        log_writer.log(page_no=idx, level="INFO", process="image_enhancement", description=f"Page {idx} enhanced image: {Path(img_path).name}", status="Completed")
        _dlog(idx, "image_enhancement", f"Enhanced image path: {img_path}", output_summary=f"Size: {Path(img_path).stat().st_size} bytes" if Path(img_path).exists() else "")

    # ------------------------------------------------------------------
    # Move each page's enhanced image out of the staging folder into
    # its per-page images/ directory (Output/<job_id>/page_N/images/)
    # and rename it to <job_id>_<original_basename>_page_<n>.png so the
    # job_id is always embedded in the filename.
    # ------------------------------------------------------------------
    original_base = Path(file_name).stem   # e.g. "AA_INV_001"
    page_image_map = {}  # page_no -> {"path": str, "filename": str}
    for page_no, image_path in enumerate(enhanced_image_paths, start=1):
        new_name = f"{JOB_ID}_{original_base}_page_{page_no}.png"
        page_img_dir = page_images_dir(MODEL_NAME, JOB_ID, page_no)
        os.makedirs(page_img_dir, exist_ok=True)
        dest_path = page_img_dir / new_name
        shutil.move(image_path, str(dest_path))
        page_image_map[page_no] = {"path": str(dest_path), "filename": new_name}

    try:
        STAGING_DIR.rmdir()
    except OSError:
        pass  # non-empty (e.g. leftover temp files) -- safe to leave behind

    # ========================================================
    # STEP 2 : ROTATION CORRECTION (operate on per-page images)
    # ========================================================
    logger.info("STEP 2 : Rotation Correction")
    for pno in sorted(page_image_map.keys()):
        image_path = page_image_map[pno]["path"]
        if cancel_check and cancel_check():
            raise PipelineCancelledException("Pipeline cancelled by client disconnect")
        logger.info(f"Correcting Rotation : {image_path}")
        correct_rotation(image_path)
        log_writer.log(page_no=pno, level="INFO", process="rotation_correction", description=f"Rotation corrected (0°)", status="Completed")
        _dlog(pno, "rotation_correction", f"Input image: {image_path}", output_summary="No rotation applied (0°)")
    logger.info("Rotation Correction Completed")
    log_writer.log(
        page_no=0, level="INFO", process="rotation_correction",
        description="Rotation correction completed", status="Completed",
        output_summary=f"{len(page_image_map)} page(s) rotation-corrected",
    )

    # ========================================================
    # STEP 3 : PARALLEL EXTRACTION
    # ========================================================

    all_results = []

    for page_no in sorted(page_image_map.keys()):
        image_path = page_image_map[page_no]["path"]
        if cancel_check and cancel_check():
            raise PipelineCancelledException("Pipeline cancelled by client disconnect")
        logger.info(f"Processing Page {page_no}/{len(page_image_map)}")
        log_writer.log(page_no=page_no, level="INFO", process="document_service", description=f"Processing Page {page_no}/{len(page_image_map)}", status="Processing")

        PAGE_DIR = OUTPUT_DIR / f"page_{page_no}"
        PAGE_TABLE_HTML_DIR = page_tables_html_dir(MODEL_NAME, JOB_ID, page_no)
        PAGE_TABLE_IMAGE_DIR = page_tables_image_dir(MODEL_NAME, JOB_ID, page_no)
        os.makedirs(PAGE_TABLE_HTML_DIR, exist_ok=True)
        os.makedirs(PAGE_TABLE_IMAGE_DIR, exist_ok=True)

        with ThreadPoolExecutor(max_workers=2) as page_executor:

            logger.info(f"-------Processing Layout---------")
            future_layout = page_executor.submit(
                process_layout,
                image_path,
                cancel_check,
            )
            logger.info(f"-------Processing docling---------")
            future_docling = page_executor.submit(
                convert_document,
                image_path=image_path,
                table_html_dir=str(PAGE_TABLE_HTML_DIR),
                table_image_dir=str(PAGE_TABLE_IMAGE_DIR),
                tables_enabled=table_rec,
                cancel_check=cancel_check,

            )

            layout_results = future_layout.result()
            full_doc_result = future_docling.result()

        log_writer.log(page_no=page_no, level="INFO", process="layout_detection", description=f"Page {page_no}: Layout detection completed ({len(layout_results.get('region_layout', []))} regions)", status="Completed")
        # DEBUG: emit per-region details
        for r_idx, region in enumerate(layout_results.get("region_layout", []), start=1):
            _dlog(page_no, "layout_detection",
                  f"Region {r_idx}: label={region.get('label','?')}, score={region.get('score', 0.0):.4f}, bbox={region.get('coordinate', [])}",
                  output_summary=f"label={region.get('label','?')}")

        # ------------------------------
        # Merge heron's full layout detections (docling-layout-heron,
        # run inside convert_document) into the SAME layout dict that
        # process_layout() produced. layout_results already has
        # block_layout / region_layout (from a different model, in
        # region_layout.py); docling_layout is added alongside them as
        # its own node, not a replacement.
        # ------------------------------
        docling_layout = full_doc_result.get("docling_layout", [])
        region_layout = layout_results.get("region_layout", [])

        # ----------------------------------------------------------
        # FALLBACK TABLE DETECTION
        #
        # If Heron (docling_layout) contains no "Table" nodes but
        # region_layout (from PP-DocLayout_plus-L) has one or more
        # entries with label "table", use the region_layout table
        # detections as a fallback:
        #
        #   1. Create synthetic docling_layout nodes from each
        #      region_layout "table" entry (convert coordinate → bbox,
        #      round to 1 decimal place). This ALWAYS happens so that
        #      raw.json's docling_layout reflects the region_layout
        #      table detections even when tables are disabled.
        #   2. Only when table_rec is enabled, re-run the TableFormer
        #      pipeline (structure recognition + cropping + export)
        #      using the fallback bboxes and update
        #      full_doc_result["tables"].
        #
        # If Heron already detects one or more tables, the fallback
        # is completely skipped and Heron's output is used as-is.
        # ----------------------------------------------------------
        has_heron_tables = any(
            d.get("label") == "Table" for d in docling_layout
        )
        if not has_heron_tables:
            region_tables = [
                r for r in region_layout if r.get("label") == "table"
            ]
            if region_tables:
                logger.info(
                    f"[fallback] Heron detected no tables; "
                    f"using {len(region_tables)} table(s) from region_layout"
                )

                # Step 1: Create synthetic docling_layout nodes
                # (always done, regardless of table_rec, so that
                #  raw.json's docling_layout is populated correctly)
                for rt in region_tables:
                    coord = rt["coordinate"]  # [x1, y1, x2, y2]
                    bbox = [
                        round(coord[0], 1),
                        round(coord[1], 1),
                        round(coord[2], 1),
                        round(coord[3], 1),
                    ]
                    docling_layout.append({
                        "label": "Table",
                        "score": rt.get("score", 0.0),
                        "bbox": bbox,
                    })

                # Step 2: Only run TableFormer pipeline if tables
                # are enabled in the request
                if table_rec:
                    fallback_bboxes = [
                        d["bbox"] for d in docling_layout if d["label"] == "Table"
                    ]
                    ocr_json = full_doc_result.get("ocr", [])
                    if ocr_json and fallback_bboxes:
                        try:
                            fallback_tables = run_table_pipeline_from_ocr_json(
                                image_path=image_path,
                                ocr_json=ocr_json,
                                table_bboxes=fallback_bboxes,
                                table_html_dir=str(PAGE_TABLE_HTML_DIR),
                                table_image_dir=str(PAGE_TABLE_IMAGE_DIR),
                                cancel_check=cancel_check,
                            )
                            full_doc_result["tables"] = fallback_tables
                            logger.info(
                                f"[fallback] Processed {len(fallback_tables)} "
                                f"table(s) from region_layout via TableFormer"
                            )
                        except Exception as exc:
                            logger.error(
                                f"[fallback] TableFormer pipeline failed for "
                                f"region_layout tables: {exc}"
                            )

        # ALWAYS assign docling_layout back to layout_results,
        # regardless of whether fallback ran or not, so that
        # raw.json always contains the full docling_layout
        # (including any synthetic table nodes from fallback).
        layout_results["docling_layout"] = docling_layout

        # ------------------------------
        # OCR (produced by docling.py's convert_document, alongside tables)
        # ------------------------------
        final_ocr = full_doc_result.get("ocr", [])

        # ------------------------------
        # TABLE EXTRACTION (depends on docling)
        # ------------------------------
        # docling.py's convert_document() now returns a single, already-
        # merged "tables" list -- html/column_wise/row_wise/cells (from
        # TableFormer) and crop_path/table_bbox/table_offset/padding (from
        # the crop step) are built together in the same loop, in the same
        # order, so there's nothing left to zip/merge here. table_type is
        # None and visual_cells is [] until STEP 6's process_table_visuals()
        # runs classification + cell detection (only when tables.enabled ==
        # true; when false, convert_document() skipped layout detection and
        # TableFormer entirely, so "tables" is already []).
        table_results = full_doc_result.get("tables", [])

        log_writer.log(page_no=page_no, level="INFO", process="docling", description=f"Page {page_no}: Docling conversion completed ({len(final_ocr)} OCR items, {len(table_results)} tables)", status="Completed")
        # DEBUG: emit per-OCR-item and table details
        _dlog(page_no, "docling", f"OCR tokens: {len(final_ocr)}, Tables detected: {len(table_results)}",
              output_summary=f"docling_layout regions: {len(layout_results.get('docling_layout', []))}")
        for t_idx, tbl in enumerate(table_results, start=1):
            _dlog(page_no, "docling", f"Table {t_idx}: bbox={tbl.get('table_bbox', [])}, type={tbl.get('table_type', 'unknown')}",
                  output_summary=f"cells={len(tbl.get('cells', []))}")

        all_results.append(
            {
                "image": image_path,
                "layout": layout_results,
                "ocr": final_ocr,
                "tables": table_results,
            }
        )

    logger.info("OCR Processing Completed")
    log_writer.log(
        page_no=0, level="INFO", process="document_service",
        description=f"OCR processing completed for {len(all_results)} page(s)",
        status="Completed",
        output_summary=f"{len(all_results)} page(s) processed",
    )


    # ========================================================
    # STEP 4 : SAVE RAW OCR OUTPUT
    # ========================================================
    logger.info("Saving Raw OCR Output")
    raw_json_path = JSON_DIR / "raw.json"

    with open(raw_json_path, "w", encoding="utf-8") as f:
        _json_dump(all_results, f)

    logger.info(f"Raw Output Saved : {raw_json_path}")

    # ========================================================
    # STEP 4.5 : PAGE STREAM SEGMENTATION (multi-page only)
    # ========================================================
    groups_info = None
    if len(all_results) > 1:
        logger.info("STEP 4.5 : Page Stream Segmentation")
        groups_info = run_segmentation(
            all_results=all_results,
            job_id=JOB_ID,
            output_dir=OUTPUT_DIR,
            log_writer=log_writer,
        )
        logger.info("Page Stream Segmentation Completed")
        logger.info("Groups: %s", [[g + 1 for g in grp] for grp in groups_info["groups"]])
        groups_str = str([[g + 1 for g in grp] for grp in groups_info["groups"]])
        log_writer.log(page_no=0, level="INFO", process="page_segmentation", description=f"Segmentation completed: {len(groups_info['groups'])} group(s) - {groups_str}", status="Completed")

    # Map 1-based page_no -> full 1-based page list of the group it belongs
    # to (e.g. {1: [1, 2], 2: [1, 2], 3: [3]}). Pages that segmentation did
    # not group (or single-page jobs) map to a single-element list containing
    # only themselves, so downstream code can treat "grouped" and
    # "ungrouped" pages the same way (a group of size 1).
    page_to_group: dict[int, list[int]] = {}
    if groups_info and groups_info.get("groups"):
        for group in groups_info["groups"]:
            group_1based = sorted(g + 1 for g in group)
            for page_no in group_1based:
                page_to_group[page_no] = group_1based
    for i in range(len(all_results)):
        page_to_group.setdefault(i + 1, [i + 1])

    # ========================================================
    # STEP 5 : GENERATE response.json
    # ========================================================
    logger.info("Generating response.json")
    response_data, clean_json_path = response(
        input_json_path=str(raw_json_path),
        output_dir=str(JSON_DIR),
        output_filename="response.json",
    )

    logger.info(f"response.json Created : {clean_json_path}")

    # NOTE: at this point response_data's tables all have
    # visual_cells == [] — process_table_visuals() hasn't run yet.
    # This is expected; it gets synced back in below, right after
    # process_table_visuals() populates all_results in STEP 6 (parallel
    # extraction) below. Do NOT treat the empty list here as a bug.


    # ========================================================
    # STEP 6 : PARALLEL EXTRACTION (KV + Table Col Extraction + Table Visuals)
    # ========================================================
    if cancel_check and cancel_check():
        raise PipelineCancelledException("Pipeline cancelled by client disconnect")

    logger.info("Running KV + Table Extraction + Table Visuals in parallel")

    kv_error = [None]
    tbl_error = [None]
    visual_error = [None]

    # Build extraction plan: for each group, determine what raw_data and
    # response_data slice to use. Groups of size 1 use per-page data as today.
    # Groups of size 2+ use the merged view from segmentation.
    extraction_plan = []
    if groups_info:
        for group in groups_info["groups"]:
            if len(group) == 1:
                page_idx = group[0]
                extraction_plan.append({
                    "type": "single",
                    "page_indices": group,
                    "raw_data": [all_results[page_idx]],
                    "response_slice": [response_data[page_idx]],
                })
            else:
                key = (group[0], group[-1])
                mv = groups_info["merged_views"].get(key)
                if mv:
                    # response_slice must contain ALL pages in the group so
                    # that run_keyvalue_extraction can write into each page's
                    # response_data entry. The merged_page is a single-element
                    # raw_data list (1 extraction run), but the extraction
                    # function iterates over raw_data AND writes into
                    # response_data[page_idx] for each raw_data entry, so
                    # response_slice must be a 1-element list for the merge
                    # page, then the fan-out below replicates that single
                    # result to every page in the group.
                    extraction_plan.append({
                        "type": "merged",
                        "page_indices": group,
                        "raw_data": [mv["merged_page"]],
                        # Deep copy so parallel KV and table extraction
                        # threads don't race on the same dict reference.
                        "response_slice": [copy.deepcopy(response_data[group[0]])],
                    })
    else:
        # No segmentation (single-page job) — behave as today
        for page_idx in range(len(all_results)):
            extraction_plan.append({
                "type": "single",
                "page_indices": [page_idx],
                "raw_data": [all_results[page_idx]],
                "response_slice": [response_data[page_idx]],
            })

    kv_results_list = [None] * len(extraction_plan)
    tbl_results_list = [None] * len(extraction_plan)

    # Per-group buffered loggers — each group gets its own kv/tbl logger
    # so that per-page pipeline.log only contains that group's extraction logs.
    group_kv_loggers = []
    group_tbl_loggers = []
    group_kv_handlers = []
    group_tbl_handlers = []
    for plan_idx in range(len(extraction_plan)):
        kv_l, kv_h = make_buffered_logger(f"kv_extraction_g{plan_idx}")
        tbl_l, tbl_h = make_buffered_logger(f"tbl_extraction_g{plan_idx}")
        group_kv_loggers.append(kv_l)
        group_tbl_loggers.append(tbl_l)
        group_kv_handlers.append(kv_h)
        group_tbl_handlers.append(tbl_h)


    def _run_kv_for_plan(plan_idx):
        try:
            plan = extraction_plan[plan_idx]
            # In DEBUG/ERROR mode, use a structured CSV logger adapter;
            # in INFO mode (or server-side), keep the plain buffered logger.
            _pages = plan["page_indices"]
            _first_page = _pages[0] + 1 if _pages else 0
            kv_log = log_writer.get_kv_logger(page_no=_first_page) or group_kv_loggers[plan_idx]
            result = run_keyvalue_extraction(
                request_data=request_data,
                raw_data=plan["raw_data"],
                response_data=plan["response_slice"],
                log=kv_log,
            )
            kv_results_list[plan_idx] = result
        except Exception as e:
            kv_error[0] = e


    def _run_tbl_for_plan(plan_idx):
        import copy

        plan = extraction_plan[plan_idx]
        if not table_rec:
            # tables disabled -> page["tables"] is [] for every page, nothing
            # to extract headers/columns from.
            tbl_results_list[plan_idx] = [{"header_extraction": {}} for _ in plan["response_slice"]]
            return

        try:
            _pages = plan["page_indices"]
            _first_page = _pages[0] + 1 if _pages else 0
            tbl_log = log_writer.get_tbl_logger(page_no=_first_page) or group_tbl_loggers[plan_idx]
            result = run_table_extraction(
                request_data=request_data,
                raw_data=plan["raw_data"],
                response_data=copy.deepcopy(plan["response_slice"]),
                log=tbl_log,
            )
            tbl_results_list[plan_idx] = result
        except Exception as e:
            tbl_error[0] = e


    def _run_visual():
        if not table_rec:
            # tables disabled -> nothing to classify (wired/wireless) or
            # detect cells for; skip the model calls entirely.
            return

        try:
            for page in all_results:
                if cancel_check and cancel_check():
                    raise PipelineCancelledException("Pipeline cancelled by client disconnect")
                process_table_visuals(
                    page["tables"]
                )
        except Exception as e:
            visual_error[0] = e


    with ThreadPoolExecutor(max_workers=3) as pool:

        # Submit KV and table extraction for each plan
        kv_futures = [pool.submit(_run_kv_for_plan, i) for i in range(len(extraction_plan))]
        tbl_futures = [pool.submit(_run_tbl_for_plan, i) for i in range(len(extraction_plan))]
        f_visual = pool.submit(_run_visual)

        for f in kv_futures:
            f.result()
        for f in tbl_futures:
            f.result()
        f_visual.result()


    # Save per-group log records to persistent lists BEFORE flushing,
    # because flush_buffered_logger() clears handler.records.
    saved_kv_records = [list(h.records) for h in group_kv_handlers]
    saved_tbl_records = [list(h.records) for h in group_tbl_handlers]

    # Per-group extraction logs are NOT flushed into the shared pipeline logger.
    # They are saved in saved_kv_records / saved_tbl_records and appended to
    # each page's own pipeline.log in STEP 11 below.
    # This prevents duplication where ALL groups' logs appear in every page's
    # pipeline.log AND then that same group's logs are appended again.


    if kv_error[0]:
        raise kv_error[0]

    if tbl_error[0]:
        raise tbl_error[0]

    if visual_error[0]:
        raise visual_error[0]

    # Fan out extraction results to response_data
    for plan_idx, plan in enumerate(extraction_plan):
        kv_result = kv_results_list[plan_idx]
        tbl_result = tbl_results_list[plan_idx]

        for local_page_idx, global_page_idx in enumerate(plan["page_indices"]):
            page = response_data[global_page_idx]

            if kv_result:
                # For merged groups, kv_result has 1 entry (the merged run);
                # write that single result to EVERY page in the group.
                # For single-page groups, kv_result has 1 entry per page.
                result_idx = 0 if plan["type"] == "merged" else local_page_idx
                if result_idx < len(kv_result):
                    page["label_extraction"] = (
                        kv_result[result_idx]["label_extraction"]
                    )

            if tbl_result:
                result_idx = 0 if plan["type"] == "merged" else local_page_idx
                if result_idx < len(tbl_result):
                    page["header_extraction"] = (
                        tbl_result[result_idx]["header_extraction"]
                    )

        # ----------------------------------------------------------
        # FIX: re-sync visual_cells (and table_type) from all_results
        # into response_data.
        #
        # response_data's tables were built by response()/_extract_tables()
        # BEFORE process_table_visuals() ran, from the raw.json snapshot
        # taken in STEP 6. At that time every table["visual_cells"] == [].
        #
        # process_table_visuals() (STEP 6 parallel block, _run_visual)
        # mutates all_results by REASSIGNING table["visual_cells"] to a
        # brand-new list:
        #
        #     table["visual_cells"] = visual_cells
        #
        # That reassignment only updates the dict inside all_results.
        # response_data's table dicts are separate dicts (built by
        # _extract_tables' dict comprehension) that captured the OLD
        # (empty) list reference before the reassignment happened, so
        # they never see the populated boxes. Without this loop,
        # response.json — and therefore annotate_invoice(), which reads
        # from response.json — always sees empty visual_cells, no matter
        # how correct the drawing/coordinate code is.
        # ----------------------------------------------------------
        for local_page_idx, global_page_idx in enumerate(plan["page_indices"]):
            if global_page_idx < len(all_results):
                page = response_data[global_page_idx]
                raw_tables = all_results[global_page_idx].get("tables", [])

                for t_idx, table in enumerate(page.get("tables", [])):
                    if t_idx < len(raw_tables):
                        table["visual_cells"] = raw_tables[t_idx].get("visual_cells", [])
                        table["table_type"] = raw_tables[t_idx].get("table_type", table.get("table_type"))

    logger.info("Parallel Extraction Completed")
    log_writer.log(
        page_no=0, level="INFO", process="extraction",
        description="KV + Table extraction + Table visuals completed",
        status="Completed",
        output_summary=f"{len(extraction_plan)} group(s) extracted",
    )
    for page_no in range(1, len(all_results) + 1):
        page_resp = response_data[page_no - 1] if page_no - 1 < len(response_data) else {}
        kv_labels = page_resp.get("label_extraction", [])
        tbl_count = len(page_resp.get("header_extraction", []))
        log_writer.log(page_no=page_no, level="INFO", process="extraction", description=f"Page {page_no}: Table extractions={tbl_count}", status="Completed")
        # Log each KV label found/not found
        for label_entry in kv_labels:
            label_name = label_entry.get("label_name", "")
            label_value = label_entry.get("value", "")
            confidence = label_entry.get("confidence", "")
            method = label_entry.get("method", "")
            if label_value and str(label_value).strip():
                log_writer.log(page_no=page_no, level="INFO", process="kv_extraction", description=f"Label '{label_name}' found: '{label_value}'", status="Completed")
                _dlog(page_no, "kv_extraction",
                      f"Label '{label_name}' matched → value='{label_value}', confidence={confidence}, method={method}",
                      output_summary=f"value='{label_value}'")
            else:
                log_writer.log(page_no=page_no, level="INFO", process="kv_extraction", description=f"Label '{label_name}' not found", status="Completed")
                _dlog(page_no, "kv_extraction",
                      f"Label '{label_name}' not found — no candidate matched min_confidence threshold",
                      status="Completed")

    # Re-save raw.json with visual_cells populated
    # ========================================================
    # STEP 7 : RE-SAVE raw.json WITH VISUAL_CELLS POPULATED
    # ========================================================
    logger.info("Re-saving Raw OCR Output with visual cells")
    with open(raw_json_path, "w", encoding="utf-8") as f:
        _json_dump(all_results, f)
    logger.info(f"Raw Output Re-saved : {raw_json_path}")




    # ========================================================
    # STEP 7.5 : ATTACH page_group TO EACH PAGE'S RESPONSE
    # ========================================================
    # Lets the frontend know which pages belong to the same logical
    # document (page-stream-segmentation group) purely from the JSON it
    # already loads per page -- no separate API call or DB column needed.
    # A page with no multi-page group just gets a single-element list
    # containing its own page number.
    for idx, page in enumerate(response_data):
        page["page_group"] = page_to_group.get(idx + 1, [idx + 1])

    # ========================================================
    # STEP 7.6 : PER-GROUP STRAIGHT-THROUGH PROCESSING (STP)
    # ========================================================
    # For every page-stream-segmentation group, check whether every
    # required label (ocr.labels[].required) and every required table
    # header (tables.table_list[].headers[].required, only for enabled
    # tables) already has a non-empty extracted value. If so the group
    # needs no human review at all: its CSV is written straight to
    # extractedoutput/success/ here, and every page in the group is
    # marked "Completed" before the job ever reaches the DB. Any group
    # missing a required value is left "Pending" for the validation
    # screen -- and since page_statuses below flows into
    # HistoryRepository.finalize(), only Pending pages are what the
    # frontend has anything left to show for review.
    def _csv_row(values):
        cells = []
        for v in values:
            text = "" if v is None else str(v)
            if any(ch in text for ch in ('"', ",", "\n", "\r")):
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        return ",".join(cells)

    required_labels = [
        str(l.get("label_name", "")).strip()
        for l in request_data.get("ocr", {}).get("labels", [])
        if l.get("required", True) and str(l.get("label_name", "")).strip()
    ]
    required_table_headers = {}
    if request_data.get("tables", {}).get("enabled", False):
        for t in request_data.get("tables", {}).get("table_list", []):
            if t.get("enabled", True) is False:
                continue
            required_table_headers[str(t.get("table_name", ""))] = [
                str(h.get("header_name", "")).strip()
                for h in t.get("headers", [])
                if h.get("required", True) and str(h.get("header_name", "")).strip()
            ]

    def _is_group_stp_complete(page_dict):
        extractions = page_dict.get("label_extraction") or []
        for label_name in required_labels:
            match = next(
                (e for e in extractions
                 if str(e.get("label_name", "")).strip().lower() == label_name.lower()),
                None,
            )
            value = match.get("value") if match else None
            if value is None or str(value).strip() == "":
                return False

        tables_out = page_dict.get("header_extraction") or []
        for table_name, headers in required_table_headers.items():
            if not headers:
                continue
            table = next(
                (t for t in tables_out
                 if str(t.get("table_name", "")).strip().lower() == table_name.strip().lower()),
                None,
            )
            columns = (table or {}).get("columns") or []
            row_count = max((len(c.get("value") or []) for c in columns), default=0)
            if row_count == 0:
                # No rows extracted for this table -- mirrors the
                # frontend's existing leniency (nothing to validate yet,
                # so an empty table never blocks STP) rather than
                # silently failing every document whose table has no rows.
                continue
            for header_name in headers:
                col = next(
                    (c for c in columns
                     if str(c.get("header_name", "")).strip().lower() == header_name.lower()),
                    None,
                )
                values = (col or {}).get("value") or []
                for row_idx in range(row_count):
                    v = values[row_idx] if row_idx < len(values) else ""
                    if v is None or str(v).strip() == "":
                        return False
        return True

    def _build_group_csv(page_dict):
        lines = []
        labels_cfg = request_data.get("ocr", {}).get("labels", [])
        header_names = [l.get("label_name", "") for l in labels_cfg]
        extractions = page_dict.get("label_extraction") or []
        value_row = []
        for label_name in header_names:
            match = next(
                (e for e in extractions
                 if str(e.get("label_name", "")).strip().lower() == str(label_name).strip().lower()),
                None,
            )
            value_row.append(match.get("value") if match and match.get("value") is not None else "")
        lines.append(_csv_row(header_names))
        lines.append(_csv_row(value_row))
        lines.append("")

        tables_out = page_dict.get("header_extraction") or []
        for t in request_data.get("tables", {}).get("table_list", []):
            table_name = t.get("table_name", "")
            lines.append(table_name)
            col_headers = [h.get("header_name", "") for h in t.get("headers", [])]
            lines.append(_csv_row(col_headers))
            table = next(
                (tt for tt in tables_out
                 if str(tt.get("table_name", "")).strip().lower() == str(table_name).strip().lower()),
                None,
            )
            columns = (table or {}).get("columns") or []
            row_count = max((len(c.get("value") or []) for c in columns), default=0)
            for row_idx in range(row_count):
                row_values = []
                for col_header in col_headers:
                    col = next(
                        (c for c in columns
                         if str(c.get("header_name", "")).strip().lower() == str(col_header).strip().lower()),
                        None,
                    )
                    vals = (col or {}).get("value") or []
                    row_values.append(vals[row_idx] if row_idx < len(vals) else "")
                lines.append(_csv_row(row_values))
            lines.append("")

        return "\n".join(lines) + "\n"

    page_statuses = {}
    base_stem = Path(file_name).stem
    unique_groups = sorted({tuple(sorted(g)) for g in page_to_group.values()})

    for group in unique_groups:
        representative_idx = group[0] - 1
        representative_page = (
            response_data[representative_idx]
            if 0 <= representative_idx < len(response_data)
            else {}
        )

        if _is_group_stp_complete(representative_page):
            group_label = (
                "Page_" + ",".join(str(p) for p in group)
                if len(group) > 1
                else f"page_{group[0]}"
            )
            success_dir = OUTPUT_DIR / "extractedoutput" / "success"
            success_dir.mkdir(parents=True, exist_ok=True)
            csv_path = success_dir / f"{base_stem}_{JOB_ID}_{group_label}.csv"
            try:
                with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(_build_group_csv(representative_page))
                for p in group:
                    page_statuses[p] = "Completed"
                log_writer.log(page_no=group[0], level="INFO", process="stp_auto_submit",
                                description=f"All required fields present — auto-submitted group {list(group)} to {csv_path.name}",
                                status="Completed")
            except Exception as exc:
                logger.error(f"[STP auto-submit] Failed to write CSV for group {group}: {exc}")
                for p in group:
                    page_statuses[p] = "Pending"
        else:
            for p in group:
                page_statuses[p] = "Pending"

    # Mirror the same status onto each page's own JSON so it's visible to
    # anyone reading response.json directly, in addition to being
    # persisted to job_pages by the caller (see process_upload).
    for idx, page in enumerate(response_data):
        page["status"] = page_statuses.get(idx + 1, "Pending")

    # ========================================================
    # STEP 8 : SAVE FINAL response.json
    # ========================================================
    logger.info("Saving Final response.json")
    with open(clean_json_path, "w", encoding="utf-8") as f:
        _json_dump(response_data, f)

    logger.info(f"Final JSON Saved : {clean_json_path}")


    # ========================================================
    # STEP 9 : GENERATE ANNOTATED IMAGES
    # ========================================================
    logger.info("Generating Annotated Images")
    # filename pattern: annotated_<job_id>_<original_base_name>_page_<n>.png
    annotated_filenames = {}

    for page_no, page_data in enumerate(all_results, start=1):
        if cancel_check and cancel_check():
            raise PipelineCancelledException("Pipeline cancelled by client disconnect")
        image_path = page_data["image"]
        image_name = Path(image_path).stem   # e.g. <job_id>_AA_INV_001_page_1

        # Save annotated image into the per-page images/ directory.
        page_img_dir = page_images_dir(MODEL_NAME, JOB_ID, page_no)
        annotated_name = f"annotated_{image_name}.png"
        annotated_filenames[page_no] = annotated_name

        annotate_invoice(
            json_path       = clean_json_path,
            image_path      = image_path,
            output_dir      = str(page_img_dir),
            output_filename = annotated_name,
        )
        log_writer.log(page_no=page_no, level="INFO", process="annotation", description=f"Page {page_no}: Annotated image generated: {annotated_name}", status="Completed")
        _dlog(page_no, "annotation", f"Annotated image saved: {page_img_dir}/{annotated_name}",
              output_summary=f"output_dir={page_img_dir}")


    logger.info("Annotated Images Generated")
    log_writer.log(page_no=0, level="INFO", process="annotation", description=f"Annotated images generated for {len(all_results)} page(s)", status="Completed")

    # ========================================================
    # STEP 10 : SPLIT raw.json / response.json PER PAGE
    # ========================================================
    # raw.json/response.json were built and maintained as combined,
    # all-pages lists above because response()/kv-extraction/table-
    # extraction all operate across the full document. Here we split that
    # combined, in-memory data into each page's own response/ folder so no
    # job-level Response/ folder is left on disk.
    logger.info("Writing per-page raw.json / response.json")

    # Extract the output path from the original request so it can be saved
    # into each page's JSON files. The frontend reads it back when loading
    # history to pre-populate the Output Path textbox.
    output_path_from_request = request_data.get("document", {}).get("Output_path", "")

    for page_no, page_raw in enumerate(all_results, start=1):
        prd = page_response_dir(MODEL_NAME, JOB_ID, page_no)
        os.makedirs(prd, exist_ok=True)

        # Decorate raw results with output_path
        page_raw_with_path = {**page_raw, "output_path": output_path_from_request}
        with open(prd / "raw.json", "w", encoding="utf-8") as f:
            _json_dump([page_raw_with_path], f)

        page_clean = response_data[page_no - 1] if page_no - 1 < len(response_data) else {}
        # Decorate response data with output_path
        page_clean_with_path = {**page_clean, "output_path": output_path_from_request}
        with open(prd / "response.json", "w", encoding="utf-8") as f:
            _json_dump([page_clean_with_path], f)

    # ========================================================
    # STEP 11 : COPY PIPELINE LOGS INTO EVERY PAGE'S log/ FOLDER
    # ========================================================
    # For INFO mode, the structured table-format log has already been
    # written to Output/<job_id>/log/pipeline.log and page_N/log/pipeline.log
    # by the log_writer. We only append the KV/table extraction logs
    # when NOT in local-logging mode (checked=False) AND not INFO.
    # For DEBUG/ERROR mode with local logging (checked=True), the
    # StructuredCsvLogger adapter already wrote all KV detail into
    # pipeline.csv and page_N/page_pipeline.csv during extraction — no
    # additional file copying is needed.
    # ========================================================
    logger.info("Copying pipeline log into each page's log folder")
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass

    tmp_log_file = TMP_LOG_DIR / "pipeline.log"

    # Ensure output/<JOB_ID>/page_N/log/pipeline.log is created for all pages
    for page_no in range(1, len(all_results) + 1):
        log_writer._get_output_page_log(page_no)

    # Close the file handler pointing into TMP_DIR before deleting it --
    # on Windows an open file handle blocks rmtree from removing it.
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)

    # ========================================================
    # STEP 12 : CLEAN UP THE SCRATCH WORKING DIRECTORY
    # ========================================================
    shutil.rmtree(TMP_DIR, ignore_errors=True)

    # Calculate total execution time
    total_elapsed = time.perf_counter() - pipeline_start
    print("\n" + "=" * 60)
    print(f"TOTAL EXECUTION TIME: {total_elapsed:.4f}s")
    print("=" * 60)

    logger.info("=" * 80)
    logger.info("PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)
    log_writer.log(page_no=0, level="INFO", process="document_service", description=f"PIPELINE COMPLETED SUCCESSFULLY (Total time: {total_elapsed:.4f}s)", status="Completed")

    annotated_images = []

    for page_no in range(1, len(all_results) + 1):
        annotated_name = annotated_filenames[page_no]
        # Per-page path: <model_name>/<job_id>/page_<N>/images/<annotated_filename>
        relative_path = relative_image_path(MODEL_NAME, JOB_ID, page_no, annotated_name)
        annotated_images.append(relative_path.replace("\\", "/"))

    # Return everything frontend needs
    return {
        "response_data": response_data,
        "annotated_images": annotated_images,
        "raw_results": all_results,
        "page_statuses": page_statuses,
    }