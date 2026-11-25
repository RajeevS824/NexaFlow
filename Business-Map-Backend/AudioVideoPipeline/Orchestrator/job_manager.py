# ###############################################################
# # ORCHESTRATOR — JOB MANAGER
# # Job naming, output path routing, JSON saving, LLM analysis
# ###############################################################

# import copy
# import json
# import logging
# import os
# import re
# import time
# import uuid
# import requests
# from concurrent.futures import ThreadPoolExecutor
# from datetime import datetime
# from pathlib import Path

# import yaml
# from docx import Document
# from docx.shared import Inches

# # Load repo-root .env (if present) so PRIMARY_LLM_API_KEY / OPENROUTER_API_KEY /
# # SECONDARY_LLM_API_KEY / EMAIL_SENDER_PASSWORD are actually set in the process
# # environment before LLMClient reads them below — same pattern already used
# # in database.py, integrated_pipeline.py, pipeline_v3_1_production.py, and
# # video_service/app.py. Without this, job_manager.py silently sees empty env
# # vars whenever it's imported/run before run_backend.py's own load_dotenv()
# # call, which is what was causing every LLM call to fail and fall back to
# # the job_name-based title and the generic "AI service did not return an
# # overview" text (looked "hardcoded" but was actually a missing .env load).
# try:
#     from dotenv import load_dotenv
#     load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
# except ImportError:
#     pass

# logger = logging.getLogger("JobManager")

# # ==================================================
# # CONFIG
# # ==================================================

# # PORTABLE PATH: works unchanged on Colab, Kaggle, or a local machine.
# _DEFAULT_CONFIG_PATH = str(
#     Path(__file__).resolve().parent.parent / "Configuration" / "config.yaml"
# )

# def _load_config(path: str = None) -> dict:
#     path = path or os.environ.get("CONFIG_PATH", _DEFAULT_CONFIG_PATH)
#     try:
#         with open(path) as f:
#             return yaml.safe_load(f)
#     except Exception as e:
#         logger.warning(f"Failed to load config from {path}: {e}")
#         # SECURITY: no secret fallback value here — if config.yaml can't be
#         # read, the API keys below will also be empty and the LLM call
#         # will fail loudly (raise_for_status) instead of silently using
#         # a leaked key.
#         return {
#             "output": {
#                 "audio_json_dir": "output/audio_json",
#                 "video_json_dir": "output/video_json",
#                 "report_dir":     "output/reports",
#             },
#             "llm": {
#                 "retry": {"max_attempts": 3, "delay_sec": 2, "backoff_multiplier": 2.0, "timeout_sec": 60},
#                 "primary": {
#                     "api_key_env": "PRIMARY_LLM_API_KEY",
#                     "base_url": "https://openrouter.ai/api/v1",
#                     "model": "cohere/north-mini:free",
#                 },
#                 "secondary": {
#                     "api_key_env": "SECONDARY_LLM_API_KEY",
#                     "base_url": "",
#                     "model_1": "",
#                     "model_2": "",
#                 },
#                 "openrouter_api_key": "",
#                 "model": "cohere/north-mini:free",
#             }
#         }

# config = _load_config()

# AUDIO_JSON_DIR = Path(config["output"]["audio_json_dir"])
# VIDEO_JSON_DIR = Path(config["output"]["video_json_dir"])
# REPORT_DIR     = Path(config.get("output", {}).get("report_dir", "output/reports"))

# # ==================================================
# # LLM CLIENT — Retry + Fallback
# # ==================================================

# class LLMClient:
#     """
#     Robust LLM client with configurable retry and multi-provider fallback.

#     Fallback Flow:
#       1. Try Primary API using the configured primary model.
#       2. If it fails after all retries: switch to Secondary API, try MODEL_1.
#       3. If MODEL_1 fails after retries: try MODEL_2.
#       4. If all models fail: raise a proper error (caller handles gracefully).

#     Retry Logic:
#       - Retries on: API timeout, Rate limit (429), Temporary server error (5xx),
#         Connection error, Any recoverable API exception.
#       - Uses configurable retry count and delay with exponential backoff.
#       - Idempotent: the same immutable request payload is re-sent on every
#         attempt, so no duplicate processing or inconsistent outputs can occur.

#     Logging:
#       - Logs retry attempts, retry failures, fallback activation, selected
#         API, selected model, final success, and final failure.
#       - NEVER logs API keys or other sensitive information.
#     """

#     def __init__(self, config_dict: dict, key_overrides: dict = None):
#         """
#         `key_overrides`, when given, lets a caller supply per-request
#         credentials (e.g. a customer's own API keys from Settings ->
#         LLM Configuration -> "Use My Own API Key") instead of the
#         application's .env defaults, without touching os.environ or any
#         other in-flight request. Expected shape:
#             {"primary_api_key": "...", "secondary_api_key": "..."}
#         Either key may be omitted/empty — that provider tier is simply
#         skipped, same as when the equivalent env var is unset.
#         Never logged — see _call_single_provider().
#         """
#         self._llm_cfg = config_dict.get("llm", {})
#         self._retry_cfg = self._llm_cfg.get("retry", {})
#         self._max_attempts = self._retry_cfg.get("max_attempts", 3)
#         self._delay_sec = self._retry_cfg.get("delay_sec", 2)
#         self._backoff_multiplier = self._retry_cfg.get("backoff_multiplier", 2.0)
#         self._timeout_sec = self._retry_cfg.get("timeout_sec", 60)

#         key_overrides = key_overrides or {}

#         # Build the provider chain: primary -> secondary model_1 -> secondary model_2
#         self._providers = []

#         primary = self._llm_cfg.get("primary", {})
#         primary_key_env = primary.get("api_key_env", "PRIMARY_LLM_API_KEY")
#         primary_key = key_overrides.get("primary_api_key") or \
#                       os.environ.get(primary_key_env) or \
#                       os.environ.get("OPENROUTER_API_KEY") or \
#                       self._llm_cfg.get("openrouter_api_key", "")
#         primary_url = primary.get("base_url", "https://openrouter.ai/api/v1")
#         primary_model = primary.get("model", "cohere/north-mini:free")
#         if primary_key and primary_model:
#             self._providers.append({
#                 "name": "Primary API",
#                 "api_key": primary_key,
#                 "base_url": primary_url,
#                 "model": primary_model,
#             })

#         secondary = self._llm_cfg.get("secondary", {})
#         secondary_key_env = secondary.get("api_key_env", "SECONDARY_LLM_API_KEY")
#         secondary_key = key_overrides.get("secondary_api_key") or os.environ.get(secondary_key_env, "")
#         secondary_url = secondary.get("base_url", "")

#         secondary_models = secondary.get("models") or [
#             secondary.get(k, "") for k in ("model_1", "model_2")
#         ]
#         for i, model in enumerate(secondary_models, start=1):
#             if secondary_key and model:
#                 self._providers.append({
#                     "name": f"Secondary API (model_{i}: {model})",
#                     "api_key": secondary_key,
#                     "base_url": secondary_url,
#                     "model": model,
#                 })

#         if not self._providers:
#             logger.warning(
#                 "No LLM providers configured. LLM workflow analysis will fail. "
#                 "Set PRIMARY_LLM_API_KEY (or OPENROUTER_API_KEY) in .env."
#             )

#     def _is_retryable(self, exception: Exception) -> bool:
#         """Determine if an exception is retryable (transient/recoverable)."""
#         # Connection errors
#         if isinstance(exception, (requests.ConnectionError, requests.Timeout)):
#             return True
#         # HTTP errors with retryable status codes
#         if isinstance(exception, requests.HTTPError):
#             response = getattr(exception, "response", None)
#             if response is not None:
#                 status = response.status_code
#                 # 429 = rate limit, 5xx = server errors
#                 if status == 429 or 500 <= status < 600:
#                     return True
#             return True  # treat HTTPError as retryable by default
#         # Any other recoverable exception
#         return True

#     def _call_single_provider(self, provider: dict, messages: list) -> str:
#         """
#         Call a single LLM provider with retry logic.
#         Returns the raw response text.
#         Raises the last exception if all retries fail.
#         """
#         api_key = provider["api_key"]
#         base_url = provider["base_url"]
#         model = provider["model"]
#         provider_name = provider["name"]

#         # Never log the API key — only the provider name and model
#         logger.info(f"[LLM] Selected API: {provider_name} | Model: {model}")

#         url = f"{base_url}/chat/completions"
#         headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type":  "application/json",
#         }
#         payload = {
#             "model": model,
#             "messages": messages,
#         }

#         last_error = None
#         for attempt in range(1, self._max_attempts + 1):
#             try:
#                 logger.info(f"[LLM] {provider_name} attempt {attempt}/{self._max_attempts}")
#                 response = requests.post(
#                     url=url,
#                     headers=headers,
#                     json=payload,
#                     timeout=self._timeout_sec,
#                 )
#                 response.raise_for_status()
#                 data = response.json()

#                 if "choices" not in data:
#                     raise RuntimeError(f"LLM API error: {data.get('error', data)}")

#                 raw = data["choices"][0]["message"]["content"]
#                 logger.info(f"[LLM] {provider_name} succeeded on attempt {attempt} | Model: {model}")
#                 return raw

#             except Exception as e:
#                 last_error = e
#                 if self._is_retryable(e) and attempt < self._max_attempts:
#                     backoff = self._delay_sec * (self._backoff_multiplier ** (attempt - 1))
#                     logger.warning(
#                         f"[LLM] {provider_name} attempt {attempt} failed: {type(e).__name__}: {e}"
#                     )
#                     logger.info(f"[LLM] Retrying in {backoff:.1f}s...")
#                     time.sleep(backoff)
#                 else:
#                     logger.error(
#                         f"[LLM] {provider_name} failed after {attempt} attempts: {type(e).__name__}: {e}"
#                     )
#                     break

#         raise last_error

#     def call(self, system_prompt: str, user_message: str) -> str:
#         """
#         Call the LLM with full retry + fallback chain.

#         Tries each provider in order (primary -> secondary model_1 -> secondary model_2).
#         Each provider gets the full retry count before falling back.

#         Returns the raw response text on success.
#         Raises RuntimeError if ALL providers fail (caller should handle gracefully).
#         """
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {"role": "user",   "content": user_message},
#         ]

#         if not self._providers:
#             raise RuntimeError("No LLM providers configured — cannot make LLM call")

#         last_error = None
#         for i, provider in enumerate(self._providers):
#             provider_name = provider["name"]
#             model = provider["model"]

#             if i > 0:
#                 logger.warning(
#                     f"[LLM] Fallback activated: switching to {provider_name} | Model: {model}"
#                 )

#             try:
#                 result = self._call_single_provider(provider, messages)
#                 logger.info(f"[LLM] Final success: {provider_name} | Model: {model}")
#                 return result
#             except Exception as e:
#                 last_error = e
#                 logger.error(f"[LLM] {provider_name} failed after all retries: {e}")
#                 if i < len(self._providers) - 1:
#                     next_provider = self._providers[i + 1]
#                     logger.warning(
#                         f"[LLM] Fallback: {provider_name} failed, switching to "
#                         f"{next_provider['name']} | Model: {next_provider['model']}"
#                     )
#                 else:
#                     logger.error(
#                         f"[LLM] Final failure: all LLM providers exhausted. Last error: {last_error}"
#                     )

#         raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


# # Singleton LLM client (application default credentials, from .env) —
# # initialized once on module load. Used for every job unless a user has
# # selected "Use My Own API Key" in Settings -> LLM Configuration, in
# # which case build_llm_client() below builds a separate, request-scoped
# # client with that user's own credentials instead.
# _llm_client = LLMClient(config)


# def build_llm_client(user_id: int = None) -> "LLMClient":
#     """
#     Returns the LLMClient to use for a given user/customer.

#     - No user_id, or the user has never configured this / has selected
#       "Default Application API Key": returns the shared singleton
#       `_llm_client`, built from the application's .env credentials.
#     - The user has selected "Use My Own API Key": builds and returns a
#       NEW LLMClient scoped to just this call, using that user's own
#       (decrypted) credentials. Never mutates os.environ or the shared
#       singleton, so one customer's key can never leak into another
#       customer's request — see database.get_llm_settings()/save_llm_settings().

#     Any failure to read the user's settings (DB down, decryption failure,
#     etc.) safely falls back to the application default client rather than
#     raising — a Settings-page/DB hiccup must never take down report
#     generation for users who never opted into a custom key.
#     """
#     if user_id is None:
#         return _llm_client

#     try:
#         import database  # local import: job_manager.py must stay importable standalone/in tests without a DB configured
#         settings = database.get_llm_settings(user_id)
#     except Exception as e:
#         logger.error(f"build_llm_client({user_id}): failed to load LLM settings, using application default: {e}")
#         return _llm_client

#     if not settings or not settings.get("use_custom_key"):
#         return _llm_client

