###############################################################
# VIDEO SERVICE — SUMMARY
# Semantic deduplication (Qwen3-VL judge) + timeline generation
###############################################################

import logging
import re
import json
import time
from difflib import SequenceMatcher

from model import run_inference, parse_json_response, MAX_NEW_TOKENS_SEMANTIC, MAX_NEW_TOKENS_SUMMARY
from prompts import SEMANTIC_PROMPT_TEMPLATE, SUMMARY_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

# ==================================================
# THRESHOLDS
# ==================================================

SIMILARITY_THRESHOLD         = 0.85   # fallback SequenceMatcher threshold
SEMANTIC_DUPLICATE_THRESHOLD = 0.75   # semantic score threshold

# ==================================================
# RETRY CONFIG
# ==================================================

_SUMMARY_MAX_RETRIES = 2
_SUMMARY_RETRY_DELAY = 1.0

# ==================================================
# RETRY HELPER
# ==================================================

def _retry_inference(operation_name: str, func, max_attempts: int = None):
    """Retry a model inference call with exponential backoff."""
    max_attempts = max_attempts or _SUMMARY_MAX_RETRIES
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                backoff = _SUMMARY_RETRY_DELAY * attempt
                logger.warning(f"{operation_name} attempt {attempt} failed ({e}); retrying in {backoff:.1f}s...")
                time.sleep(backoff)
            else:
                logger.error(f"{operation_name} failed after {max_attempts} attempts: {e}")
                raise
    raise last_error


# ==================================================
# SEMANTIC SIMILARITY  (Qwen3-VL judge)
# ==================================================

