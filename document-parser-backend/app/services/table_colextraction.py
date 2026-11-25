# table_colextrcation.py

import re
from datetime import datetime

from app.core.logger import logger
import app.services.table_colextraction as _self


# ═══════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════

def normalize_text(text):
    """Lowercase, strip, collapse whitespace."""
    if text is None:
        return ""
    return " ".join(str(text).split()).lower().strip()


def is_alias_match(alias, text_norm):
    """Whole-word match of alias inside text_norm.
    Falls back to exact normalized equality for headers with non-word
    characters (e.g. "#", "$", "@") that \b word boundaries can't match.
    """
    pattern = r"\b" + re.escape(alias) + r"\b"
    if re.search(pattern, text_norm):
        return True
    # Fallback: exact normalized equality — needed for column headers
    # like "#" where \b#\b can never match because # is not a \w char.
    return alias == text_norm


def any_key_matches(keys, target_norm):
    """
    Return True if any normalized key in `keys`
    word-matches `target_norm`.
    """
    for key in keys:
        key_norm = normalize_text(key)
        if key_norm and is_alias_match(key_norm, target_norm):
            return True
    return False


# ═══════════════════════════════════════════════════════
# DATATYPE DETECTION
# ═══════════════════════════════════════════════════════

def detect_list_dtype(values):
    cleaned = [
        str(v).strip()
        for v in values
        if str(v).strip() not in ("", "None", "null")
    ]

    if not cleaned:
        return "string"

    number_pattern = re.compile(r"^-?\d+(\.\d+)?$")
    if all(number_pattern.match(v.replace(",", "")) for v in cleaned):
        return "number"

    date_formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
        "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d",
    ]

    def is_date(val):
        for fmt in date_formats:
            try:
                datetime.strptime(val, fmt)
                return True
            except Exception:
                pass
        return False

    if all(is_date(v) for v in cleaned):
        return "date"

    return "string"


# ═══════════════════════════════════════════════════════
# TABLE + ROW-START FINDER
#
# Returns a 4-tuple:
#   (raw_table, start_index, start_source, header_row_index)
#
# start_source  │ meaning
# ──────────────┼──────────────────────────────────────────────
# "column_name" │ PHASE 1 — rowStart matched a column_wise KEY
#               │   → column_wise keys ARE the headers
#               │   → start_index = 0
#               │   → header_row_index = None
# ──────────────┼──────────────────────────────────────────────
# "column_value"│ PHASE 2 — rowStart matched a VALUE inside a
#               │   column (embedded header row in the data)
#               │   → that row's values are the virtual headers
#               │   → start_index  = header_row_index + 1
#               │   → header_row_index = matched row idx
# ──────────────┼──────────────────────────────────────────────
# "default"     │ No rowStart given — use first table, start=0
#               │   → try Phase 1 column finding
# ═══════════════════════════════════════════════════════

def _score_table_by_headers(raw_table, headers_cfg):
    """
    Score a table based on how many requested headers
    match its column names.

    Returns:
        score (int)
    """
    column_wise = raw_table.get("column_wise", {})

    if not column_wise:
        return 0

    score = 0

    for header_cfg in headers_cfg:

        header_name_norm = normalize_text(
            header_cfg["header_name"]
        )

        aliases_norm = [
            normalize_text(a)
            for a in header_cfg.get("aliases", [])
        ]

        all_aliases = [header_name_norm] + aliases_norm

        for col_name in column_wise.keys():

            col_norm = normalize_text(col_name)

            matched = False

            for alias in all_aliases:
                if alias and is_alias_match(alias, col_norm):
                    score += 1
                    matched = True
                    break

            if matched:
                break

    return score

