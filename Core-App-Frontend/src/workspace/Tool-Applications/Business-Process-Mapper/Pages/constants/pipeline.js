// // ─────────────────────────────────────────────
// // pipeline.js – shared constants for the BusinessMap processing pipeline.
// // Pulled out into their own module so both BusinessMap.jsx (normal
// // generate flow) and BusinessMapContext.jsx (resume-after-refresh flow)
// // can use the exact same step/phase mapping without importing from each
// // other (which would create a circular import, since BusinessMap.jsx
// // already imports from the context).
// // ─────────────────────────────────────────────

// /** The 5 canonical pipeline steps shown in the progress bar. */
// export const PIPELINE_STEPS = ["Upload", "Validate", "Process", "Generate", "Complete"];

// /** Maps backend phase names → step index. */
// export const PHASE_TO_STEP = {
//   validating: 1,   // "Validate"
//   processing: 2,   // "Process"
//   audio_done: 2,   // still "Process" — audio finished, video may still be running
//   video_done: 2,   // still "Process" — video finished, about to generate
//   generating: 3,   // "Generate"
//   saving:     3,   // still "Generate"
// };


















// ─────────────────────────────────────────────
// pipeline.js – shared constants for the BusinessMap processing pipeline.
// Pulled out into their own module so both BusinessMap.jsx (normal
// generate flow) and BusinessMapContext.jsx (resume-after-refresh flow)
// can use the exact same step/phase mapping without importing from each
// other (which would create a circular import, since BusinessMap.jsx
// already imports from the context).
// ─────────────────────────────────────────────

/** The 5 canonical pipeline steps shown in the progress bar. */
export const PIPELINE_STEPS = ["Upload", "Validate", "Process", "Generate", "Complete"];

/** Maps backend phase names → step index. */
export const PHASE_TO_STEP = {
  validating: 1,   // "Validate"
  processing: 2,   // "Process"
  audio_done: 2,   // still "Process" — audio finished, video may still be running
  video_done: 2,   // still "Process" — video finished, about to generate
  generating: 3,   // "Generate"
  saving:     3,   // still "Generate"
};

/**
 * Progress-percentage thresholds that drive step highlighting.
 * Listed highest-first so getStepIndexForProgress can just walk down
 * the list and return on the first match.
 */
const PROGRESS_STEP_THRESHOLDS = [
  { minPct: 70, step: 3 }, // "Generate"
  { minPct: 50, step: 2 }, // "Process"
  { minPct: 32, step: 1 }, // "Validate"
];

/**
 * Given a progress percentage, returns the step index that should be
 * highlighted at that point. Below 32% this returns 0 ("Upload"),
 * i.e. no later step is highlighted yet.
 */
export function getStepIndexForProgress(pct) {
  for (const { minPct, step } of PROGRESS_STEP_THRESHOLDS) {
    if (pct >= minPct) return step;
  }
  return 0;
}

/**
 * Bar state to show once a job has reached a final status. Only a finished
 * job (SUCCESS, or PARTIAL = finished with some errors) fills the bar and marks
 * every step done. A cancelled or failed job leaves the bar empty and no step
 * marked, so it never looks like it completed.
 */
export function getFinalBarState(status) {
  return status === "SUCCESS" || status === "PARTIAL"
    ? { progress: 100, stepIndex: 4 }
    : { progress: 0, stepIndex: -1 };
}