#     overrides = {
#         "primary_api_key": settings.get("primary_api_key", ""),
#         "secondary_api_key": settings.get("secondary_api_key", ""),
#     }
#     if not overrides["primary_api_key"] and not overrides["secondary_api_key"]:
#         # Custom mode selected but nothing actually stored (e.g. encryption
#         # unavailable at save time) — fall back rather than making a
#         # provider-less LLMClient that can only fail.
#         logger.warning(f"build_llm_client({user_id}): custom mode selected but no usable key found, using application default")
#         return _llm_client

#     logger.info(f"[LLM] Using custom API key configuration for user_id={user_id}")
#     return LLMClient(config, key_overrides=overrides)

# # Backward compatibility: keep these module-level variables for any
# # code that still references them directly.
# OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or config.get("llm", {}).get("openrouter_api_key", "")
# LLM_MODEL          = config.get("llm", {}).get("model", "cohere/north-mini:free")

# if not OPENROUTER_API_KEY:
#     logger.warning(
#         "OPENROUTER_API_KEY is not set (env var or config.yaml). "
#         "LLM workflow analysis will use fallback providers if configured."
#     )

# # ==================================================
# # MASTER PROMPT
# # ==================================================

# MASTER_PROMPT = """
# You are a workflow analyst. Your job is to match audio narration with video actions
# to create a unified workflow description of a tutorial.

# CORE TASK

# For each step in the tutorial:
# 1. Understand what the AUDIO narrator is explaining
# 2. Understand what the VIDEO shows the user doing
# 3. Determine if both describe the SAME workflow step
# 4. If YES: Create a COMBINED UNDERSTANDING
# 5. If NO: Flag for MANUAL VALIDATION

# ═════════════════════════════════════════════════════════════════════════
# MATCHING LOGIC (WORKFLOW-BASED - NO SCORING)
# ═════════════════════════════════════════════════════════════════════════

# A CORRECT MATCH means:
# - Audio intent = Video action (same workflow step)
# - Wording CAN be different
# - Workflow meaning MUST be identical

# MATCHING EXAMPLES

# Example 1:
# Audio:     "Tap the profile icon."
# Video:     "User clicks account avatar in top-right corner."
# Match?     YES
# Reason:    Both describe opening the profile menu (same workflow step)
# Combined:  "User opens Google account menu using the profile icon."

# Example 2:
# Audio:     "Scroll down until you find Language settings."
# Video:     "User scrolls through settings page."
# Match?     YES
# Reason:    Both describe scrolling to find language option (same workflow step)
# Combined:  "User scrolls through settings page to locate Language option."

# Example 3:
# Audio:     "Select the Personal Info option."
# Video:     "User taps Personal Info tab."
# Match?     YES
# Reason:    Both describe accessing Personal Info (same workflow step)
# Combined:  "User opens Personal Info section from account settings."

# ═════════════════════════════════════════════════════════════════════════
# MANUAL VALIDATION TRIGGERS (WHEN TO FLAG)
# ═════════════════════════════════════════════════════════════════════════

# Flag for MANUAL VALIDATION if ANY of these apply:

# CASE 1: Different Actions
# Audio:  "Tap Language option."
# Video:  "User opens Security settings."
# Reason: Different workflow steps - cannot combine

# CASE 2: Promotional Audio (NOT part of workflow)
# Audio:  "Subscribe to my channel for more videos."
# Video:  "User changes account language."
# Reason: Audio is promotional, not a workflow instruction - IGNORE THIS AUDIO

# CASE 3: Ambiguous Video
# Audio:  "Tap Add Language button."
# Video:  "A popup appears but no clear action visible."
# Reason: Cannot confirm if the action actually occurred on screen

# CASE 4: Missing Visual Evidence
# Audio:  "Save your changes."
# Video:  "User scrolls around but doesn't tap Save button."
# Reason: Expected action not visible in video

# CASE 5: Timing Mismatch
# Audio:  "Open Personal Information."
# Video:  "User is already editing language preferences."
# Reason: Audio timing doesn't match video - workflow steps misaligned

# CASE 6: Decorative UI Elements
# Audio:  [Relevant instruction]
# Video:  "Subscribe button animation plays" OR "Bell icon appears" OR "Logo animation"
# Reason: Video shows UI element, not user action - ignore video, use audio only
#         OR flag if unclear

# CONTENT TO IGNORE (Not Part of Workflow)

# DO NOT create steps for:

# Promotional messages:
# - "Subscribe to the channel"
# - "Like and share this video"
# - "Hit the notification bell"

# Greetings:
# - "Welcome back everyone"
# - "Hi there, thanks for watching"

# Outro statements:
# - "Thanks for watching"
# - "Don't forget to like"
# - "See you next time"

# Filler speech:
# - "Okay..."
# - "Now..."
# - "Let's continue..."
# - "So..."

# Decorative UI animations:
# - Subscribe button animations
# - Bell icon animations
# - Logo animations
# - Watermarks
# - Intro graphics

# If these appear in video but do NOT correspond to workflow actions:
# → IGNORE them
# → Do NOT create a workflow step

# ═════════════════════════════════════════════════════════════════════════
# OUTPUT FORMAT — STRICT JSON (PRIMARY)
# ═════════════════════════════════════════════════════════════════════════

# Output a single valid JSON object — no markdown, no code fences, no commentary.

# Exact schema:

# {
#   "process_description": "One sentence (max 12 words) describing what process this tutorial demonstrates.",
#   "process_overview": "2-4 sentence paragraph, written only AFTER you have analyzed every step in section_a, summarizing the complete process end-to-end: what it accomplishes, roughly how many steps it takes, and the overall path from the first step to the last. Must be generated fresh from the actual detected steps every time — never generic or boilerplate text.",
#   "section_a": [
#     {
#       "step": 1,
#       "time_range": "00:00 - 00:05",
#       "description": "Opening Google Account",
#       "actions": "User taps the profile icon to open the Google account menu.",
#       "screenshot": "frame_0000.jpg"
#     }
#   ],
#   "section_b": [
#     {
#       "number": 1,
#       "time_range": "00:45 - 00:50",
#       "audio_understanding": "Narrator says to save changes.",
#       "video_understanding": "User scrolls but does not tap Save.",
#       "reason_for_manual_review": "Missing visual evidence of save action.",
#       "screenshot": "frame_0015.jpg"
#     }
#   ]
# }

# FIELD RULES:
# - "step" / "number": integer, sequential starting from 1
# - "time_range": string in "HH:MM - HH:MM" or "MM:SS - MM:SS" format
# - "description": 3-6 words, short title of the step
# - "actions": one concise sentence (combined audio + video)
# - "audio_understanding": one sentence of what narrator says
# - "video_understanding": one sentence of what video shows
# - "reason_for_manual_review": one sentence, reference the case (Case 1–6)
# - "screenshot": EXACT filename from the VIDEO JSON (e.g. "frame_0004.jpg") — NEVER invented
# - "process_overview": derive this ONLY from the steps you actually produced in
#   section_a for THIS run — never copy an overview from a previous run, never
#   use a generic template sentence like "This process automates X". Reference
#   the real number of steps and the real start/end actions.
# - If section_b has no items, return "section_b": []
# - Output ONLY the JSON object — nothing before or after it

# ═════════════════════════════════════════════════════════════════════════
# SCREENSHOT PATH SELECTION RULES (CRITICAL — READ CAREFULLY)
# ═════════════════════════════════════════════════════════════════════════

# HOW TO PICK THE CORRECT SCREENSHOT FOR EACH STEP:

# RULE 1 — PICK THE FRAME WHERE THE ACTION IS COMPLETED, NOT WHERE IT STARTS.

#   WRONG: Picking the frame where the user is about to click a button
#   RIGHT: Picking the frame where the button has already been clicked and the result is visible

#   Example:
#   Step: "User clicks the Blank button to open a new form"
#   WRONG frame: frame where cursor is hovering over the Blank button
#   RIGHT frame: frame where the new blank form is already open on screen

# RULE 2 — THE SCREENSHOT MUST SHOW THE OUTCOME OF THE ACTION.

#   The result of the action must be visible in the chosen frame.
#   If the action is "User types the form title", pick the frame where the typed title is visible.
#   If the action is "User clicks Send", pick the frame where the Send dialog is open.
#   If the action is "User submits the quiz", pick the frame where the submission confirmation appears.

# RULE 3 — FOR SECTION B (MANUAL VALIDATION), PICK THE FRAME THAT BEST SHOWS THE CONFLICT.

#   Pick the frame where the mismatch between audio and video is most clearly visible.
#   This should be the frame where the ambiguity or conflict is easiest for a human reviewer to spot.

# RULE 4 — USE EXACT FILENAMES FROM THE VIDEO JSON.

#   Only use frame filenames that actually exist in the VIDEO JSON data provided.
#   Do NOT guess or invent frame filenames.
#   Match the timestamp of the completed action to the closest available frame in the JSON.

# RULE 5 — NEVER PICK THE FIRST FRAME OF A STEP AS DEFAULT.

#   Do not default to picking the earliest frame in the time range.
#   Always scan through all frames in the time range and pick the one showing completion.

# SCREENSHOT SELECTION EXAMPLE:

#   Step: "User clicks the Answer key option and selects the correct answer"
#   Time Range: 00:28 - 00:33
#   Available frames in this range: frame_0028.jpg, frame_0030.jpg, frame_0032.jpg

#   frame_0028.jpg → User is clicking Answer key (action starting)
#   frame_0030.jpg → Answer key panel is open (action in progress)
#   frame_0032.jpg → Correct answer is selected and highlighted (action COMPLETED)

#   CORRECT CHOICE: frame_0032.jpg  ← outcome is visible here

# ═════════════════════════════════════════════════════════════════════════
# DECISION TREE (HOW TO ANALYZE)
# ═════════════════════════════════════════════════════════════════════════

# For EACH audio segment + video frame pair:

# Step 1: Extract Audio Meaning
# - What is the narrator instructing the user to do?
# - Ignore if promotional/filler/outro

# Step 2: Extract Video Meaning
# - What action is the user actually performing?
# - Ignore if decorative UI (animations, logos, bells, etc.)

# Step 3: Compare Meanings
# - Do they describe the SAME workflow step?

#   YES (Same step) -> COMBINE THEM
#   - Fill description and actions fields in section_a
#   - For screenshot: find the frame where the action result is visible (COMPLETED state)

#   NO (Different steps) -> MANUAL VALIDATION
#   - Fill section_b object with reason:
#     - Different actions (Case 1)?
#     - Promotional audio (Case 2)?
#     - Ambiguous video (Case 3)?
#     - Missing evidence (Case 4)?
#     - Timing mismatch (Case 5)?
#   - For screenshot: pick frame where conflict is most visible

#   UNCLEAR -> MANUAL VALIDATION
#   - Send for human review in section_b

# ═════════════════════════════════════════════════════════════════════════
# CRITICAL RULES
# ═════════════════════════════════════════════════════════════════════════

# DO THIS:
# - Match workflow MEANING, not exact wording
# - Ignore promotional/greeting/outro content
# - Combine audio + video into ONE unified actions description
# - For screenshot: ALWAYS pick the frame where the action is COMPLETED and result is visible
# - Flag any ambiguity to section_b
# - Keep descriptions concise (1 sentence in actions field)
# - Output ONLY the JSON object — nothing else


# IF AUDIO IS EMPTY OR MISSING (no separate audio file uploaded AND no embedded audio track in the video):
# - Do not generate steps from audio
# - Use ONLY the video JSON as source
# - Keep "process_description" as a plain short title of the workflow — do NOT
#   add any "Note:" prefix or disclaimer yourself; the system adds the
#   video-only disclaimer separately as its own line in the document
# - "process_overview" must also be phrased purely in terms of what is visible
#   on screen — describe the sequence of visual steps only
# - Generate sequential steps in section_a from visual events only
# - Do not assume any spoken instructions or dialogue
# - If visual information is insufficient, describe only what is visibly observable
# - NEVER reference speech, conversations, sounds, transcripts, narration, or audio events anywhere in section_a, process_description, or process_overview — describe only what is visible on screen
# - section_b must be empty []


# DO NOT DO THIS:
# - Calculate any scores (similarity, confidence, percentage)
# - Use embeddings or algorithms
# - Invent actions not shown in either audio or video
# - Force matches between unrelated steps
# - Include promotional content as workflow steps
# - Skip Manual Validation for ambiguous cases
# - Add commentary, preamble, or closing text outside the JSON
# - Use markdown formatting, code fences, or tables
# - Pick the first or earliest frame of a time range by default
# - Pick a frame that shows the action starting instead of completing
# - Invent screenshot filenames — ONLY use exact filenames from the VIDEO JSON

# ═════════════════════════════════════════════════════════════════════════
# FINAL INSTRUCTION
# ═════════════════════════════════════════════════════════════════════════

# Analyze the audio and video JSONs provided.

# Output ONLY a single valid JSON object with two keys:
# 1. "section_a": list of verified workflow steps
# 2. "section_b": list of steps requiring manual review (empty list if none)