def _find_table_and_row_start(
    raw_tables,
    row_start_keys,
    headers_cfg=None,
    used_table_indexes=None
):

    if used_table_indexes is None:
        used_table_indexes = set()

    # ==================================================
    # CASE 3
    # No rowStart
    # ==================================================
    if not row_start_keys:

        candidate_tables = []

        for raw_table in raw_tables:

            table_idx = raw_table.get("table_index")

            if table_idx in used_table_indexes:
                continue

            score = _score_table_by_headers(
                raw_table,
                headers_cfg or []
            )

            candidate_tables.append(
                (score, raw_table)
            )

        if candidate_tables:

            candidate_tables.sort(
                key=lambda x: x[0],
                reverse=True
            )

            best_score, best_table = candidate_tables[0]

            if best_score <= 0:
                return None, None, None, None

            return best_table, 0, "default", None

        return None, None, None, None

    # ==================================================
    # CASE 1
    # rowStart matched column names
    # ==================================================
    phase1_candidates = []

    for raw_table in raw_tables:

        table_idx = raw_table.get("table_index")

        if table_idx in used_table_indexes:
            continue

        column_wise = raw_table.get("column_wise", {})

        if not column_wise:
            continue

        matched = False

        for col_name in column_wise:

            if any_key_matches(
                row_start_keys,
                normalize_text(col_name)
            ):

                matched = True
                break

        if matched:

            score = _score_table_by_headers(
                raw_table,
                headers_cfg or []
            )

            phase1_candidates.append(
                (
                    score,
                    raw_table
                )
            )

    if phase1_candidates:

        phase1_candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )

    
        best_score, best_table = phase1_candidates[0]

        if best_score <= 0:
            return None, None, None, None

        return best_table, 0, "column_name", None

    # ==================================================
    # CASE 2
    # rowStart matched cell value
    # virtual header scoring
    # ==================================================
    phase2_candidates = []

    for raw_table in raw_tables:

        table_idx = raw_table.get("table_index")

        if table_idx in used_table_indexes:
            continue

        column_wise = raw_table.get("column_wise", {})

        if not column_wise:
            continue

        table_matched = False

        for col_name, col_values in column_wise.items():

            for row_idx, val in enumerate(col_values):

                if not any_key_matches(
                    row_start_keys,
                    normalize_text(str(val))
                ):
                    continue

                score = 0

                for header_cfg in headers_cfg or []:

                    found = False

                    header_name = normalize_text(
                        header_cfg["header_name"]
                    )

                    aliases = [
                        normalize_text(a)
                        for a in header_cfg.get(
                            "aliases",
                            []
                        )
                    ]

                    all_aliases = [header_name] + aliases

                    for col_key, col_vals in column_wise.items():

                        if row_idx >= len(col_vals):
                            continue

                        virtual_header = normalize_text(
                            str(col_vals[row_idx])
                        )

                        for alias in all_aliases:

                            if alias and is_alias_match(
                                alias,
                                virtual_header
                            ):
                                score += 1
                                found = True
                                break

                        if found:
                            break


                if score > 0:

                    phase2_candidates.append(
                        (
                            score,
                            raw_table,
                            row_idx
                        )
                    )

                    table_matched = True
                    break



            if table_matched:
                break

    if phase2_candidates:

        phase2_candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )

        score, best_table, header_row_index = (
            phase2_candidates[0]
        )

        if score <= 0:
            return None, None, None, None

        return (
            best_table,
            header_row_index + 1,
            "column_value",
            header_row_index
        )


    # ==================================================
    # FALLBACK
    # rowStart not found anywhere
    # use header matching only
    # ==================================================

    candidate_tables = []

    for raw_table in raw_tables:

        table_idx = raw_table.get("table_index")

        if table_idx in used_table_indexes:
            continue

        score = _score_table_by_headers(
            raw_table,
            headers_cfg or []
        )

        candidate_tables.append(
            (
                score,
                raw_table
            )
        )

    if candidate_tables:

        candidate_tables.sort(
            key=lambda x: x[0],
            reverse=True
        )

        best_score, best_table = candidate_tables[0]

        if best_score > 0:

            logger.info(
                f"[FALLBACK] rowStart not found. "
                f"Selected table_index="
                f"{best_table.get('table_index')} "
                f"score={best_score}"
            )

            return best_table, 0, "fallback", None

    return None, None, None, None
# ═══════════════════════════════════════════════════════
# ROW-END FINDER  (shared by both phases)
# ═══════════════════════════════════════════════════════

