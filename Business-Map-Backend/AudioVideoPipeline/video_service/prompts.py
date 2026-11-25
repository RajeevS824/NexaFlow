###############################################################
# VIDEO SERVICE — PROMPTS
# All prompt templates and message builders for Qwen3-VL
###############################################################

# ==================================================
# SUMMARY PROMPT
# ==================================================

SUMMARY_PROMPT_TEMPLATE = """\
You are a video analysis assistant producing a final timeline summary.

RULES:
1. Combine the action descriptions into a coherent chronological timeline.
2. Remove duplicate or near-duplicate descriptions.
3. Preserve only unique, meaningful action transitions, and also with timestamp second.
4. Keep it concise, factual, and temporally accurate.
5. Use present tense. No speculation. No emotions. No filler words.
6. Output ONLY a valid JSON object — no markdown, no explanation.
   Format: {{"timeline": ["action 1", "action 2", ...]}}

Frame-by-frame actions (deduplicated, with timestamps):
{descriptions}

Return ONLY the JSON object.
"""

# ==================================================
# SEMANTIC SIMILARITY PROMPT
# ==================================================

SEMANTIC_PROMPT_TEMPLATE = """\
You are a semantic similarity judge for UI action descriptions.

Compare these two action descriptions:
ACTION A: {action_a}
ACTION B: {action_b}

STEP 1 — UI ELEMENT CHECK (do this first, before scoring):
Extract the target UI element from each action (button name, field name, menu name, etc.).
If ACTION A and ACTION B target DIFFERENT UI elements → score MUST be <= 0.20 and is_duplicate MUST be false.
Different element names = different actions, regardless of how similar the sentence structure is.

STEP 2 — SCORE only if UI elements are the same or no specific element is mentioned:
- 1.0       = identical meaning, same target
- 0.80-0.99 = same action + same target, only minor wording difference    → duplicate
- 0.60-0.79 = related action but not equivalent                           → not duplicate
- 0.00-0.59 = clearly different actions                                   → not duplicate

CRITICAL RULE:
Same action verb (click, type, scroll) with DIFFERENT target = score <= 0.20, is_duplicate false.

Examples:
A: "Clicked the Submit button"      B: "Clicked the View score button" → score 0.10, is_duplicate false  ← different targets
A: "Clicked the Submit button"      B: "Pressed the Submit button"     → score 0.95, is_duplicate true   ← same target
A: "Clicked Login button"           B: "Pressed the Login button"      → score 0.95, is_duplicate true
A: "Scrolled downward"              B: "Scrolled upward"               → score 0.15, is_duplicate false
A: "Typed in search box"            B: "Entered text in search"        → score 0.90, is_duplicate true
A: "Opened settings menu"           B: "Opened profile menu"           → score 0.10, is_duplicate false  ← different targets
A: "Clicked Settings"               B: "Clicked Profile"               → score 0.10, is_duplicate false  ← different targets
A: "no user action"                 B: "no user action"                → score 1.00, is_duplicate true

Return ONLY a valid JSON object, no markdown, no explanation:
{{
  "semantic_score": <float 0.0 to 1.0>,
  "is_duplicate": <true or false>,
  "reason": "<one sentence — mention UI element names if relevant>"
}}
"""

# ==================================================
# TRIPLET PROMPT BUILDER
# ==================================================

def build_triplet_prompt(has_prev: bool, has_next: bool) -> str:
    """Build the per-frame analysis prompt based on available context frames."""

    parts = []
    if has_prev:
        parts.append("IMAGE 1 = PREVIOUS frame (screen state BEFORE current frame)")
    curr_num = 2 if has_prev else 1
    parts.append(f"IMAGE {curr_num} = CURRENT frame (frame to analyze)")
    if has_next:
        next_num = 3 if has_prev else 2
        parts.append(f"IMAGE {next_num} = NEXT frame (screen state AFTER current frame)")

    context = "\n".join(f"- {x}" for x in parts)

    return f"""You are analyzing sequential screen-recording frames.
Frames provided:
{context}

Objective:
Determine ONLY the user action that happened in the CURRENT frame.

Frame usage:
- PREVIOUS frame → understand what existed before
- CURRENT frame → identify exact action
- NEXT frame → confirm what changed after

Reasoning rule:
Compare PREVIOUS → CURRENT → NEXT to infer action,
but produce output ONLY for CURRENT frame.

STRICT RULES:
- Output exactly ONE action.
- Never describe previous frame.
- Never describe next frame.
- Never summarize sequence.
- Never output multiple actions.
- Maximum 20 - 30 words.
- Single line only.
- Be specific when UI element is visible.
- If evidence is unclear, use next frame to validate.
- If no visible interaction occurred, return:
  no user action

Good outputs:
Clicked Login button
Typed in search box
Opened settings menu
Scrolled downward
Selected dropdown option
Closed popup
Dragged slider
no user action

Bad outputs:
User clicked then opened page
The next frame shows success
Screen changed after click
Current frame appears to show

Return ONLY the CURRENT frame action."""


# ==================================================
# MESSAGE BUILDER  (triplet: prev + curr + next)
# ==================================================

def build_messages(
    anchor_idx: int,
    frame_files: list,
    n_frames: int,
) -> tuple:
    """
    Build a single user message with up to 3 frames:
      - PREVIOUS frame (if anchor_idx > 0)
      - CURRENT  frame (always)
      - NEXT     frame (if anchor_idx < n_frames - 1)

    Returns:
      messages    - list ready for run_inference()
      window_idxs - list of frame indices used (for logging)
    """
    has_prev = anchor_idx > 0
    has_next = anchor_idx < n_frames - 1

    window_idxs = []
    content     = []

    if has_prev:
        prev_path = frame_files[anchor_idx - 1]
        content.append({"type": "image", "image": str(prev_path)})
        window_idxs.append(anchor_idx - 1)

    curr_path = frame_files[anchor_idx]
    content.append({"type": "image", "image": str(curr_path)})
    window_idxs.append(anchor_idx)

    if has_next:
        next_path = frame_files[anchor_idx + 1]
        content.append({"type": "image", "image": str(next_path)})
        window_idxs.append(anchor_idx + 1)

    prompt_text = build_triplet_prompt(has_prev, has_next)
    content.append({"type": "text", "text": prompt_text})

    messages = [{"role": "user", "content": content}]
    return messages, window_idxs