# For every screenshot field: select the frame where the action is COMPLETED and the outcome is clearly visible on screen — never the starting frame. Use ONLY exact filenames from the VIDEO JSON.

# No commentary. No markdown. No code fences. No explanation.
# Just the single clean JSON object.
# """


# # ==================================================
# # JOB NAMING
# # ==================================================

# def make_job_name(video_path: str) -> str:
#     stem = Path(video_path).stem
#     name = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
#     return name or f"job_{uuid.uuid4().hex[:6]}"


# def make_output_paths(job_name: str) -> dict:
#     AUDIO_JSON_DIR.mkdir(parents=True, exist_ok=True)
#     VIDEO_JSON_DIR.mkdir(parents=True, exist_ok=True)
#     REPORT_DIR.mkdir(parents=True, exist_ok=True)

#     return {
#         "audio_json":        AUDIO_JSON_DIR / f"{job_name}_audio.json",
#         "video_json":        VIDEO_JSON_DIR / f"{job_name}_video.json",
#         "section_a_clean":   REPORT_DIR     / f"{job_name}_workflow_steps_clean.docx",
#         "section_b":         REPORT_DIR     / f"{job_name}_workflow_validation.docx",
#     }


# # ==================================================
# # OUTPUT SAVERS
# # ==================================================

# def save_audio_result(job_name: str, audio_response: dict) -> Path:
#     paths = make_output_paths(job_name)
#     out   = paths["audio_json"]

#     payload = {
#         "metadata": {
#             "job_name":       job_name,
#             "service":        "audio",
#             "saved_at":       datetime.now().isoformat(),
#             "status":         audio_response.get("status"),
#             "request_id":     audio_response.get("request_id"),
#             "segments_count": audio_response.get("segments_count", 0),
#             "latency_sec":    audio_response.get("latency_sec"),
#         },
#         "result":   audio_response,
#         "segments": audio_response.get("segments", []),
#     }

#     with open(out, "w", encoding="utf-8") as f:
#         json.dump(payload, f, indent=2, ensure_ascii=False)

#     logger.info(f"Audio JSON saved: {out}")
#     return out


# def save_video_result(job_name: str, video_response: dict) -> Path:
#     paths = make_output_paths(job_name)
#     out   = paths["video_json"]

#     inner = video_response.get("result", {})
#     meta  = inner.get("metadata", {})

#     payload = {
#         "metadata": {
#             "job_name":       job_name,
#             "service":        "video",
#             "saved_at":       datetime.now().isoformat(),
#             "status":         video_response.get("status"),
#             "job_id":         video_response.get("id"),
#             "unique_actions": meta.get("unique_actions", 0),
#             "errors":         meta.get("errors", 0),
#             "latency_sec":    video_response.get("latency_sec"),
#         },
#         "result": video_response,
#     }

#     with open(out, "w", encoding="utf-8") as f:
#         json.dump(payload, f, indent=2, ensure_ascii=False)

#     logger.info(f"Video JSON saved: {out}")
#     return out


# # ==================================================
# # LLM WORKFLOW ANALYSIS
# # ==================================================

# def _build_user_message(audio_data: dict, video_data: dict) -> str:
#     import copy
#     # Strip base64 images before sending to LLM — text only
#     video_data_clean = copy.deepcopy(video_data)
#     for record in (
#         video_data_clean.get("result", {})
#                         .get("result", {})
#                         .get("frame_records", [])
#     ):
#         record.pop("anchor_image_b64", None)

#     # Check if audio is empty
#     segments = audio_data.get("segments", [])
#     if not segments:
#         audio_note = "NOTE: Audio segments are EMPTY. No audio was detected in this video. Generate all steps from video JSON only. Still set 'process_description' to a short, genuine title (max 12 words) describing the process shown in the VIDEO — do NOT put any note about missing/empty audio into process_description; that note is added separately by the application. Do not assume any spoken instructions. section_b should be empty []."
#     else:
#         audio_note = ""

#     return f"""Analyze the following audio and video data and generate the workflow report as a strict JSON object matching the schema in the system prompt.
# {audio_note}

# AUDIO JSON:
# {json.dumps(audio_data, indent=2)}

# VIDEO JSON:
# {json.dumps(video_data_clean, indent=2)}
# """


# def _parse_json_response(raw: str) -> dict:
#     """
#     Try to parse LLM response as strict JSON.
#     Strips markdown code fences if present.
#     Returns parsed dict with 'section_a' and 'section_b' keys.
#     Raises ValueError if parsing fails.
#     """
#     clean = raw.strip()
#     # Strip markdown code fences
#     if clean.startswith("```"):
#         lines = clean.splitlines()
#         clean = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
#     clean = clean.rstrip("`").strip()

#     # Find first { and last }
#     s = clean.find("{")
#     e = clean.rfind("}") + 1
#     if s != -1 and e > s:
#         clean = clean[s:e]

#     data = json.loads(clean)

#     if "section_a" not in data or "section_b" not in data:
#         raise ValueError("JSON missing section_a or section_b keys")

#     return data

# def _run_llm_analysis(
#     audio_data: dict,
#     video_data: dict,
#     user_id: int = None
# ) -> tuple:    """
#     Call LLM with full retry + fallback chain via LLMClient.
#     Returns (section_a_rows, section_b_rows, process_description, process_overview).
#     """
#     user_message = _build_user_message(audio_data, video_data)

#     # FIX: the LLM call is now wrapped in its own try/except. Previously,
#     # when no provider was configured at all, LLMClient.call() raised
#     # RuntimeError HERE, before any parsing or fallback logic ran — and
#     # that exception escaped this function entirely, landing in the outer
#     # try/except in run_workflow_analysis(), which just returned empty
#     # rows and never touched _build_fallback_rows_from_video(). That's why
#     # the docx table was completely empty instead of showing the one
#     # detected action.
#     try:
#         raw = build_llm_client(user_id).call(MASTER_PROMPT, user_message)
#     except Exception as e:
#         logger.warning(
#             f"LLM call failed entirely ({e}) — building Section A directly "
#             "from the video service's detected actions"
#         )
#         a_rows = _build_fallback_rows_from_video(video_data)
#         # Return the real error message (not empty strings) so the caller
#         # can show WHY the LLM path failed instead of a generic message.
#         return a_rows, [], "", f"__LLM_ERROR__:{e}"

#     # ── Try JSON path first ──────────────────────────────────
#     try:
#         parsed = _parse_json_response(raw)
#         section_a          = parsed.get("section_a", [])
#         section_b          = parsed.get("section_b", [])
#         process_description = parsed.get("process_description", "")
#         process_overview   = parsed.get("process_overview", "")
#         logger.info(f"LLM response parsed as JSON | section_a={len(section_a)} | section_b={len(section_b)} | desc={process_description}")

#         a_rows = []
#         for item in section_a:
#             a_rows.append({
#                 "Step":        str(item.get("step", "")),
#                 "Description": item.get("description", ""),
#                 "Actions":     item.get("actions", ""),
#                 "Screenshot":  item.get("screenshot", ""),
#             })

#         b_rows = []
#         for item in section_b:
#             b_rows.append({
#                 "#":                       str(item.get("number", "")),
#                 "Time Range":              item.get("time_range", ""),
#                 "Audio Understanding":     item.get("audio_understanding", ""),
#                 "Video Understanding":     item.get("video_understanding", ""),
#                 "Reason for Manual Review": item.get("reason_for_manual_review", ""),
#                 "Screenshot":              item.get("screenshot", ""),
#             })

#         # NEW: even if the LLM returned valid JSON, if it decided there
#         # were zero steps, still fall back to the video service's own
#         # detections rather than shipping an empty table.
#         if not a_rows:
#             logger.warning(
#                 "LLM JSON parsed but section_a was empty — building "
#                 "Section A directly from the video service's detected actions"
#             )
#             a_rows = _build_fallback_rows_from_video(video_data)

#         return a_rows, b_rows, process_description, process_overview

#     except (ValueError, json.JSONDecodeError, KeyError) as e:
#         json_parse_error = e
#         logger.warning(f"JSON parse failed ({e}) — falling back to markdown parser")
#         logger.debug(f"Raw LLM response that failed JSON parsing:\n{raw}")

#     # ── Fallback: markdown parser ────────────────────────────
#     logger.info("Using markdown fallback parser")
#     a_rows, b_rows = _parse_markdown_tables(raw)

#     if not a_rows:
#         logger.warning(
#             "Markdown fallback parser also produced no rows — building "
#             "Section A directly from the video service's detected actions"
#         )
#         a_rows = _build_fallback_rows_from_video(video_data)

#     # Same as the "LLM call failed entirely" branch above: surface the real
#     # reason the JSON schema wasn't honored, instead of returning a silent
#     # empty string that the caller can't explain to the user.
#     return a_rows, b_rows, "", f"__LLM_ERROR__:LLM response was not valid JSON ({json_parse_error})"

# def _build_fallback_rows_from_video(video_data: dict) -> list:
#     """
#     Last-resort Section A rows built directly from the Video service's own
#     detected actions (frame_records / consolidated_timeline), used only
#     when the LLM response could not be parsed as JSON *or* as the legacy
#     markdown table format. Guarantees the generated document always
#     reflects what was actually observed in the video instead of shipping
#     with an empty steps table.
#     """
#     inner = video_data.get("result", {}).get("result", {})
#     frame_records = inner.get("frame_records", [])

#     # Keep only the non-duplicate actions (skip frames the video service
#     # itself flagged as semantically identical to a previous one), in
#     # their original chronological order.
#     kept = [r for r in frame_records if not r.get("is_duplicate") and r.get("final_action")]

#     rows = []
#     for idx, rec in enumerate(kept, start=1):
#         action = rec.get("final_action", "").strip()
#         rows.append({
#             "Step":        str(idx),
#             "Description": action[:60],
#             "Actions":     action,
#             "Screenshot":  rec.get("anchor_frame_file", ""),
#         })
#     return rows


# # ==================================================
# # MARKDOWN PARSER — extract section A and B rows
# # ==================================================

# def _parse_markdown_tables(markdown_text: str) -> tuple:
#     """
#     Parse markdown into two lists of row dicts:
#       section_a_rows — all columns from Section A
#       section_b_rows — all columns from Section B
#     """
#     section_a_rows = []
#     section_b_rows = []

#     lines         = markdown_text.splitlines()
#     current       = None
#     headers       = []

#     for line in lines:
#         line = line.strip()

#         if "SECTION A" in line:
#             current = "A"
#             headers = []
#             continue
#         if "SECTION B" in line:
#             current = "B"
#             headers = []
#             continue

#         if not line.startswith("|"):
#             continue
#         if line.startswith("|---") or line.startswith("|:--"):
#             continue

#         cells = [c.strip() for c in line.strip("|").split("|")]

#         if not headers:
#             headers = cells
#             continue

#         row = {}
#         for idx, h in enumerate(headers):
#             row[h] = cells[idx] if idx < len(cells) else ""

#         if current == "A":
#             section_a_rows.append(row)
#         elif current == "B":
#             section_b_rows.append(row)

#     return section_a_rows, section_b_rows


# # ==================================================
# # FRAME IMAGE FETCHER — via HTTP from Video Service
# # ==================================================

# VIDEO_SERVICE_URL = config.get("services", {}).get("video", {}).get("url", "http://localhost:8022")


# def _fetch_frame_image(screenshot_path: str, video_data: dict) -> bytes:
#     """
#     Given a screenshot filename from LLM output,
#     fetch the actual frame image from Video service via HTTP.
#     Returns image bytes or empty bytes if not found.
#     Includes lightweight retry for transient network failures.
#     """
#     if not screenshot_path:
#         return b""

#     fname  = Path(screenshot_path).name  # e.g. "frame_0004.jpg"
#     job_id = video_data.get("metadata", {}).get("job_id") or video_data.get("result", {}).get("id", "")

#     if not job_id:
#         logger.warning(f"No job_id in video_data — cannot fetch frame {fname}")
#         return b""

#     url = f"{VIDEO_SERVICE_URL}/frames/{job_id}/{fname}"
#     max_attempts = 2
#     for attempt in range(1, max_attempts + 1):
#         try:
#             resp = requests.get(url, timeout=10)
#             if resp.status_code == 200:
#                 return resp.content
#             else:
#                 logger.warning(f"Frame fetch failed {url}: {resp.status_code}")
#                 if attempt < max_attempts:
#                     time.sleep(1)
#         except Exception as e:
#             logger.warning(f"Frame fetch error {url} (attempt {attempt}): {e}")
#             if attempt < max_attempts:
#                 time.sleep(1)
#     return b""


# def _add_image_to_cell(cell, img_bytes: bytes) -> None:
#     """Embed image bytes into a docx table cell."""
#     import io
#     try:
#         img_stream = io.BytesIO(img_bytes)
#         p   = cell.paragraphs[0]
#         run = p.add_run()
#         run.add_picture(img_stream, width=Inches(2.5))
#     except Exception as e:
#         cell.paragraphs[0].add_run(f"[Image error: {e}]")