def semantic_similarity(action_a: str, action_b: str) -> dict:
    """
    Use the loaded Qwen3-VL model to judge semantic similarity
    between two action strings (text-only call — no images).

    Returns:
        {
            "semantic_score":  float  0.0–1.0,
            "is_duplicate":    bool,
            "reason":          str,
            "method":          "semantic_model" | "fallback_sequencematcher"
        }
    """
    # Edge case: empty inputs
    if not action_a or not action_b:
        return {
            "semantic_score": 0.0,
            "is_duplicate":   False,
            "reason":         "One or both actions are empty.",
            "method":         "semantic_model",
        }

    # Edge case: identical strings — skip model call entirely
    if action_a.strip().lower() == action_b.strip().lower():
        return {
            "semantic_score": 1.0,
            "is_duplicate":   True,
            "reason":         "Actions are character-identical.",
            "method":         "semantic_model",
        }

    prompt   = SEMANTIC_PROMPT_TEMPLATE.format(
        action_a=action_a.strip(),
        action_b=action_b.strip(),
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    try:
        raw = _retry_inference(
            "semantic_similarity",
            lambda: run_inference(messages, max_new_tokens=MAX_NEW_TOKENS_SEMANTIC)
        )
        logger.debug(f"  Semantic raw response: {raw}")

        result  = parse_json_response(raw)
        score   = float(result.get("semantic_score", 0.0))
        is_dup  = bool(result.get("is_duplicate", score >= SEMANTIC_DUPLICATE_THRESHOLD))
        reason  = str(result.get("reason", "No reason provided."))

        return {
            "semantic_score": round(score, 3),
            "is_duplicate":   is_dup,
            "reason":         reason,
            "method":         "semantic_model",
        }

    except Exception as ex:
        # Graceful fallback — pipeline must never break
        logger.warning(
            f"  Semantic judge failed ({ex}). Falling back to SequenceMatcher."
        )
        fallback_score = SequenceMatcher(
            None, action_a.lower(), action_b.lower()
        ).ratio()
        return {
            "semantic_score": round(fallback_score, 3),
            "is_duplicate":   fallback_score >= SIMILARITY_THRESHOLD,
            "reason":         f"Fallback SequenceMatcher used (model error: {ex})",
            "method":         "fallback_sequencematcher",
        }


# ==================================================
# CONSOLIDATED SUMMARY  (batched to avoid token cutoff)
# ==================================================

SUMMARY_BATCH_SIZE = 20   # actions per batch — safe for 2B model context

# Roughly how many output tokens one timeline item needs (a short JSON
# string entry) — used to size each summary call's max_new_tokens to the
# actual amount of content instead of always requesting the full
# MAX_NEW_TOKENS_SUMMARY budget (2048), which is sized for the worst
# case (a full 20-item batch). A 1-2 item batch (e.g. a very short
# video) generating up to 2048 tokens wastes real time on CPU, since
# generation is sequential — one full forward pass per token.
TOKENS_PER_ITEM  = 90
MIN_SUMMARY_TOKENS = 150  # floor — enough for a couple of items + JSON wrapper


def _scaled_token_budget(item_count: int) -> int:
    return max(MIN_SUMMARY_TOKENS, min(MAX_NEW_TOKENS_SUMMARY, item_count * TOKENS_PER_ITEM))


def _call_summary_model(descriptions: str, max_tokens: int = MAX_NEW_TOKENS_SUMMARY) -> list:
    """
    Single summary call. Returns a list of timeline strings.
    Robust to markdown fences, truncated JSON, and plain-text fallback.
    Includes retry logic for transient inference failures.
    """
    prompt   = SUMMARY_PROMPT_TEMPLATE.format(descriptions=descriptions)
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    raw = _retry_inference(
        "summary_model",
        lambda: run_inference(messages, max_new_tokens=max_tokens)
    )

    logger.info(f"  Summary raw output ({len(raw)} chars): {raw[:120]} ...")

    try:
        result = parse_json_response(raw)
        return result.get("timeline", [])
    except (ValueError, AttributeError):
        pass

    # Attempt: extract ["..."] array substring
    clean = raw.strip()
    sa, ea = clean.find("["), clean.rfind("]") + 1
    if sa != -1 and ea > sa:
        try:
            result = json.loads(clean[sa:ea])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Attempt: model output was truncated mid-JSON — recover complete items
    items = re.findall(r'"((?:[^"\\]|\\.)+)"', clean)
    items = [i for i in items if len(i) > 10]
    if items:
        logger.warning(
            f"  JSON truncated — recovered {len(items)} items via regex."
        )
        return items

    # Final fallback: plain-text lines
    logger.warning(f"  Summary JSON parse failed. Raw: {raw[:300]}")
    return [line.strip(" -\u2022") for line in clean.splitlines() if line.strip(" -\u2022")]


def _merge_batches_safely(items: list) -> list:
    """
    Merge a list of per-batch timeline items into a smoother final timeline,
    WITHOUT ever asking the model to compress more than SUMMARY_BATCH_SIZE
    items in a single call.

    The old code sent every batch's items into one giant merge call, bounded
    by the same MAX_NEW_TOKENS_SUMMARY used for a single 20-item batch. For
    long videos (many batches) that meant compressing 40/60/100+ items into
    one fixed-size response — small models handle that by keeping the
    beginning and end (they anchor the prompt) and dropping or truncating
    everything in between, which is exactly the "middle of the video is
    missing" symptom.

    Instead, merge in safe-sized chunks and repeat (merge-tree style) until
    one chunk remains, so every merge call operates on a size that's already
    proven not to drop content, and no item is ever silently discarded —
    only summarized within its own safe-sized group.
    """
    current = items
    max_rounds = 6  # generous for any realistic video length; guards against pathological input
    for _round in range(max_rounds):
        if len(current) <= SUMMARY_BATCH_SIZE:
            break
        next_round = []
        for i in range(0, len(current), SUMMARY_BATCH_SIZE):
            chunk = current[i : i + SUMMARY_BATCH_SIZE]
            merged_desc = "\n".join(f"  {j + 1}. {item}" for j, item in enumerate(chunk))
            merged_chunk = _call_summary_model(merged_desc, max_tokens=_scaled_token_budget(len(chunk)))
            # Never drop a chunk outright if the model call comes back empty —
            # fall back to the unmerged chunk so those items survive.
            next_round.extend(merged_chunk if merged_chunk else chunk)

        if len(next_round) >= len(current):
            # No progress this round (model didn't actually compress the
            # chunk) — stop here rather than looping without making
            # progress. Every item from `current` is still present in
            # `next_round`, just not compressed further this round.
            logger.warning(
                f"  Merge round made no progress ({len(current)} \u2192 {len(next_round)} items) \u2014 stopping."
            )
            current = next_round
            break
        current = next_round
    return current


def generate_summary(unique_records: list) -> list:
    """
    Summarise unique_records in batches of SUMMARY_BATCH_SIZE,
    then merge all batch results into one final timeline.
    """
    if not unique_records:
        return []

    # Step 1: summarise each batch
    batches     = [
        unique_records[i : i + SUMMARY_BATCH_SIZE]
        for i in range(0, len(unique_records), SUMMARY_BATCH_SIZE)
    ]
    batch_items = []

    for b_idx, batch in enumerate(batches):
        logger.info(
            f"  Summary batch {b_idx + 1}/{len(batches)} "
            f"({len(batch)} actions) ..."
        )
        descriptions = "\n".join(
            f"  [t={r['timestamp_sec']:.1f}s] {r['final_action']}"
            for r in batch
        )
        items = _call_summary_model(descriptions, max_tokens=_scaled_token_budget(len(batch)))
        logger.info(f"    \u2192 {len(items)} items from batch {b_idx + 1}")
        logger.debug(f"    batch {b_idx + 1} input descriptions:\n{descriptions}")
        logger.debug(f"    batch {b_idx + 1} output items: {items}")
        batch_items.extend(items)

    # Step 2: if more than one batch, merge — in safe-sized chunks, never
    # one giant call (see _merge_batches_safely docstring above).
    if len(batches) > 1 and batch_items:
        logger.info(
            f"  Merging {len(batch_items)} items from {len(batches)} batches "
            f"(chunked, max {SUMMARY_BATCH_SIZE} items per merge call) ..."
        )
        merged = _merge_batches_safely(batch_items)
        logger.debug(f"Final merged timeline ({len(merged)} items): {merged}")
        return merged

    logger.debug(f"Final timeline (single batch, {len(batch_items)} items): {batch_items}")
    return batch_items