def _find_row_end(column_wise, row_end_keys, start_index):
    """
    Scan values from start_index onwards for any table_rowEnd key.
    Returns the earliest matching row_index (exclusive slice end),
    or None if no match / no rowEnd configured.
    """
    if not row_end_keys:
        return None

    earliest = None

    for col_name, col_values in column_wise.items():
        for row_idx in range(start_index, len(col_values)):
            val_norm = normalize_text(str(col_values[row_idx]))
            if any_key_matches(row_end_keys, val_norm):
                if earliest is None or row_idx < earliest[0]:
                    earliest = (row_idx, col_name, col_values[row_idx])

    if earliest is not None:
        row_idx, col_name, val = earliest
        logger.info(
            f"[TABLE] rowEnd matched value '{val}' "
            f"in col='{col_name}' at row {row_idx} → end={row_idx} (exclusive)"
        )
        return row_idx

    return None


# ═══════════════════════════════════════════════════════
# PHASE 1 — COLUMN FINDER
# Match header_name / aliases against column_wise KEYS.
# Used when column_wise keys are real header names.
# ═══════════════════════════════════════════════════════

def _find_column_key_phase1(column_wise, header_cfg):
    """
    Returns: (col_key, matched_alias, match_type)
          or (None, None, None)
    """
    header_name_norm = normalize_text(header_cfg["header_name"])
    aliases_norm = [
        normalize_text(a) for a in header_cfg.get("aliases", [])
    ]
    all_aliases = [header_name_norm] + aliases_norm

    for col_key in column_wise:
        col_key_norm = normalize_text(col_key)
        for alias in all_aliases:
            if alias and is_alias_match(alias, col_key_norm):
                match_type = "header" if alias == header_name_norm else "alias"
                logger.info(
                    f"[PHASE 1] Header '{header_cfg['header_name']}' "
                    f"matched col key '{col_key}' via alias '{alias}'"
                )
                return col_key, alias, match_type

    return None, None, None


# ═══════════════════════════════════════════════════════
# PHASE 2 — COLUMN FINDER
#
# column_wise keys are generic (e.g. "0","1","2"…).
# The embedded header row (at header_row_index) holds the
# real column names as VALUES.
#
# We build a virtual header map:
#   col_key  →  column_wise[col_key][header_row_index]
# then match the requested header against those values.
# ═══════════════════════════════════════════════════════

def _find_column_key_phase2(column_wise, header_row_index, header_cfg):
    """
    Returns: (col_key, matched_alias, match_type, virtual_header_text)
          or (None, None, None, None)
    """
    header_name_norm = normalize_text(header_cfg["header_name"])
    aliases_norm = [
        normalize_text(a) for a in header_cfg.get("aliases", [])
    ]
    all_aliases = [header_name_norm] + aliases_norm

    for col_key, col_values in column_wise.items():

        if header_row_index >= len(col_values):
            continue

        # The value at header_row_index is the virtual column header
        virtual_header      = col_values[header_row_index]
        virtual_header_norm = normalize_text(str(virtual_header))

        if not virtual_header_norm:
            continue                      # empty cell — skip

        for alias in all_aliases:
            if alias and is_alias_match(alias, virtual_header_norm):
                match_type = "header" if alias == header_name_norm else "alias"
                logger.info(
                    f"[PHASE 2] Header '{header_cfg['header_name']}' "
                    f"matched virtual header '{virtual_header}' "
                    f"in col '{col_key}' via alias '{alias}'"
                )
                return col_key, alias, match_type, virtual_header

    return None, None, None, None


# ═══════════════════════════════════════════════════════
# MAIN EXTRACTION
# ═══════════════════════════════════════════════════════