# def _build_process_overview(rows: list, process_title: str, video_data: dict = None, error_detail: str = "") -> str:
#     """
#     Used ONLY when the LLM did not return a "process_overview" field for
#     this run (LLM call failed entirely, no provider configured, or the raw
#     response failed both the JSON and markdown parsers).

#     This is intentionally NOT a synthesized summary — it does not fabricate
#     "This process consists of N steps: it begins with X and concludes with
#     Y" style sentences that imitate AI-written analysis using string
#     templates. That kind of templated text is what was making the document
#     look "hardcoded" even when the LLM had actually failed. Instead this
#     states plainly that the overview could not be generated, and — when
#     available — includes the real reason the LLM call failed, so the cause
#     (missing/invalid API key, network issue, model unavailable, etc.) is
#     visible directly in the document instead of only in the logs.
#     """
#     reason_line = f" Reason: {error_detail}" if error_detail else ""

#     if rows:
#         return (
#             "The AI service did not return a process overview for this run, "
#             "so this section could not be generated. The steps identified "
#             "below are shown as detected. Please verify the LLM configuration "
#             "(e.g. PRIMARY_LLM_API_KEY / OPENROUTER_API_KEY) and re-generate "
#             f"this document to get a full, AI-written overview.{reason_line}"
#         )
#     return (
#         "The AI service did not return a process overview or process steps "
#         "for this run. Please verify the LLM configuration (e.g. "
#         f"PRIMARY_LLM_API_KEY / OPENROUTER_API_KEY) and re-generate this document.{reason_line}"
#     )


# def _write_section_a_clean_docx(rows: list, output_file: Path, video_data: dict = None, process_description: str = "", no_audio: bool = False, process_overview: str = "") -> None:
#     """Section A — BRD format docx with centered title, process overview, and steps table."""
#     from docx.shared import Pt, RGBColor
#     from docx.enum.text import WD_ALIGN_PARAGRAPH

#     doc = Document()

#     process_title = process_description or "Workflow Process"

#     # ── Title: Business Requirements Document (centered, large) ──
#     title_para = doc.add_paragraph()
#     title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
#     title_run = title_para.add_run("Business Requirements Document")
#     title_run.bold = True
#     title_run.font.size = Pt(20)

#     # ── "For" line (centered) ──
#     for_para = doc.add_paragraph()
#     for_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
#     for_para.add_run("For")

#     # ── Process title (centered, from LLM description) ──
#     proc_para = doc.add_paragraph()
#     proc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
#     proc_run = proc_para.add_run(process_title)
#     proc_run.bold = True
#     proc_run.font.size = Pt(14)

#     # ── Note: shown only when no audio was detected ──
#     if no_audio:
#         note_para = doc.add_paragraph()
#         note_run = note_para.add_run("Note: The output is based only on video frames.")
#         note_run.bold = True
#         note_run.italic = True
#         note_run.font.size = Pt(11)
#         note_run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

#     doc.add_paragraph()  # spacer

#     # ── 1. Process Overview ──
#     doc.add_heading("1.  Process Overview:", level=2)
#     overview_para = doc.add_paragraph()
#     overview_para.add_run(process_overview or _build_process_overview(rows, process_title, video_data))

#     doc.add_paragraph()  # spacer

#     # ── 2. Process Steps ──
#     doc.add_heading("2.  Process Steps:", level=2)

#     headers = ["Step", "Description", "Actions", "Screenshot"]
#     table   = doc.add_table(rows=1, cols=len(headers))
#     table.style = "Table Grid"

#     hdr_cells = table.rows[0].cells
#     for idx, h in enumerate(headers):
#         hdr_cells[idx].text = h

#     for row in rows:
#         cells = table.add_row().cells
#         cells[0].text = row.get("Step", "")
#         cells[1].text = row.get("Description", "")
#         cells[2].text = row.get("Actions", "")

#         # Fetch actual image from Video service
#         img_bytes = _fetch_frame_image(row.get("Screenshot", ""), video_data or {})
#         if img_bytes:
#             cells[3].paragraphs[0].clear()
#             _add_image_to_cell(cells[3], img_bytes)
#         else:
#             cells[3].text = row.get("Screenshot Path", "")

#     doc.save(str(output_file))


# def _write_section_b_docx(rows: list, output_file: Path, video_data: dict = None) -> None:
#     """Section B — manual validation docx with embedded images."""
#     doc = Document()
#     doc.add_heading("Manual Validation Required", level=2)

#     headers = ["#", "Time Range", "Audio Understanding", "Video Understanding",
#            "Reason for Manual Review", "Screenshot"]
#     table   = doc.add_table(rows=1, cols=len(headers))
#     table.style = "Table Grid"

#     hdr_cells = table.rows[0].cells
#     for idx, h in enumerate(headers):
#         hdr_cells[idx].text = h

#     for row in rows:
#         cells = table.add_row().cells
#         cells[0].text = row.get("#", "")
#         cells[1].text = row.get("Time Range", "")
#         cells[2].text = row.get("Audio Understanding", "")
#         cells[3].text = row.get("Video Understanding", "")
#         cells[4].text = row.get("Reason for Manual Review", "")

#         # Fetch actual image from Video service
#         img_bytes = _fetch_frame_image(row.get("Screenshot", ""), video_data or {})
#         if img_bytes:
#             cells[5].paragraphs[0].clear()
#             _add_image_to_cell(cells[5], img_bytes)
#         else:
#             cells[5].text = row.get("Screenshot Path", "")

#     doc.save(str(output_file))


# # ==================================================
# # EMAIL SENDER
# # ==================================================

# EMAIL_CFG = config.get("email", {})

# def send_email_with_attachments(
#     recipient_email: str,
#     username: str,
#     attachment_paths: list,
#     job_name: str = "",
# ) -> None:
#     """
#     Send output docx files as email attachments to the user.
#     Reads SMTP settings from config.yaml under the 'email' key.
#     """
#     import smtplib
#     from email.mime.multipart import MIMEMultipart
#     from email.mime.base import MIMEBase
#     from email.mime.text import MIMEText
#     from email import encoders

#     smtp_host     = EMAIL_CFG.get("smtp_host", "smtp.gmail.com")
#     smtp_port     = EMAIL_CFG.get("smtp_port", 587)
#     sender_email  = EMAIL_CFG.get("sender_email", "")
#     sender_pass   = os.environ.get("EMAIL_SENDER_PASSWORD") or EMAIL_CFG.get("sender_password", "")
#     sender_name   = EMAIL_CFG.get("sender_name", "OneNextGen Automation Pvt Ltd")

#     if not sender_email or not sender_pass:
#         logger.warning("Email credentials not configured — skipping email send.")
#         return

#     process_title = job_name.replace("_", " ").title() if job_name else "Workflow Process"

#     msg = MIMEMultipart()
#     msg["From"]    = f"{sender_name} <{sender_email}>"
#     msg["To"]      = recipient_email
#     msg["Subject"] = "Your Business Requirements Document is Ready"

#     body = f"""Hi {username},

# Your process flow document has been created successfully with all the steps defined in the video.

# Please find the attached Business Requirements Document:

# Process Description: {process_title}

# Document Contents:
#   1. Workflow Steps (Section A) — verified workflow steps with screenshots
#   2. Manual Validation (Section B) — steps requiring manual review

# Best regards,
# {sender_name}
# """
#     msg.attach(MIMEText(body, "plain"))

#     for path in attachment_paths:
#         p = Path(path)
#         if not p.exists():
#             logger.warning(f"Attachment not found, skipping: {path}")
#             continue
#         with open(p, "rb") as f:
#             part = MIMEBase("application", "octet-stream")
#             part.set_payload(f.read())
#         encoders.encode_base64(part)
#         part.add_header(
#             "Content-Disposition",
#             f"attachment; filename={p.name}",
#         )
#         msg.attach(part)

#     try:
#         with smtplib.SMTP(smtp_host, smtp_port) as server:
#             server.starttls()
#             server.login(sender_email, sender_pass)
#             server.sendmail(sender_email, recipient_email, msg.as_string())
#         logger.info(f"Email sent to {recipient_email}")
#     except Exception as e:
#         logger.error(f"Failed to send email to {recipient_email}: {e}")


# # ==================================================
# # MAIN WORKFLOW ANALYSIS
# # ==================================================

# def run_workflow_analysis(
#     job_name:        str,
#     audio_json_path: Path,
#     video_json_path: Path,
#     username:        str = "",
#     recipient_email: str = "",
#     case3:           bool = None,
#     user_id:         int = None,
# ) -> Path:
#     """
#     Load audio + video JSONs → call the LLM with both complete JSONs so
#     it can reason about the full temporal/contextual relationship between
#     narration and visuals in a single pass → save:
#       1. <job>_workflow_steps_clean.docx    (Section A, BRD format, images embedded)
#       2. <job>_workflow_validation.docx     (Section B, images embedded)
#     If recipient_email is provided, sends both files as email attachments.
#     Returns path to the Section A clean docx.

#     `user_id`: whose Settings -> LLM Configuration to use for this call —
#     see build_llm_client(). None (the default) always uses the
#     application's .env credentials, same as before this parameter existed.

#     The LLM call uses the full retry + fallback chain (LLMClient). If all
#     providers fail, the function returns empty section rows gracefully —
#     the pipeline never crashes.

#     `case3`, when True, means no separate audio was uploaded AND no embedded
#     audio track was found (the user confirmed "Continue" using video frames
#     only). When True, section_b is always forced empty — there's no audio to
#     cross-validate against. If not provided, it's inferred from whether the
#     audio JSON has any segments (kept as a fallback for direct callers).
#     """
#     paths = make_output_paths(job_name)

#     logger.info(f"[{job_name}] Starting LLM workflow analysis...")

#     with open(audio_json_path, encoding="utf-8") as f:
#         audio_data = json.load(f)
#     with open(video_json_path, encoding="utf-8") as f:
#         video_data = json.load(f)

#     if case3 is None:
#         case3 = not audio_data.get("segments", [])

#     # ── Single unified LLM call over the COMPLETE audio JSON and COMPLETE
#     # video JSON together, with full retry + fallback via LLMClient.
#     try:
#         section_a_rows, section_b_rows, process_description, process_overview = _run_llm_analysis(
#         audio_data,
#         video_data,
#         user_id
#         )
#     except Exception as e:
#         logger.error(f"[{job_name}] LLM analysis failed after all retries and fallbacks: {e}")
#         section_a_rows, section_b_rows = [], []
#         process_description = ""
#         process_overview = f"__LLM_ERROR__:{e}"

#     logger.info(f"[{job_name}] LLM analysis complete | section_a={len(section_a_rows)} | section_b={len(section_b_rows)}")

#     if case3:
#         # Case 3 always means: section_b is empty (nothing to cross-validate
#         # against audio), regardless of what the LLM returned.
#         section_b_rows = []
#         logger.info(f"[{job_name}] Case 3 — output generated using video frames only")

#     # Fallback process description to job_name if LLM didn't provide one
#     if not process_description:
#         process_description = job_name.replace("_", " ").title()

#     # If the LLM call itself threw an exception, _run_llm_analysis tags the
#     # overview slot with the real error so we can show WHY it failed instead
#     # of a generic message — surface that here, then clear the tag so the
#     # rest of the pipeline (and the docx) sees a normal readable sentence.
#     llm_error_detail = ""
#     if process_overview.startswith("__LLM_ERROR__:"):
#         llm_error_detail = process_overview[len("__LLM_ERROR__:"):]
#         process_overview = ""

#     # Fallback process overview if the LLM didn't provide one (parse failure,
#     # markdown-fallback path, or the model simply omitted the field) — build
#     # a short sentence from the actual step descriptions rather than leaving
#     # the overview blank.
#     if not process_overview:
#         process_overview = _build_process_overview(
#             section_a_rows, process_description, video_data, llm_error_detail
#         )

#     # 1 & 2. Section A + Section B docx — independent outputs once the rows
#     # above are computed, so write them concurrently.
#     with ThreadPoolExecutor(max_workers=2) as pool:
#         fut_a = pool.submit(
#             _write_section_a_clean_docx,
#             section_a_rows, paths["section_a_clean"], video_data, process_description, case3, process_overview,
#         )
#         fut_b = pool.submit(
#             _write_section_b_docx,
#             section_b_rows, paths["section_b"], video_data,
#         )
#         fut_a.result()
#         fut_b.result()

#     logger.info(f"[{job_name}] Section A clean docx saved: {paths['section_a_clean']}")
#     logger.info(f"[{job_name}] Section B validation docx saved: {paths['section_b']}")

#     # 3. Send email if recipient provided
#     if recipient_email and EMAIL_CFG.get("enabled", False):
#         try:
#             send_email_with_attachments(
#                 recipient_email=recipient_email,
#                 username=username or job_name,
#                 attachment_paths=[paths["section_a_clean"], paths["section_b"]],
#                 job_name=process_description,
#             )
#         except Exception as e:
#             logger.error(f"[{job_name}] Email sending failed: {e}")

#     return paths["section_a_clean"]


###############################################################
# ORCHESTRATOR — JOB MANAGER
# Job naming, output path routing, JSON saving, LLM analysis
###############################################################

import copy
import json
import logging
import os
import re
import time
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import yaml
from docx import Document
from docx.shared import Inches

# Load repo-root .env (if present) so LLM API keys and EMAIL_SENDER_PASSWORD
# are actually set in the process
# environment before LLMClient reads them below — same pattern already used
# in database.py, integrated_pipeline.py, pipeline_v3_1_production.py, and
# video_service/app.py. Without this, job_manager.py silently sees empty env
# vars whenever it's imported/run before run_backend.py's own load_dotenv()
# call, which is what was causing every LLM call to fail and fall back to
# the job_name-based title and the generic "AI service did not return an
# overview" text (looked "hardcoded" but was actually a missing .env load).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

logger = logging.getLogger("JobManager")

# ==================================================
# CONFIG
# ==================================================

# PORTABLE PATH: works unchanged on Colab, Kaggle, or a local machine.
_DEFAULT_CONFIG_PATH = str(
    Path(__file__).resolve().parent.parent / "Configuration" / "config.yaml"
)


def _load_config(path: str = None) -> dict:
    path = path or os.environ.get("CONFIG_PATH", _DEFAULT_CONFIG_PATH)
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        # SECURITY: no secret fallback value here — if config.yaml can't be
        # read, the API keys below will also be empty and the LLM call
        # will fail loudly (raise_for_status) instead of silently using
        # a leaked key.
        return {
            "output": {
                "audio_json_dir": "output/audio_json",
                "video_json_dir": "output/video_json",
                "report_dir": "output/reports",
            },
            "llm": {
                "retry": {
                    "max_attempts": 3,
                    "delay_sec": 2,
                    "backoff_multiplier": 2.0,
                    "timeout_sec": 60
                },
                "primary": {
                    "api_key_env": "PRIMARY_LLM_API_KEY",
                    "base_url": "https://openrouter.ai/api/v1",
                    "model": "cohere/north-mini:free",
                },
                "openrouter_api_key": "",
                "model": "cohere/north-mini:free",
            }
        }


config = _load_config()

AUDIO_JSON_DIR = Path(config["output"]["audio_json_dir"])
VIDEO_JSON_DIR = Path(config["output"]["video_json_dir"])
REPORT_DIR = Path(config.get("output", {}).get("report_dir", "output/reports"))

LLM_PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "deepseek": "https://api.deepseek.com",
    "xai": "https://api.x.ai/v1",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


def get_application_llm_api_key() -> str:
    """Return the application OpenRouter key, preserving legacy env names."""
    primary = config.get("llm", {}).get("primary", {})
    return (
        os.environ.get("PROCESSIQ_LLM_PRIMARY_API_KEY")
        or os.environ.get(primary.get("api_key_env", "PRIMARY_LLM_API_KEY"))
        or os.environ.get("OPENROUTER_API_KEY")
        or config.get("llm", {}).get("openrouter_api_key", "")
    )


def fetch_provider_models(provider_id: str, api_key: str) -> list:
    """Fetch a provider's model catalog using fixed, provider-owned URLs."""
    if not isinstance(provider_id, str) or provider_id not in LLM_PROVIDER_BASE_URLS:
        raise ValueError("Unsupported LLM provider.")

    base_url = LLM_PROVIDER_BASE_URLS[provider_id]
    headers = {"Accept": "application/json"}
    if provider_id == "anthropic":
        url = f"{base_url}/v1/models"
        headers.update({
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        })
    elif provider_id == "gemini":
        url = f"{base_url}/models"
        headers["x-goog-api-key"] = api_key
    else:
        url = f"{base_url}/models"
        headers["Authorization"] = f"Bearer {api_key}"

    response = requests.get(url=url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Provider returned an invalid model catalog.")

    if provider_id == "gemini":
        models = data.get("models", [])
        if not isinstance(models, list):
            raise RuntimeError("Provider returned an invalid model catalog.")
        return [
            {
                "id": item["name"][len("models/"):]
                if item["name"].startswith("models/") else item["name"],
                "name": item.get("displayName") or item["name"],
            }
            for item in models
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("supportedGenerationMethods"), list)
            and "generateContent" in item["supportedGenerationMethods"]
        ]

    models = data.get("data")
    if not isinstance(models, list):
        raise RuntimeError("Provider returned an invalid model catalog.")
    return [
        {"id": item["id"], "name": item.get("name") or item["id"]}
        for item in models
        if isinstance(item, dict) and item.get("id")
    ]

# ==================================================
# LLM CLIENT — Retry
# ==================================================


class LLMClient:
    """
    LLM client with configurable retry behavior for one selected provider.

    Retry Logic:
      - Retries on: API timeout, Rate limit (429), Temporary server error (5xx),
        Connection error, Any recoverable API exception.
      - Uses configurable retry count and delay with exponential backoff.
      - Idempotent: the same immutable request payload is re-sent on every
        attempt, so no duplicate processing or inconsistent outputs can occur.

    Logging:
      - Logs retry attempts, retry failures, selected API/model, and outcomes.
      - NEVER logs API keys or other sensitive information.
    """

    def __init__(self, config_dict: dict, key_overrides: dict = None):
        """
        `key_overrides`, when given, lets a caller supply per-request
        credentials (e.g. a customer's own API keys from Settings ->
        LLM Configuration -> "Use My Own API Key") instead of the
        application's .env defaults, without touching os.environ or any
        other in-flight request. Expected shape:
            {"provider": "...", "model": "...", "primary_api_key": "..."}
        Never logged — see _call_single_provider().
        """
        self._llm_cfg = config_dict.get("llm", {})
        self._retry_cfg = self._llm_cfg.get("retry", {})
        self._max_attempts = self._retry_cfg.get("max_attempts", 3)
        self._delay_sec = self._retry_cfg.get("delay_sec", 2)
        self._backoff_multiplier = self._retry_cfg.get(
            "backoff_multiplier", 2.0
        )
        self._timeout_sec = self._retry_cfg.get("timeout_sec", 60)

        key_overrides = key_overrides or {}

        provider_id = key_overrides.get("provider", "openrouter")
        if not isinstance(provider_id, str) or provider_id not in LLM_PROVIDER_BASE_URLS:
            raise ValueError("Unsupported LLM provider.")

        self._providers = []

        primary = self._llm_cfg.get("primary", {})
        primary_key = (
            key_overrides.get("primary_api_key")
            or get_application_llm_api_key()
        )
        primary_model = key_overrides.get("model") or primary.get(
            "model", "cohere/north-mini:free"
        )

        if primary_key and primary_model:
            self._providers.append({
                "name": provider_id,
                "provider": provider_id,
                "api_key": primary_key,
                "base_url": LLM_PROVIDER_BASE_URLS[provider_id],
                "model": primary_model,
            })

        if not self._providers:
            logger.warning(
                "No LLM provider configured. LLM workflow analysis will fail. "
                "Set PROCESSIQ_LLM_PRIMARY_API_KEY in .env."
            )

    def _is_retryable(self, exception: Exception) -> bool:
        """Determine if an exception is retryable (transient/recoverable)."""
        # Connection errors
        if isinstance(exception, (requests.ConnectionError, requests.Timeout)):
            return True

        # HTTP errors with retryable status codes
        if isinstance(exception, requests.HTTPError):
            response = getattr(exception, "response", None)
            if response is not None:
                status = response.status_code

                # 429 = rate limit, 5xx = server errors
                if status == 429 or 500 <= status < 600:
                    return True

            return True  # treat HTTPError as retryable by default

        # Any other recoverable exception
        return True

    def _call_single_provider(self, provider: dict, messages: list) -> str:
        """
        Call a single LLM provider with retry logic.
        Returns the raw response text.
        Raises the last exception if all retries fail.
        """
        api_key = provider["api_key"]
        base_url = provider["base_url"]
        model = provider["model"]
        provider_name = provider["name"]
        provider_id = provider["provider"]

        # Never log the API key — only the provider name and model
        logger.info(
            f"[LLM] Selected API: {provider_name} | Model: {model}"
        )

        headers = {
            "Content-Type": "application/json",
        }
        if provider_id == "anthropic":
            url = f"{base_url}/v1/messages"
            headers.update({
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            })
            system_prompt = "\n\n".join(
                message["content"]
                for message in messages
                if message["role"] == "system"
            )
            payload = {
                "model": model,
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [
                    message for message in messages
                    if message["role"] != "system"
                ],
            }
        elif provider_id == "gemini":
            url = (
                f"{base_url}/models/{quote(model, safe='')}:generateContent"
            )
            headers["x-goog-api-key"] = api_key
            system_prompt = "\n\n".join(
                message["content"]
                for message in messages
                if message["role"] == "system"
            )
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [
                    {
                        "role": "model" if message["role"] == "assistant" else "user",
                        "parts": [{"text": message["content"]}],
                    }
                    for message in messages
                    if message["role"] != "system"
                ],
                "generationConfig": {"maxOutputTokens": 8192},
            }
        else:
            url = f"{base_url}/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
            payload = {"model": model, "messages": messages}

        last_error = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                logger.info(
                    f"[LLM] {provider_name} attempt "
                    f"{attempt}/{self._max_attempts}"
                )

                response = requests.post(
                    url=url,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_sec,
                )

                response.raise_for_status()
                data = response.json()

                if provider_id == "anthropic":
                    raw = "".join(
                        block.get("text", "")
                        for block in data.get("content", [])
                        if block.get("type") == "text"
                    )
                elif provider_id == "gemini":
                    candidates = data.get("candidates", [])
                    parts = (
                        candidates[0].get("content", {}).get("parts", [])
                        if candidates else []
                    )
                    raw = "".join(
                        part.get("text", "")
                        for part in parts
                        if isinstance(part, dict)
                    )
                else:
                    if "choices" not in data:
                        raise RuntimeError(
                            f"LLM API error: {data.get('error', data)}"
                        )
                    raw = data["choices"][0]["message"]["content"]

                if not raw:
                    raise RuntimeError("LLM API returned no text content.")

                logger.info(
                    f"[LLM] {provider_name} succeeded on attempt "
                    f"{attempt} | Model: {model}"
                )

                return raw

            except Exception as e:
                last_error = e

                if (
                    self._is_retryable(e)
                    and attempt < self._max_attempts
                ):
                    backoff = (
                        self._delay_sec
                        * (self._backoff_multiplier ** (attempt - 1))
                    )

                    logger.warning(
                        f"[LLM] {provider_name} attempt {attempt} "
                        f"failed: {type(e).__name__}: {e}"
                    )

                    logger.info(
                        f"[LLM] Retrying in {backoff:.1f}s..."
                    )

                    time.sleep(backoff)

                else:
                    logger.error(
                        f"[LLM] {provider_name} failed after "
                        f"{attempt} attempts: {type(e).__name__}: {e}"
                    )
                    break

        raise last_error

    def call(self, system_prompt: str, user_message: str) -> str:
        """
        Call the selected LLM provider with the configured retry behavior.

        Retries the selected provider according to the configured retry count.

        Returns the raw response text on success.
        Raises RuntimeError if the provider fails (caller should handle gracefully).
        """
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            },
        ]

        if not self._providers:
            raise RuntimeError(
                "No LLM providers configured — cannot make LLM call"
            )

        provider = self._providers[0]
        provider_name = provider["name"]
        model = provider["model"]
        try:
            result = self._call_single_provider(provider, messages)
        except Exception as e:
            logger.error(
                f"[LLM] {provider_name} failed after all retries: {e}"
            )
            logger.error(
                f"[LLM] Final failure for selected provider {provider_name}: {e}"
            )
            raise RuntimeError(
                f"All LLM providers failed. Last error: {e}"
            )

        logger.info(
            f"[LLM] Final success: {provider_name} | Model: {model}"
        )
        return result


# Singleton LLM client (application default credentials, from .env) —
# initialized once on module load. Used for every job unless a user has
# selected "Use My Own API Key" in Settings -> LLM Configuration, in
# which case build_llm_client() below builds a separate, request-scoped
# client with that user's own credentials instead.
_llm_client = LLMClient(config)