def table_phase1(request_data, page_data):
    tables_cfg = request_data.get("tables", {})
    table_list = tables_cfg.get("table_list", [])
    raw_tables = page_data.get("tables", [])
    results    = []
    used_table_indexes = set()

    for table_cfg in table_list:

        table_name    = table_cfg.get("table_name", "unknown")
        headers_cfg   = table_cfg.get("headers", [])
        table_enabled = table_cfg.get("enabled", True)

        if not table_enabled:
            logger.info(
                f"[TABLE PHASE 1] Skipping disabled table '{table_name}'"
            )
            continue

        min_confidence = table_cfg.get("min_confidence", 0.75)
        row_start_keys = table_cfg.get("table_rowStart", [])
        row_end_keys   = table_cfg.get("table_rowEnd", [])

        logger.info("=" * 50)
        logger.info(
            f"[TABLE] Processing '{table_name}' | "
            f"min_confidence={min_confidence} | "
            f"rowStart={row_start_keys} | "
            f"rowEnd={row_end_keys}"
        )
        logger.info("=" * 50)

        # ── Step 1: find raw table + row bounds ──────────
        raw_table, start_index, start_source, header_row_index = (
            _find_table_and_row_start(
                raw_tables,
                row_start_keys,
                headers_cfg,
                used_table_indexes
            )
        )
        if raw_table is None:
            logger.info(
                f"[TABLE] No matching raw table found for '{table_name}'"
            )
            continue

        column_wise = raw_table.get("column_wise", {})
        table_idx   = raw_table.get("table_index", "?")
        used_table_indexes.add(table_idx)

        logger.info(
            f"[TABLE] Matched table_index={table_idx} | "
            f"phase='{start_source}' | "
            f"header_row={header_row_index} | "
            f"data_start={start_index}"
        )

        # ── Step 2: find row end ──────────────────────────
        end_index = _find_row_end(column_wise, row_end_keys, start_index)

        logger.info(
            f"[TABLE] Row slice → [{start_index} : {end_index}]"
        )

        # ── Step 3: log virtual header map (Phase 2 only) ─
        if start_source == "column_value" and header_row_index is not None:
            virtual_map = {
                k: v[header_row_index]
                for k, v in column_wise.items()
                if header_row_index < len(v)
            }
            logger.info(
                f"[PHASE 2] Virtual header map → {virtual_map}"
            )

        # ── Step 4: extract each requested column ─────────
        table_results = []

        for header_cfg in headers_cfg:
            header_name = header_cfg["header_name"]

            logger.info(f"[TABLE] Searching column '{header_name}'")

            # ── choose phase ─────────────────────────────
            
            if start_source in ("column_name", "default", "fallback"):
                # ── PHASE 1 ──────────────────────────────
                # column_wise keys are the real headers
                col_key, matched_alias, match_type = (
                    _find_column_key_phase1(column_wise, header_cfg)
                )
                virtual_header_text = col_key   # key itself is the header

            else:
                # ── PHASE 2 ──────────────────────────────
                # column_wise keys are generic; real headers
                # are values embedded at header_row_index
                col_key, matched_alias, match_type, virtual_header_text = (
                    _find_column_key_phase2(
                        column_wise, header_row_index, header_cfg
                    )
                )

            # ── column not found in either phase ─────────
            if col_key is None:
                logger.info(
                    f"[TABLE] Column '{header_name}' not found "
                    f"(phase='{start_source}')"
                )
                continue

            # ── slice values ──────────────────────────────
            col_values = column_wise[col_key]
            values = (
                col_values[start_index : end_index]
                if end_index is not None
                else col_values[start_index:]
            )

            logger.info(
                f"[TABLE] '{header_name}' → "
                f"col_key='{col_key}' | "
                f"virtual_header='{virtual_header_text}' | "
                f"values={values}"
            )

            retrieved_dtype = detect_list_dtype(values)

            table_results.append({
                "header_name":        header_name,
                "required":           header_cfg.get("required", False),
                "data_type":          header_cfg.get("data_type", "string"),
                "retrived_dtype":     retrieved_dtype,
                "value":              values,
                # the column_wise key used ("0","1",… or a real name)
                "foundkey":           col_key,
                # the actual header text matched (virtual or key)
                "virtual_header":     virtual_header_text,
                # alias string that triggered the match
                "matched_by":         matched_alias,
                # "header" | "alias"
                "match_type":         match_type,
                # which phase resolved this column
                "phase": (
                    "phase1" if start_source in (
                        "column_name",
                        "default",
                        "fallback"
                    )
                    else "phase2"
                ),
            })

        results.append({
            "table_name": table_name,
            "extraction_phase": (
                "phase1" if start_source in (
                    "column_name",
                    "default",
                    "fallback"
                )
                else "phase2"
            ),
            "header_row_index": header_row_index,
            "data_start_index": start_index,
            "data_end_index": end_index,
            "columns": table_results,
        })

    return results


# ═══════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════

def main(request_data, raw_data, response_data, log=None):

    
    _real_logger = _self.logger
    if log is not None:
        _self.logger = log

    try:
        for page_index, page_data in enumerate(raw_data):
            logger.info(f"TABLE EXTRACTION PAGE {page_index + 1}")
            results = table_phase1(request_data, page_data)
            response_data[page_index]["header_extraction"] = results

        return response_data

    finally:
        _self.logger = _real_logger