def build_llm_client(user_id: int = None) -> "LLMClient":
    """
    Returns the LLMClient to use for a given user/customer.

    - No user_id, or the user has never configured this / has selected
      "Default Application API Key": returns the shared singleton
      `_llm_client`, built from the application's .env credentials.
    - The user has selected "Use My Own API Key": builds and returns a
      NEW LLMClient scoped to just this call, using that user's own
      (decrypted) credentials. Never mutates os.environ or the shared
      singleton, so one customer's key can never leak into another
      customer's request — see database.get_llm_settings()/save_llm_settings().

    Any failure to read the user's settings (DB down, decryption failure,
    etc.) safely falls back to the application default client rather than
    raising — a Settings-page/DB hiccup must never take down report
    generation for users who never opted into a custom key.
    """
    if user_id is None:
        return _llm_client

    try:
        import database
        # local import: job_manager.py must stay importable standalone/in tests
        # without a DB configured
        settings = database.get_llm_settings(user_id)

    except Exception as e:
        logger.error(
            f"build_llm_client({user_id}): failed to load LLM settings, "
            f"using application default: {e}"
        )
        return _llm_client

    if not settings or not settings.get("use_custom_key"):
        return _llm_client

    overrides = {
        "provider": settings.get("provider", "openrouter"),
        "model": settings.get("model", ""),
        "primary_api_key": settings.get("primary_api_key", ""),
    }

    if not overrides["primary_api_key"]:
        # Custom mode selected but nothing actually stored (e.g. encryption
        # unavailable at save time) — fall back rather than making a
        # provider-less LLMClient that can only fail.
        logger.warning(
            f"build_llm_client({user_id}): custom mode selected but "
            f"no usable key found, using application default"
        )
        return _llm_client

    logger.info(
        f"[LLM] Using custom API key configuration for user_id={user_id}"
    )

    return LLMClient(
        config,
        key_overrides=overrides
    )


# Backward compatibility: keep these module-level variables for any
# code that still references them directly.
OPENROUTER_API_KEY = get_application_llm_api_key()

LLM_MODEL = config.get(
    "llm",
    {}
).get(
    "model",
    "cohere/north-mini:free"
)

if not OPENROUTER_API_KEY:
    logger.warning(
        "PROCESSIQ_LLM_PRIMARY_API_KEY is not set (nor are legacy OpenRouter "
        "key variables or config.yaml). LLM workflow analysis will fail."
    )

# ==================================================
# MASTER PROMPT
# ==================================================

MASTER_PROMPT = """
You are a workflow analyst. Your job is to match audio narration with video actions
to create a unified workflow description of a tutorial.

CORE TASK

For each step in the tutorial:
1. Understand what the AUDIO narrator is explaining
2. Understand what the VIDEO shows the user doing
3. Determine if both describe the SAME workflow step
4. If YES: Create a COMBINED UNDERSTANDING
5. If NO: Flag for MANUAL VALIDATION

═════════════════════════════════════════════════════════════════════════
MATCHING LOGIC (WORKFLOW-BASED - NO SCORING)
═════════════════════════════════════════════════════════════════════════

A CORRECT MATCH means:
- Audio intent = Video action (same workflow step)
- Wording CAN be different
- Workflow meaning MUST be identical

MATCHING EXAMPLES

Example 1:
Audio:     "Tap the profile icon."
Video:     "User clicks account avatar in top-right corner."
Match?     YES
Reason:    Both describe opening the profile menu (same workflow step)
Combined:  "User opens Google account menu using the profile icon."

Example 2:
Audio:     "Scroll down until you find Language settings."
Video:     "User scrolls through settings page."
Match?     YES
Reason:    Both describe scrolling to find language option (same workflow step)
Combined:  "User scrolls through settings page to locate Language option."

Example 3:
Audio:     "Select the Personal Info option."
Video:     "User taps Personal Info tab."
Match?     YES
Reason:    Both describe accessing Personal Info (same workflow step)
Combined:  "User opens Personal Info section from account settings."

═════════════════════════════════════════════════════════════════════════
MANUAL VALIDATION TRIGGERS (WHEN TO FLAG)
═════════════════════════════════════════════════════════════════════════

Flag for MANUAL VALIDATION if ANY of these apply:

CASE 1: Different Actions
Audio:  "Tap Language option."
Video:  "User opens Security settings."
Reason: Different workflow steps - cannot combine

CASE 2: Promotional Audio (NOT part of workflow)
Audio:  "Subscribe to my channel for more videos."
Video:  "User changes account language."
Reason: Audio is promotional, not a workflow instruction - IGNORE THIS AUDIO

CASE 3: Ambiguous Video
Audio:  "Tap Add Language button."
Video:  "A popup appears but no clear action visible."
Reason: Cannot confirm if the action actually occurred on screen

CASE 4: Missing Visual Evidence
Audio:  "Save your changes."
Video:  "User scrolls around but doesn't tap Save button."
Reason: Expected action not visible in video

CASE 5: Timing Mismatch
Audio:  "Open Personal Information."
Video:  "User is already editing language preferences."
Reason: Audio timing doesn't match video - workflow steps misaligned

CASE 6: Decorative UI Elements
Audio:  [Relevant instruction]
Video:  "Subscribe button animation plays" OR "Bell icon appears" OR "Logo animation"
Reason: Video shows UI element, not user action - ignore video, use audio only
        OR flag if unclear

CONTENT TO IGNORE (Not Part of Workflow)

DO NOT create steps for:

Promotional messages:
- "Subscribe to the channel"
- "Like and share this video"
- "Hit the notification bell"

Greetings:
- "Welcome back everyone"
- "Hi there, thanks for watching"

Outro statements:
- "Thanks for watching"
- "Don't forget to like"
- "See you next time"

Filler speech:
- "Okay..."
- "Now..."
- "Let's continue..."
- "So..."

Decorative UI animations:
- Subscribe button animations
- Bell icon animations
- Logo animations
- Watermarks
- Intro graphics

If these appear in video but do NOT correspond to workflow actions:
→ IGNORE them
→ Do NOT create a workflow step

═════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT — STRICT JSON (PRIMARY)
═════════════════════════════════════════════════════════════════════════

Output a single valid JSON object — no markdown, no code fences, no commentary.

Exact schema:

{
  "process_description": "One sentence (max 12 words) describing what process this tutorial demonstrates.",
  "process_overview": "2-4 sentence paragraph, written only AFTER you have analyzed every step in section_a, summarizing the complete process end-to-end: what it accomplishes, roughly how many steps it takes, and the overall path from the first step to the last. Must be generated fresh from the actual detected steps every time — never generic or boilerplate text.",
  "section_a": [
    {
      "step": 1,
      "time_range": "00:00 - 00:05",
      "description": "Opening Google Account",
      "actions": "User taps the profile icon to open the Google account menu.",
      "screenshot": "frame_0000.jpg"
    }
  ],
  "section_b": [
    {
      "number": 1,
      "time_range": "00:45 - 00:50",
      "audio_understanding": "Narrator says to save changes.",
      "video_understanding": "User scrolls but does not tap Save.",
      "reason_for_manual_review": "Missing visual evidence of save action.",
      "screenshot": "frame_0015.jpg"
    }
  ]
}

FIELD RULES:
- "step" / "number": integer, sequential starting from 1
- "time_range": string in "HH:MM - HH:MM" or "MM:SS - MM:SS" format
- "description": 3-6 words, short title of the step
- "actions": one concise sentence (combined audio + video)
- "audio_understanding": one sentence of what narrator says
- "video_understanding": one sentence of what video shows
- "reason_for_manual_review": one sentence, reference the case (Case 1–6)
- "screenshot": EXACT filename from the VIDEO JSON (e.g. "frame_0004.jpg") — NEVER invented
- "process_overview": derive this ONLY from the steps you actually produced in
  section_a for THIS run — never copy an overview from a previous run, never
  use a generic template sentence like "This process automates X". Reference
  the real number of steps and the real start/end actions.
- If section_b has no items, return "section_b": []
- Output ONLY the JSON object — nothing before or after it

═════════════════════════════════════════════════════════════════════════
SCREENSHOT PATH SELECTION RULES (CRITICAL — READ CAREFULLY)
═════════════════════════════════════════════════════════════════════════

HOW TO PICK THE CORRECT SCREENSHOT FOR EACH STEP:

RULE 1 — PICK THE FRAME WHERE THE ACTION IS COMPLETED, NOT WHERE IT STARTS.

  WRONG: Picking the frame where the user is about to click a button
  RIGHT: Picking the frame where the button has already been clicked and the result is visible

  Example:
  Step: "User clicks the Blank button to open a new form"
  WRONG frame: frame where cursor is hovering over the Blank button
  RIGHT frame: frame where the new blank form is already open on screen

RULE 2 — THE SCREENSHOT MUST SHOW THE OUTCOME OF THE ACTION.

  The result of the action must be visible in the chosen frame.
  If the action is "User types the form title", pick the frame where the typed title is visible.
  If the action is "User clicks Send", pick the frame where the Send dialog is open.
  If the action is "User submits the quiz", pick the frame where the submission confirmation appears.

RULE 3 — FOR SECTION B (MANUAL VALIDATION), PICK THE FRAME THAT BEST SHOWS THE CONFLICT.

  Pick the frame where the mismatch between audio and video is most clearly visible.
  This should be the frame where the ambiguity or conflict is easiest for a human reviewer to spot.

RULE 4 — USE EXACT FILENAMES FROM THE VIDEO JSON.

  Only use frame filenames that actually exist in the VIDEO JSON data provided.
  Do NOT guess or invent frame filenames.
  Match the timestamp of the completed action to the closest available frame in the JSON.

RULE 5 — NEVER PICK THE FIRST FRAME OF A STEP AS DEFAULT.

  Do not default to picking the earliest frame in the time range.
  Always scan through all frames in the time range and pick the one showing completion.

SCREENSHOT SELECTION EXAMPLE:

  Step: "User clicks the Answer key option and selects the correct answer"
  Time Range: 00:28 - 00:33
  Available frames in this range: frame_0028.jpg, frame_0030.jpg, frame_0032.jpg

  frame_0028.jpg → User is clicking Answer key (action starting)
  frame_0030.jpg → Answer key panel is open (action in progress)
  frame_0032.jpg → Correct answer is selected and highlighted (action COMPLETED)

  CORRECT CHOICE: frame_0032.jpg  ← outcome is visible here

═════════════════════════════════════════════════════════════════════════
DECISION TREE (HOW TO ANALYZE)
═════════════════════════════════════════════════════════════════════════

For EACH audio segment + video frame pair:

Step 1: Extract Audio Meaning
- What is the narrator instructing the user to do?
- Ignore if promotional/filler/outro

Step 2: Extract Video Meaning
- What action is the user actually performing?
- Ignore if decorative UI (animations, logos, bells, etc.)

Step 3: Compare Meanings
- Do they describe the SAME workflow step?

  YES (Same step) -> COMBINE THEM
  - Fill description and actions fields in section_a
  - For screenshot: find the frame where the action result is visible (COMPLETED state)

  NO (Different steps) -> MANUAL VALIDATION
  - Fill section_b object with reason:
    - Different actions (Case 1)?
    - Promotional audio (Case 2)?
    - Ambiguous video (Case 3)?
    - Missing evidence (Case 4)?
    - Timing mismatch (Case 5)?
  - For screenshot: pick frame where conflict is most visible

  UNCLEAR -> MANUAL VALIDATION
  - Send for human review in section_b

═════════════════════════════════════════════════════════════════════════
CRITICAL RULES
═════════════════════════════════════════════════════════════════════════

DO THIS:
- Match workflow MEANING, not exact wording
- Ignore promotional/greeting/outro content
- Combine audio + video into ONE unified actions description
- For screenshot: ALWAYS pick the frame where the action is COMPLETED and result is visible
- Flag any ambiguity to section_b
- Keep descriptions concise (1 sentence in actions field)
- Output ONLY the JSON object — nothing else


IF AUDIO IS EMPTY OR MISSING (no separate audio file uploaded AND no embedded audio track in the video):
- Do not generate steps from audio
- Use ONLY the video JSON as source
- Keep "process_description" as a plain short title of the workflow — do NOT
  add any "Note:" prefix or disclaimer yourself; the system adds the
  video-only disclaimer separately as its own line in the document
- "process_overview" must also be phrased purely in terms of what is visible
  on screen — describe the sequence of visual steps only
- Generate sequential steps in section_a from visual events only
- Do not assume any spoken instructions or dialogue
- If visual information is insufficient, describe only what is visibly observable
- NEVER reference speech, conversations, sounds, transcripts, narration, or audio events anywhere in section_a, process_description, or process_overview — describe only what is visible on screen
- section_b must be empty []

DO NOT DO THIS:
- Calculate any scores (similarity, confidence, percentage)
- Use embeddings or algorithms
- Invent actions not shown in either audio or video
- Force matches between unrelated steps
- Include promotional content as workflow steps
- Skip Manual Validation for ambiguous cases
- Add commentary, preamble, or closing text outside the JSON
- Use markdown formatting, code fences, or tables
- Pick the first or earliest frame of a time range by default
- Pick a frame that shows the action starting instead of completing
- Invent screenshot filenames — ONLY use exact filenames from the VIDEO JSON

═════════════════════════════════════════════════════════════════════════
FINAL INSTRUCTION
═════════════════════════════════════════════════════════════════════════

Analyze the audio and video JSONs provided.

Output ONLY a single valid JSON object with two keys:
1. "section_a": list of verified workflow steps
2. "section_b": list of steps requiring manual review (empty list if none)

For every screenshot field: select the frame where the action is COMPLETED and the outcome is clearly visible on screen — never the starting frame. Use ONLY exact filenames from the VIDEO JSON.

No commentary. No markdown. No code fences. No explanation.
Just the single clean JSON object.
"""


# ==================================================
# JOB NAMING
# ==================================================

def make_job_name(video_path: str) -> str:
    stem = Path(video_path).stem
    name = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return name or f"job_{uuid.uuid4().hex[:6]}"


def make_output_paths(job_name: str) -> dict:
    AUDIO_JSON_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_JSON_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    return {
        "audio_json": AUDIO_JSON_DIR / f"{job_name}_audio.json",
        "video_json": VIDEO_JSON_DIR / f"{job_name}_video.json",
        "section_a_clean": REPORT_DIR / f"{job_name}_workflow_steps_clean.docx",
        "section_b": REPORT_DIR / f"{job_name}_workflow_validation.docx",
    }


# ==================================================
# OUTPUT SAVERS
# ==================================================

def save_audio_result(job_name: str, audio_response: dict) -> Path:
    paths = make_output_paths(job_name)
    out = paths["audio_json"]

    payload = {
        "metadata": {
            "job_name": job_name,
            "service": "audio",
            "saved_at": datetime.now().isoformat(),
            "status": audio_response.get("status"),
            "request_id": audio_response.get("request_id"),
            "segments_count": audio_response.get("segments_count", 0),
            "latency_sec": audio_response.get("latency_sec"),
        },
        "result": audio_response,
        "segments": audio_response.get("segments", []),
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info(f"Audio JSON saved: {out}")
    return out


def save_video_result(job_name: str, video_response: dict) -> Path:
    paths = make_output_paths(job_name)
    out = paths["video_json"]

    inner = video_response.get("result", {})
    meta = inner.get("metadata", {})

    payload = {
        "metadata": {
            "job_name": job_name,
            "service": "video",
            "saved_at": datetime.now().isoformat(),
            "status": video_response.get("status"),
            "job_id": video_response.get("id"),
            "unique_actions": meta.get("unique_actions", 0),
            "errors": meta.get("errors", 0),
            "latency_sec": video_response.get("latency_sec"),
        },
        "result": video_response,
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info(f"Video JSON saved: {out}")
    return out


# ==================================================
# LLM WORKFLOW ANALYSIS
# ==================================================

def _build_user_message(audio_data: dict, video_data: dict) -> str:
    import copy

    # Strip base64 images before sending to LLM — text only
    video_data_clean = copy.deepcopy(video_data)

    for record in (
        video_data_clean.get("result", {})
        .get("result", {})
        .get("frame_records", [])
    ):
        record.pop("anchor_image_b64", None)

    # Check if audio is empty
    segments = audio_data.get("segments", [])

    if not segments:
        audio_note = (
            "NOTE: Audio segments are EMPTY. No audio was detected in this "
            "video. Generate all steps from video JSON only. Still set "
            "'process_description' to a short, genuine title (max 12 words) "
            "describing the process shown in the VIDEO — do NOT put any note "
            "about missing/empty audio into process_description; that note is "
            "added separately by the application. Do not assume any spoken "
            "instructions. section_b should be empty []."
        )
    else:
        audio_note = ""

    return f"""Analyze the following audio and video data and generate the workflow report as a strict JSON object matching the schema in the system prompt.
{audio_note}

AUDIO JSON:
{json.dumps(audio_data, indent=2)}

VIDEO JSON:
{json.dumps(video_data_clean, indent=2)}
"""


def _parse_json_response(raw: str) -> dict:
    """
    Try to parse LLM response as strict JSON.
    Strips markdown code fences if present.
    Returns parsed dict with 'section_a' and 'section_b' keys.
    Raises ValueError if parsing fails.
    """
    clean = raw.strip()

    # Strip markdown code fences
    if clean.startswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(
            lines[1:] if lines[0].startswith("```") else lines
        )

    clean = clean.rstrip("`").strip()

    # Find first { and last }
    s = clean.find("{")
    e = clean.rfind("}") + 1

    if s != -1 and e > s:
        clean = clean[s:e]

    data = json.loads(clean)

    if "section_a" not in data or "section_b" not in data:
        raise ValueError(
            "JSON missing section_a or section_b keys"
        )

    return data


def _run_llm_analysis(
    audio_data: dict,
    video_data: dict,
    user_id: int = None
) -> tuple:
    """
    Call LLM with full retry + fallback chain via LLMClient.
    Returns (section_a_rows, section_b_rows, process_description, process_overview).
    """
    user_message = _build_user_message(audio_data, video_data)

    # FIX: the LLM call is now wrapped in its own try/except. Previously,
    # when no provider was configured at all, LLMClient.call() raised
    # RuntimeError HERE, before any parsing or fallback logic ran —
    # and that exception escaped this function entirely, landing in the
    # outer try/except in run_workflow_analysis(), which just returned
    # empty rows and never touched _build_fallback_rows_from_video().
    # That's why the docx table was completely empty instead of showing
    # the one detected action.
    try:
        raw = build_llm_client(user_id).call(
            MASTER_PROMPT,
            user_message
        )

    except Exception as e:
        logger.warning(
            f"LLM call failed entirely ({e}) — building Section A directly "
            f"from the video service's detected actions"
        )

        a_rows = _build_fallback_rows_from_video(video_data)

        # Return the real error message (not empty strings) so the caller
        # can show WHY the LLM path failed instead of a generic message.
        return (
            a_rows,
            [],
            "",
            f"__LLM_ERROR__:{e}"
        )

    # ── Try JSON path first ──────────────────────────────────
    try:
        parsed = _parse_json_response(raw)

        section_a = parsed.get("section_a", [])
        section_b = parsed.get("section_b", [])
        process_description = parsed.get("process_description", "")
        process_overview = parsed.get("process_overview", "")

        logger.info(
            f"LLM response parsed as JSON | "
            f"section_a={len(section_a)} | "
            f"section_b={len(section_b)} | "
            f"desc={process_description}"
        )

        a_rows = []

        for item in section_a:
            a_rows.append({
                "Step": str(item.get("step", "")),
                "Description": item.get("description", ""),
                "Actions": item.get("actions", ""),
                "Screenshot": item.get("screenshot", ""),
            })

        b_rows = []

        for item in section_b:
            b_rows.append({
                "#": str(item.get("number", "")),
                "Time Range": item.get("time_range", ""),
                "Audio Understanding": item.get(
                    "audio_understanding",
                    ""
                ),
                "Video Understanding": item.get(
                    "video_understanding",
                    ""
                ),
                "Reason for Manual Review": item.get(
                    "reason_for_manual_review",
                    ""
                ),
                "Screenshot": item.get("screenshot", ""),
            })

        # NEW: even if the LLM returned valid JSON, if it decided there
        # were zero steps, still fall back to the video service's own
        # detections rather than shipping an empty table.
        if not a_rows:
            logger.warning(
                "LLM JSON parsed but section_a was empty — building "
                "Section A directly from the video service's detected actions"
            )

            a_rows = _build_fallback_rows_from_video(video_data)

        return (
            a_rows,
            b_rows,
            process_description,
            process_overview
        )

    except (ValueError, json.JSONDecodeError, KeyError) as e:
        json_parse_error = e

        logger.warning(
            f"JSON parse failed ({e}) — falling back to markdown parser"
        )

        logger.debug(
            f"Raw LLM response that failed JSON parsing:\n{raw}"
        )

    # ── Fallback: markdown parser ────────────────────────────
    logger.info("Using markdown fallback parser")

    a_rows, b_rows = _parse_markdown_tables(raw)

    if not a_rows:
        logger.warning(
            "Markdown fallback parser also produced no rows — building "
            "Section A directly from the video service's detected actions"
        )

        a_rows = _build_fallback_rows_from_video(video_data)

    # Same as the "LLM call failed entirely" branch above: surface the real
    # reason the JSON schema wasn't honored, instead of returning a silent
    # empty string that the caller can't explain to the user.
    return (
        a_rows,
        b_rows,
        "",
        f"__LLM_ERROR__:LLM response was not valid JSON ({json_parse_error})"
    )


def _build_fallback_rows_from_video(video_data: dict) -> list:
    """
    Last-resort Section A rows built directly from the Video service's own
    detected actions (frame_records / consolidated_timeline), used only
    when the LLM response could not be parsed as JSON *or* as the legacy
    markdown table format. Guarantees the generated document always
    reflects what was actually observed in the video instead of shipping
    with an empty steps table.
    """
    inner = video_data.get("result", {}).get("result", {})
    frame_records = inner.get("frame_records", [])

    # Keep only the non-duplicate actions (skip frames the video service
    # itself flagged as semantically identical to a previous one), in
    # their original chronological order.
    kept = [
        r
        for r in frame_records
        if not r.get("is_duplicate") and r.get("final_action")
    ]

    rows = []

    for idx, rec in enumerate(kept, start=1):
        action = rec.get("final_action", "").strip()

        rows.append({
            "Step": str(idx),
            "Description": action[:60],
            "Actions": action,
            "Screenshot": rec.get("anchor_frame_file", ""),
        })

    return rows


# ==================================================
# MARKDOWN PARSER — extract section A and B rows
# ==================================================

def _parse_markdown_tables(markdown_text: str) -> tuple:
    """
    Parse markdown into two lists of row dicts:
      section_a_rows — all columns from Section A
      section_b_rows — all columns from Section B
    """
    section_a_rows = []
    section_b_rows = []

    lines = markdown_text.splitlines()
    current = None
    headers = []

    for line in lines:
        line = line.strip()

        if "SECTION A" in line:
            current = "A"
            headers = []
            continue

        if "SECTION B" in line:
            current = "B"
            headers = []
            continue

        if not line.startswith("|"):
            continue

        if line.startswith("|---") or line.startswith("|:--"):
            continue

        cells = [
            c.strip()
            for c in line.strip("|").split("|")
        ]

        if not headers:
            headers = cells
            continue

        row = {}

        for idx, h in enumerate(headers):
            row[h] = cells[idx] if idx < len(cells) else ""

        if current == "A":
            section_a_rows.append(row)

        elif current == "B":
            section_b_rows.append(row)

    return section_a_rows, section_b_rows


# ==================================================
# FRAME IMAGE FETCHER — via HTTP from Video Service
# ==================================================

VIDEO_SERVICE_URL = config.get(
    "services",
    {}
).get(
    "video",
    {}
).get(
    "url",
    "http://localhost:8022"
)


def _fetch_frame_image(
    screenshot_path: str,
    video_data: dict
) -> bytes:
    """
    Given a screenshot filename from LLM output,
    fetch the actual frame image from Video service via HTTP.
    Returns image bytes or empty bytes if not found.
    Includes lightweight retry for transient network failures.
    """
    if not screenshot_path:
        return b""

    fname = Path(screenshot_path).name

    job_id = (
        video_data.get("metadata", {}).get("job_id")
        or video_data.get("result", {}).get("id", "")
    )

    if not job_id:
        logger.warning(
            f"No job_id in video_data — cannot fetch frame {fname}"
        )
        return b""

    url = f"{VIDEO_SERVICE_URL}/frames/{job_id}/{fname}"

    max_attempts = 2

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(
                url,
                timeout=10
            )

            if resp.status_code == 200:
                return resp.content

            else:
                logger.warning(
                    f"Frame fetch failed {url}: {resp.status_code}"
                )

                if attempt < max_attempts:
                    time.sleep(1)

        except Exception as e:
            logger.warning(
                f"Frame fetch error {url} "
                f"(attempt {attempt}): {e}"
            )

            if attempt < max_attempts:
                time.sleep(1)

    return b""


def _add_image_to_cell(
    cell,
    img_bytes: bytes
) -> None:
    """Embed image bytes into a docx table cell."""
    import io

    try:
        img_stream = io.BytesIO(img_bytes)
        p = cell.paragraphs[0]
        run = p.add_run()
        run.add_picture(
            img_stream,
            width=Inches(2.5)
        )

    except Exception as e:
        cell.paragraphs[0].add_run(
            f"[Image error: {e}]"
        )


def _build_process_overview(
    rows: list,
    process_title: str,
    video_data: dict = None,
    error_detail: str = ""
) -> str:
    """
    Used ONLY when the LLM did not return a "process_overview" field for
    this run (LLM call failed entirely, no provider configured, or the raw
    response failed both the JSON and markdown parsers).

    This is intentionally NOT a synthesized summary — it does not fabricate
    "This process consists of N steps: it begins with X and concludes with
    Y" style sentences that imitate AI-written analysis using string
    templates. That kind of templated text is what was making the document
    look "hardcoded" even when the LLM had actually failed. Instead this
    states plainly that the overview could not be generated, and — when
    available — includes the real reason the LLM call failed, so the cause
    (missing/invalid API key, network issue, model unavailable, etc.) is
    visible directly in the document instead of only in the logs.
    """
    reason_line = (
        f" Reason: {error_detail}"
        if error_detail
        else ""
    )

    if rows:
        return (
            "The AI service did not return a process overview for this run, "
            "so this section could not be generated. The steps identified "
            "below are shown as detected. Please verify the LLM configuration "
            "(e.g. PRIMARY_LLM_API_KEY / OPENROUTER_API_KEY) and re-generate "
            f"this document to get a full, AI-written overview.{reason_line}"
        )

    return (
        "The AI service did not return a process overview or process steps "
        "for this run. Please verify the LLM configuration (e.g. "
        f"PRIMARY_LLM_API_KEY / OPENROUTER_API_KEY) and re-generate this "
        f"document.{reason_line}"
    )


def _write_section_a_clean_docx(
    rows: list,
    output_file: Path,
    video_data: dict = None,
    process_description: str = "",
    no_audio: bool = False,
    process_overview: str = ""
) -> None:
    """Section A — BRD format docx with centered title, process overview, and steps table."""
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    process_title = process_description or "Workflow Process"

    # ── Title: Business Requirements Document (centered, large) ──
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    title_run = title_para.add_run(
        "Business Requirements Document"
    )
    title_run.bold = True
    title_run.font.size = Pt(20)

    # ── "For" line (centered) ──
    for_para = doc.add_paragraph()
    for_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for_para.add_run("For")

    # ── Process title (centered, from LLM description) ──
    proc_para = doc.add_paragraph()
    proc_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    proc_run = proc_para.add_run(process_title)
    proc_run.bold = True
    proc_run.font.size = Pt(14)

    # ── Note: shown only when no audio was detected ──
    if no_audio:
        note_para = doc.add_paragraph()

        note_run = note_para.add_run(
            "Note: The output is based only on video frames."
        )
        note_run.bold = True
        note_run.italic = True
        note_run.font.size = Pt(11)
        note_run.font.color.rgb = RGBColor(
            0xC0,
            0x00,
            0x00
        )

    doc.add_paragraph()  # spacer

    # ── 1. Process Overview ──
    doc.add_heading(
        "1.  Process Overview:",
        level=2
    )

    overview_para = doc.add_paragraph()

    overview_para.add_run(
        process_overview
        or _build_process_overview(
            rows,
            process_title,
            video_data
        )
    )

    doc.add_paragraph()  # spacer

    # ── 2. Process Steps ──
    doc.add_heading(
        "2.  Process Steps:",
        level=2
    )

    headers = [
        "Step",
        "Description",
        "Actions",
        "Screenshot"
    ]

    table = doc.add_table(
        rows=1,
        cols=len(headers)
    )
    table.style = "Table Grid"

    hdr_cells = table.rows[0].cells

    for idx, h in enumerate(headers):
        hdr_cells[idx].text = h

    for row in rows:
        cells = table.add_row().cells

        cells[0].text = row.get("Step", "")
        cells[1].text = row.get("Description", "")
        cells[2].text = row.get("Actions", "")

        # Fetch actual image from Video service
        img_bytes = _fetch_frame_image(
            row.get("Screenshot", ""),
            video_data or {}
        )

        if img_bytes:
            cells[3].paragraphs[0].clear()

            _add_image_to_cell(
                cells[3],
                img_bytes
            )

        else:
            cells[3].text = row.get(
                "Screenshot Path",
                ""
            )

    doc.save(str(output_file))


def _write_section_b_docx(
    rows: list,
    output_file: Path,
    video_data: dict = None
) -> None:
    """Section B — manual validation docx with embedded images."""
    doc = Document()

    doc.add_heading(
        "Manual Validation Required",
        level=2
    )

    headers = [
        "#",
        "Time Range",
        "Audio Understanding",
        "Video Understanding",
        "Reason for Manual Review",
        "Screenshot"
    ]

    table = doc.add_table(
        rows=1,
        cols=len(headers)
    )
    table.style = "Table Grid"

    hdr_cells = table.rows[0].cells

    for idx, h in enumerate(headers):
        hdr_cells[idx].text = h

    for row in rows:
        cells = table.add_row().cells

        cells[0].text = row.get("#", "")
        cells[1].text = row.get("Time Range", "")
        cells[2].text = row.get(
            "Audio Understanding",
            ""
        )
        cells[3].text = row.get(
            "Video Understanding",
            ""
        )
        cells[4].text = row.get(
            "Reason for Manual Review",
            ""
        )

        # Fetch actual image from Video service
        img_bytes = _fetch_frame_image(
            row.get("Screenshot", ""),
            video_data or {}
        )

        if img_bytes:
            cells[5].paragraphs[0].clear()

            _add_image_to_cell(
                cells[5],
                img_bytes
            )

        else:
            cells[5].text = row.get(
                "Screenshot Path",
                ""
            )

    doc.save(str(output_file))


# ==================================================
# EMAIL SENDER
# ==================================================

EMAIL_CFG = config.get("email", {})


def send_email_with_attachments(
    recipient_email: str,
    username: str,
    attachment_paths: list,
    job_name: str = "",
) -> None:
    """
    Send output docx files as email attachments to the user.
    Reads SMTP settings from config.yaml under the 'email' key.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email import encoders

    smtp_host = EMAIL_CFG.get(
        "smtp_host",
        "smtp.gmail.com"
    )

    smtp_port = EMAIL_CFG.get(
        "smtp_port",
        587
    )

    sender_email = EMAIL_CFG.get(
        "sender_email",
        ""
    )

    sender_pass = (
        os.environ.get("EMAIL_SENDER_PASSWORD")
        or EMAIL_CFG.get("sender_password", "")
    )

    sender_name = EMAIL_CFG.get(
        "sender_name",
        "OneNextGen Automation Pvt Ltd"
    )

    if not sender_email or not sender_pass:
        logger.warning(
            "Email credentials not configured — skipping email send."
        )
        return

    process_title = (
        job_name.replace("_", " ").title()
        if job_name
        else "Workflow Process"
    )

    msg = MIMEMultipart()

    msg["From"] = (
        f"{sender_name} <{sender_email}>"
    )

    msg["To"] = recipient_email

    msg["Subject"] = (
        "Your Business Requirements Document is Ready"
    )

    body = f"""Hi {username},

Your process flow document has been created successfully with all the steps defined in the video.

Please find the attached Business Requirements Document:

Process Description: {process_title}

Document Contents:
  1. Workflow Steps (Section A) — verified workflow steps with screenshots
  2. Manual Validation (Section B) — steps requiring manual review

Best regards,
{sender_name}
"""

    msg.attach(
        MIMEText(body, "plain")
    )

    for path in attachment_paths:
        p = Path(path)

        if not p.exists():
            logger.warning(
                f"Attachment not found, skipping: {path}"
            )
            continue

        with open(p, "rb") as f:
            part = MIMEBase(
                "application",
                "octet-stream"
            )
            part.set_payload(f.read())

        encoders.encode_base64(part)

        part.add_header(
            "Content-Disposition",
            f"attachment; filename={p.name}",
        )

        msg.attach(part)

    try:
        with smtplib.SMTP(
            smtp_host,
            smtp_port
        ) as server:
            server.starttls()

            server.login(
                sender_email,
                sender_pass
            )

            server.sendmail(
                sender_email,
                recipient_email,
                msg.as_string()
            )

        logger.info(
            f"Email sent to {recipient_email}"
        )

    except Exception as e:
        logger.error(
            f"Failed to send email to {recipient_email}: {e}"
        )


# ==================================================
# MAIN WORKFLOW ANALYSIS
# ==================================================

class PipelineCancelled(Exception):
    """Raised by run_workflow_analysis when the job was cancelled mid-way."""


def run_workflow_analysis(
    job_name: str,
    audio_json_path: Path,
    video_json_path: Path,
    username: str = "",
    recipient_email: str = "",
    case3: bool = None,
    user_id: int = None,
    cancel_check=None,
) -> Path:
    """
    Load audio + video JSONs → call the LLM with both complete JSONs so
    it can reason about the full temporal/contextual relationship between
    narration and visuals in a single pass → save:
      1. <job>_workflow_steps_clean.docx    (Section A, BRD format, images embedded)
      2. <job>_workflow_validation.docx     (Section B, images embedded)
    If recipient_email is provided, sends both files as email attachments.
    Returns path to the Section A clean docx.

    `user_id`: whose Settings -> LLM Configuration to use for this call —
    see build_llm_client(). None (the default) always uses the
    application's .env credentials, same as before this parameter existed.

    The LLM call uses the full retry + fallback chain (LLMClient). If all
    providers fail, the function returns empty section rows gracefully —
    the pipeline never crashes.

    `case3`, when True, means no separate audio was uploaded AND no embedded
    audio track was found (the user confirmed "Continue" using video frames
    only). When True, section_b is always forced empty — there's no audio to
    cross-validate against. If not provided, it's inferred from whether the
    audio JSON has any segments (kept as a fallback for direct callers).

    `cancel_check` (optional): callable returning True once the job was
    cancelled. It is polled between the LLM call, the document writing and the
    email step; when it fires, any documents already written are removed, no
    email is sent, and PipelineCancelled is raised. With the default (None)
    behaviour is unchanged.
    """
    paths = make_output_paths(job_name)

    def _cancelled() -> bool:
        return bool(cancel_check and cancel_check())

    def _discard_outputs() -> None:
        for key in ("section_a_clean", "section_b"):
            try:
                Path(paths[key]).unlink(missing_ok=True)
            except Exception:
                pass

    if _cancelled():
        raise PipelineCancelled(job_name)

    logger.info(
        f"[{job_name}] Starting LLM workflow analysis..."
    )

    with open(audio_json_path, encoding="utf-8") as f:
        audio_data = json.load(f)

    with open(video_json_path, encoding="utf-8") as f:
        video_data = json.load(f)

    if case3 is None:
        case3 = not audio_data.get("segments", [])

    if _cancelled():
        raise PipelineCancelled(job_name)

    # ── Single unified LLM call over the COMPLETE audio JSON and COMPLETE
    # video JSON together, with full retry + fallback via LLMClient.
    try:
        (
            section_a_rows,
            section_b_rows,
            process_description,
            process_overview
        ) = _run_llm_analysis(
            audio_data,
            video_data,
            user_id
        )

    except Exception as e:
        logger.error(
            f"[{job_name}] LLM analysis failed after all retries "
            f"and fallbacks: {e}"
        )

        section_a_rows = []
        section_b_rows = []
        process_description = ""
        process_overview = f"__LLM_ERROR__:{e}"

    logger.info(
        f"[{job_name}] LLM analysis complete | "
        f"section_a={len(section_a_rows)} | "
        f"section_b={len(section_b_rows)}"
    )

    if case3:
        # Case 3 always means: section_b is empty (nothing to cross-validate
        # against audio), regardless of what the LLM returned.
        section_b_rows = []

        logger.info(
            f"[{job_name}] Case 3 — output generated using video frames only"
        )

    # Fallback process description to job_name if LLM didn't provide one
    if not process_description:
        process_description = (
            job_name.replace("_", " ").title()
        )

    # If the LLM call itself threw an exception, _run_llm_analysis tags the
    # overview slot with the real error so we can show WHY it failed instead
    # of a generic message — surface that here, then clear the tag so the
    # rest of the pipeline (and the docx) sees a normal readable sentence.
    llm_error_detail = ""

    if process_overview.startswith("__LLM_ERROR__:"):
        llm_error_detail = process_overview[
            len("__LLM_ERROR__:")
        ]

        process_overview = ""

    # Fallback process overview if the LLM didn't provide one (parse failure,
    # markdown-fallback path, or the model simply omitted the field) — build
    # a short sentence from the actual step descriptions rather than leaving
    # the overview blank.
    if not process_overview:
        process_overview = _build_process_overview(
            section_a_rows,
            process_description,
            video_data,
            llm_error_detail
        )

    if _cancelled():
        raise PipelineCancelled(job_name)

    # 1 & 2. Section A + Section B docx — independent outputs once the rows
    # above are computed, so write them concurrently.
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(
            _write_section_a_clean_docx,
            section_a_rows,
            paths["section_a_clean"],
            video_data,
            process_description,
            case3,
            process_overview,
        )

        fut_b = pool.submit(
            _write_section_b_docx,
            section_b_rows,
            paths["section_b"],
            video_data,
        )

        fut_a.result()
        fut_b.result()

    logger.info(
        f"[{job_name}] Section A clean docx saved: "
        f"{paths['section_a_clean']}"
    )

    logger.info(
        f"[{job_name}] Section B validation docx saved: "
        f"{paths['section_b']}"
    )

    if _cancelled():
        _discard_outputs()
        raise PipelineCancelled(job_name)

    # 3. Send email if recipient provided
    if recipient_email and EMAIL_CFG.get("enabled", False):
        try:
            send_email_with_attachments(
                recipient_email=recipient_email,
                username=username or job_name,
                attachment_paths=[
                    paths["section_a_clean"],
                    paths["section_b"]
                ],
                job_name=process_description,
            )

        except Exception as e:
            logger.error(
                f"[{job_name}] Email sending failed: {e}"
            )

    return paths["section_a_clean"]