

import React, { useState, useEffect } from "react";
import Modal from "./components/Modal";
import { uploadAndStart, confirmAudio, pollJobStatus, cancelJob, cancelJobBeacon, getDownloadUrl, getUploadConfig } from "../../../config/businessMapApi";
import { useBusinessMap } from "../../../context/BusinessMapContext";
import { clearJobState } from "../../../utils/businessMapJobPersistence";
import { PIPELINE_STEPS, getStepIndexForProgress, getFinalBarState } from "./constants/pipeline";
import "../Styles/BusinessMap.css";
import "../Styles/bm-common.css";

// NOTE: Audio-track detection is performed exclusively by the backend
// (via ffprobe) after the user clicks Generate and the file finishes
// uploading. There is intentionally no client-side audio detection here —
// browser APIs like `mozHasAudio`/`webkitAudioDecodedByteCount` are
// unreliable across browsers and previously caused false "No Audio
// Detected" popups even for videos that had a valid audio track.
// ─────────────────────────────────────────────────────────────

function BusinessMap() {
  const {
    videoFile, setVideoFile,
    audioFile, setAudioFile,
    progress, setProgress,
    stepIndex, setStepIndex,
    statusText, setStatusText,
    statusType, setStatusType,
    isRunning, setIsRunning,
    result, setResult,
    jobId, setJobId,
    setJobName,
    uploadedVideoName, setUploadedVideoName,
    uploadedAudioName, setUploadedAudioName,
    showNoAudioDialog, setShowNoAudioDialog,
    noAudioMessage, setNoAudioMessage,
    pendingJobId, setPendingJobId,
    pendingJobName, setPendingJobName,
    showUserDetails, setShowUserDetails,
    username, setUsername,
    email, setEmail,
    userDetailsError, setUserDetailsError,
    intervalRef, videoInputRef, audioInputRef,
    cancelledJobsRef,
  } = useBusinessMap();

  // While a job is running, keep the highlighted step in line with the bar.
  // (During upload the bar is set up to 40% but the step used to stay on
  // "Upload", so the bar and the labels disagreed.)
  useEffect(() => {
    if (!isRunning) return;
    const s = getStepIndexForProgress(progress);
    setStepIndex((prev) => (prev >= s ? prev : s));
  }, [isRunning, progress, setStepIndex]);

  /* local-only modal state — the "Ready to Generate?" confirmation is a
     pre-flight step, nothing has been sent to the backend yet, so there's
     nothing meaningful to restore after a refresh here. */
  const [showConfirm, setShowConfirm] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  /* Max upload sizes, configured on the Settings page — fetched once on
     mount so file-select validation below can enforce the real current
     limits (not a hardcoded 500MB) before ever sending anything to the
     backend. Falls back to 500MB if the fetch fails, matching the
     backend's own fallback so both sides stay consistent. */
  const [maxUploadMb, setMaxUploadMb] = useState(500);
  const [maxAudioUploadMb, setMaxAudioUploadMb] = useState(500);
  const [fileSizeError, setFileSizeError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getUploadConfig();
        if (!cancelled) {
          if (data?.max_upload_size_mb) setMaxUploadMb(data.max_upload_size_mb);
          if (data?.max_audio_upload_size_mb) setMaxAudioUploadMb(data.max_audio_upload_size_mb);
        }
      } catch {
        // Keep the 500MB defaults — the backend still enforces the real
        // limits regardless, so this is just a best-effort UX nicety.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  /* ── Warn before leaving while a job is actively processing (refresh,
       tab close, or browser navigation). This only shows the browser's
       native "leave site?" prompt — it must NOT cancel anything here,
       because `beforeunload` fires the instant the user *attempts* to
       leave, even if they then click "Cancel" on that native prompt and
       stay on the page. Cancelling at this point would kill jobs for
       people who never actually left. ── */
  useEffect(() => {
    function handleBeforeUnload(e) {
      if (!isRunning) return;
      e.preventDefault();
      e.returnValue =
        "A video is currently being processed. Leaving this page will cancel the processing.";
      return e.returnValue;
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isRunning]);

  /* ── Actually cancel the backend job when the page is genuinely being
       discarded (reload committed, tab closed, or navigated away) — as
       opposed to `beforeunload`, `pagehide` only fires once the browser
       has committed to unloading, so a user who dismisses the native
       "leave site?" prompt and stays never triggers this. This is what
       makes a reload end up as CANCELLED rather than continuing to
       completion in the background and showing up as Completed. ── */
  useEffect(() => {
    function handlePageHide() {
      if (!isRunning || !jobId) return;
      cancelJobBeacon(jobId);
    }
    window.addEventListener("pagehide", handlePageHide);
    return () => window.removeEventListener("pagehide", handlePageHide);
  }, [isRunning, jobId]);

  /* ── Status helper ── */
  function updateStatus(video, audio) {
    if (video) {
      setStatusText(
        audio
          ? "Both files ready. Click Generate to proceed."
          : "Video ready. You can also add an audio file (optional)."
      );
      setStatusType("ready");
    } else {
      setStatusText("Upload a video file to get started. Audio is optional.");
      setStatusType("idle");
    }
  }

  /* ── File handlers ── */
  function handleVideoChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!validateFileSize(file, maxUploadMb)) { e.target.value = ""; return; }
    setVideoFile(file);
    setResult(null);
    updateStatus(file, audioFile);
  }

  function handleAudioChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!validateFileSize(file, maxAudioUploadMb)) { e.target.value = ""; return; }
    setAudioFile(file);
    updateStatus(videoFile, file);
  }

  /* Blocks selection entirely (never sent to the backend) if the file
     exceeds the configured limit — backend still enforces this too as
     the real source of truth, this is just so the user finds out
     immediately instead of waiting on an upload that will be rejected. */
  function validateFileSize(file, limitMb) {
    const maxBytes = limitMb * 1024 * 1024;
    if (file.size > maxBytes) {
      const fileMb = (file.size / (1024 * 1024)).toFixed(1);
      setFileSizeError(
        `File upload failed. The selected file is ${fileMb} MB. Your maximum allowed upload ` +
        `size is ${limitMb} MB. Please upload a file that is ${limitMb} MB or smaller.`
      );
      return false;
    }
    setFileSizeError("");
    return true;
  }

  /* ── User details ── */
  function handleUserDetailsToggle(e) {
    const checked = e.target.checked;
    setShowUserDetails(checked);
    if (!checked) { setUsername(""); setEmail(""); setUserDetailsError(""); }
  }

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const USERNAME_CHAR_RE = /^[A-Za-z_ ]+$/;
  const REPEATED_CHAR_RE = /(.)\1{2,}/i;

  function validateUserDetails() {
    if (!showUserDetails) { setUserDetailsError(""); return { valid: true }; }
    let message = "";
    const raw = username, trimmed = username.trim();
    if (!raw || !trimmed) message = "Username is required.";
    else if (raw !== trimmed) message = "Username cannot start or end with a space.";
    else if (/\s{2,}/.test(raw)) message = "Username cannot contain multiple consecutive spaces.";
    else if (trimmed.length < 3 || trimmed.length > 20) message = "Username must be between 3 and 20 characters.";
    else if (/\d/.test(trimmed)) message = "Username cannot contain numbers.";
    else if (!USERNAME_CHAR_RE.test(trimmed)) message = "Username can only contain letters, underscores, and single spaces.";
    else if (REPEATED_CHAR_RE.test(trimmed)) message = "Username cannot contain the same character repeated 3+ times.";
    else if (!email.trim() || !EMAIL_RE.test(email.trim())) message = "Please enter a valid email address.";
    setUserDetailsError(message);
    return { valid: !message };
  }

  /* ── Generate button click → validate, then show "Ready to Generate?"
       confirmation. Audio detection happens only on the backend, only
       after the user confirms and the upload completes. ── */
  async function handleGenerateClick() {
    if (isRunning) return; // belt-and-braces guard against duplicate submits
    if (!videoFile) {
      setStatusText("Please upload a video file.");
      setStatusType("error");
      return;
    }
    if (videoFile.size > 500 * 1024 * 1024) {
      setStatusText("File exceeds the 500 MB limit.");
      setStatusType("error");
      return;
    }
    if (!validateUserDetails().valid) {
      setStatusText("Please fix the highlighted field before continuing.");
      setStatusType("error");
      return;
    }

    setShowConfirm(true);
  }

  /* ── OK in confirmation → upload and let the backend decide the
       audio source (this is the only place that decision is made) ── */
  async function handleConfirmOK() {
    if (isRunning) return; // duplicate-submit guard
    setShowConfirm(false);
    if (intervalRef.current) clearInterval(intervalRef.current);

    setIsRunning(true);
    setResult(null);
    setProgress(0);
    setStepIndex(0);
    setStatusText("Uploading…");
    setStatusType("idle");
    setUploadedVideoName(videoFile.name);
    setUploadedAudioName(audioFile ? audioFile.name : null);

    try {
      const started = await uploadAndStart(
        videoFile,
        (pct) => setProgress(Math.min(pct, 40)),
        audioFile,
        showUserDetails ? username : "",
        showUserDetails ? email    : "",
      );

      setJobId(started.job_id);
      setJobName(started.job_name);

      if (started.status === "NEEDS_AUDIO_CONFIRMATION") {
        // Case 3, confirmed by real backend ffprobe inspection: the
        // backend has paused and is waiting for the user's decision.
        // Nothing has been processed yet.
        setIsRunning(false);
        setProgress(0);
        setStepIndex(-1);
        setPendingJobId(started.job_id);
        setPendingJobName(started.job_name);
        setNoAudioMessage(
          started.message ||
            "No audio track was found in the uploaded video, and no separate audio file was uploaded. Would you like to continue generating the output using only the video frames (video JSON)?"
        );
        setShowNoAudioDialog(true);
        return;
      }

      // Case 1 or Case 2: audio source already resolved — continue normally.
      await pollToCompletion(started.job_id);
    } catch (err) {
      setIsRunning(false);
      setProgress(0);
      setStepIndex(-1);
      setStatusText(err?.error || err?.detail || "Pipeline failed. Check backend logs.");
      setStatusType("error");
      clearJobState();
    }
  }

  /* ── Shared polling helper used after a job starts processing,
       whether that's immediately (Case 1/2) or after Continue (Case 3) ── */
  async function pollToCompletion(id) {
    setIsRunning(true);
    setStatusText("Processing…");
    setStatusType("idle");

    try {
      const data = await pollJobStatus(id, (pct) => {
        const clipped = Math.min(pct, 95);
        setProgress((prev) => Math.max(prev, clipped));
        setStepIndex((prev) => Math.max(prev, getStepIndexForProgress(clipped)));
      });

      // The user already cancelled this job (Cancel button / popup): that
      // handler has set the final state, so a late poll result must not
      // overwrite it (it used to put the bar back to 100%).
      if (cancelledJobsRef.current.has(id)) return;

      // Defensive: if the backend is paused awaiting confirmation, show
      // the popup instead of treating it as a failure.
      if (data.status === "NEEDS_AUDIO_CONFIRMATION") {
        setIsRunning(false);
        setProgress(0);
        setStepIndex(-1);
        setPendingJobId(data.job_id || id);
        setPendingJobName(data.job_name);
        setNoAudioMessage(
          data.message ||
            "No audio track was found in the uploaded video, and no separate audio file was uploaded. Would you like to continue generating the output using only the video frames (video JSON)?"
        );
        setShowNoAudioDialog(true);
        return;
      }

      // Only a finished job fills the bar. Cancelled / failed jobs reset it.
      const bar = getFinalBarState(data.status);
      setStepIndex(bar.stepIndex);
      setProgress(bar.progress);
      setIsRunning(false);
      setResult(data);

      if (data.status === "SUCCESS") {
        setStatusText("Output generated successfully!");
        setStatusType("ready");
      } else if (data.status === "PARTIAL") {
        setStatusText("Completed with some errors — see details below.");
        setStatusType("error");
      } else if (data.status === "CANCELLED") {
        setStatusText(data.message || "Processing was cancelled.");
        setStatusType("error");
      } else {
        setStatusText("Pipeline failed.");
        setStatusType("error");
      }
    } catch (err) {
      if (cancelledJobsRef.current.has(id)) return;
      setIsRunning(false);
      setProgress(0);
      setStepIndex(-1);
      setStatusText(err?.error || err?.detail || "Pipeline failed. Check backend logs.");
      setStatusType("error");
      clearJobState();
    }
  }

  /* ── Edit in confirmation → stay on page ── */
  function handleConfirmEdit() {
    setShowConfirm(false);
  }

  /* ── Explicit user-initiated cancellation of an in-progress job.
       This is the real, synchronized way to stop backend processing —
       tells the server (via Job ID) to release resources and mark the
       job Cancelled, then clears local + persisted frontend state. ── */
  async function handleCancelProcessing() {
    if (!jobId || cancelling) return;
    cancelledJobsRef.current.add(jobId);
    setCancelling(true);
    setStatusText("Cancelling…");
    setStatusType("idle");

    try {
      const data = await cancelJob(jobId);
      setResult({
        status: "CANCELLED",
        message: data?.message || "Processing was cancelled by the user.",
      });
      setStatusText(data?.message || "Processing cancelled by the user.");
    } catch (err) {
      setResult({
        status: "CANCELLED",
        message: "Processing was cancelled by the user.",
      });
      setStatusText(err?.error || err?.detail || "Processing cancelled by the user.");
    } finally {
      setIsRunning(false);
      setProgress(0);
      setStepIndex(-1);
      setStatusType("error");
      setCancelling(false);
      clearJobState();
    }
  }

  /* ── Cancel on the "No Audio Detected" popup → tell the backend to
       stop the workflow for this job. No video frames or audio have
       been processed at this point. ── */
  async function handleNoAudioCancel() {
    const id = pendingJobId;
    if (id) cancelledJobsRef.current.add(id);
    setShowNoAudioDialog(false);
    setPendingJobId(null);
    setPendingJobName(null);

    setStatusText("Cancelling…");
    setStatusType("idle");

    try {
      const data = id ? await confirmAudio(id, false) : null;
      setResult({
        status: "CANCELLED",
        message: data?.message || "Processing was cancelled by the user.",
      });
      setStatusText("Processing cancelled by the user.");
      setStatusType("error");
    } catch (err) {
      setResult({
        status: "CANCELLED",
        message: "Processing was cancelled by the user.",
      });
      setStatusText("Processing cancelled by the user.");
      setStatusType("error");
    } finally {
      setIsRunning(false);
      setProgress(0);
      setStepIndex(-1);
      clearJobState();
    }
  }

  /* ── Continue on the "No Audio Detected" popup → tell the backend to
       proceed using only video frames, then resume polling ── */
  async function handleNoAudioContinue() {
    const id = pendingJobId;
    setShowNoAudioDialog(false);
    setPendingJobId(null);
    setPendingJobName(null);

    if (!id) return;

    setIsRunning(true);
    setProgress(40);
    setStepIndex(0);
    setStatusText("Processing using only video frames…");
    setStatusType("idle");

    try {
      await confirmAudio(id, true);
      await pollToCompletion(id);
    } catch (err) {
      setIsRunning(false);
      setProgress(0);
      setStepIndex(-1);
      setStatusText(err?.error || err?.detail || "Pipeline failed. Check backend logs.");
      setStatusType("error");
      clearJobState();
    }
  }

  /* ── Reset ── */
  function handleReset() {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setVideoFile(null); setAudioFile(null);
    setProgress(0); setStepIndex(-1);
    setIsRunning(false); setResult(null);
    setStatusText("Upload a video file to get started. Audio is optional.");
    setStatusType("idle");
    setShowUserDetails(false); setUsername(""); setEmail(""); setUserDetailsError("");
    setShowConfirm(false);
    setShowNoAudioDialog(false);
    setPendingJobId(null);
    setPendingJobName(null);
    setNoAudioMessage("");
    setJobId(null);
    setJobName(null);
    setUploadedVideoName(null);
    setUploadedAudioName(null);
    if (videoInputRef.current) videoInputRef.current.value = "";
    if (audioInputRef.current) audioInputRef.current.value = "";
    clearJobState();
  }

  const displayVideoName = videoFile?.name || uploadedVideoName;
  const displayAudioName = audioFile?.name || uploadedAudioName;

  /* ── Render ── */
  return (
    <>
      {/* ── Confirmation Modal — true modal: locks background scroll/
           interaction and traps keyboard focus while open ── */}
      <Modal open={showConfirm} labelledBy="confirm-title">
        <div className="bm-modal-icon">
          <i className="ti ti-sparkles" aria-hidden="true" />
        </div>
        <h2 className="bm-modal-title" id="confirm-title">Ready to Generate?</h2>
        <p className="bm-modal-body">
          Your files are ready to process. Click <strong>OK</strong> to start the pipeline,
          or <strong>Edit</strong> to go back and make changes.
        </p>
        <div className="bm-modal-file-summary">
          <span className="bm-modal-file-chip">
            <i className="ti ti-video" /> {displayVideoName}
          </span>
          {displayAudioName && (
            <span className="bm-modal-file-chip">
              <i className="ti ti-microphone" /> {displayAudioName}
            </span>
          )}
        </div>
        <div className="bm-modal-actions">
          <button className="bm-modal-btn bm-modal-btn-edit" onClick={handleConfirmEdit} type="button">
            <i className="ti ti-edit" /> Edit
          </button>
          <button className="bm-modal-btn bm-modal-btn-ok" onClick={handleConfirmOK} type="button">
            <i className="ti ti-check" /> OK, Start
          </button>
        </div>
      </Modal>

      {/* ── No Audio Detected Dialog ──
           Driven entirely by the backend's USER_CONFIRMATION_REQUIRED
           response, which is only returned after the backend has
           genuinely inspected the uploaded video file with ffprobe. Also
           a true modal, and restorable after a refresh (state lives in
           BusinessMapContext, not component-local). ── */}
      <Modal open={showNoAudioDialog} labelledBy="no-audio-title">
        <div className="bm-modal-icon">⚠️</div>
        <h2 className="bm-modal-title" id="no-audio-title">No Audio Detected</h2>
        <p className="bm-modal-body">
          {noAudioMessage ||
            "No audio track was found in the uploaded video, and no separate audio file was uploaded. Would you like to continue generating the output using only the video frames (video JSON)?"}
        </p>
        <div className="bm-modal-actions">
          <button
            className="bm-modal-btn bm-modal-btn-edit"
            onClick={handleNoAudioCancel}
            type="button"
          >
            <i className="ti ti-x" /> Cancel
          </button>
          <button
            className="bm-modal-btn bm-modal-btn-ok"
            onClick={handleNoAudioContinue}
            type="button"
          >
            <i className="ti ti-check" /> Continue
          </button>
        </div>
      </Modal>

      <main className="fp-page">
        <div className="fp-container">
          <div className="fp-card">
            <div className="fp-heading-block">
              <p className="fp-heading">Business Processor</p>
              <p className="fp-card-subtitle">
                Upload video and audio files to process and generate business requirement document
              </p>
            </div>

            {/* ── Upload zones ── */}
            <div className="fp-upload-grid">
              {/* Video zone */}
              <div
                className={`fp-upload-zone${videoFile || uploadedVideoName ? " has-file" : ""}`}
                onClick={() => !isRunning && videoInputRef.current?.click()}
                role="button" tabIndex={0} aria-label="Upload video file"
                onKeyDown={(e) => e.key === "Enter" && !isRunning && videoInputRef.current?.click()}
              >
                <i className="ti ti-video fp-zone-icon" aria-hidden="true" />
                <span className="fp-zone-label">Select Video file</span>
                <button className="fp-upload-btn" onClick={(e) => { e.stopPropagation(); videoInputRef.current?.click(); }} type="button" disabled={isRunning}>
                  <i className="ti ti-upload" aria-hidden="true" /> Upload video
                </button>
                <span className="fp-filename">{displayVideoName || "No file selected"}</span>
                <span className="fp-formats">Supported: .mp4, .avi, .mov, .mkv, .webm (max {maxUploadMb}MB)</span>
                <input ref={videoInputRef} type="file" accept="video/*" style={{ display: "none" }} onChange={handleVideoChange} aria-label="Video file input" />
              </div>

              {/* Audio zone */}
              <div
                className={`fp-upload-zone${audioFile || uploadedAudioName ? " has-file" : ""}`}
                onClick={() => !isRunning && audioInputRef.current?.click()}
                role="button" tabIndex={0} aria-label="Upload audio file (optional)"
                onKeyDown={(e) => e.key === "Enter" && !isRunning && audioInputRef.current?.click()}
              >
                <i className="ti ti-microphone fp-zone-icon" aria-hidden="true" />
                <span className="fp-zone-label">
                  Select Audio file <span className="fp-optional-badge">optional</span>
                </span>
                <button className="fp-upload-btn" onClick={(e) => { e.stopPropagation(); audioInputRef.current?.click(); }} type="button" disabled={isRunning}>
                  <i className="ti ti-upload" aria-hidden="true" /> Upload audio
                </button>
                <span className="fp-filename">{displayAudioName || "No file selected"}</span>
                <span className="fp-formats">Supported: .mp3, .wav (max {maxAudioUploadMb}MB)</span>
                <input ref={audioInputRef} type="file" accept="audio/*" style={{ display: "none" }} onChange={handleAudioChange} aria-label="Audio file input (optional)" />
              </div>
            </div>

            {fileSizeError && <p className="fp-field-error">{fileSizeError}</p>}

            {/* ── User details (optional) ── */}
            <div className="fp-user-details">
              <label className={`fp-user-details-toggle${isRunning ? " disabled" : ""}`}>
                <input type="checkbox" className="fp-user-details-checkbox" checked={showUserDetails} onChange={handleUserDetailsToggle} disabled={isRunning} aria-label="Provide user details" />
                Provide user details
              </label>
              {showUserDetails && (
                <div className="fp-user-fields-grid">
                  <div className="fp-field-group">
                    <label htmlFor="bm-username" className="fp-field-label">Username</label>
                    <input id="bm-username" type="text" className="fp-field-input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Enter username" disabled={isRunning} />
                  </div>
                  <div className="fp-field-group">
                    <label htmlFor="bm-email" className="fp-field-label">Email ID</label>
                    <input id="bm-email" type="email" className="fp-field-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" disabled={isRunning} />
                  </div>
                </div>
              )}
              {userDetailsError && <p className="fp-field-error">{userDetailsError}</p>}
            </div>

            {/* ── Progress section — always visible ── */}
            <div className="fp-progress-section">
              <div className="fp-progress-header">
                <span className="fp-progress-title">Processing progress</span>
              </div>

              <div className="fp-progress-track" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100} aria-label="Processing progress">
                <div className="fp-progress-fill" style={{ width: `${progress}%` }} />
              </div>

              {/* Step labels — always visible below the bar */}
              <div className="fp-step-labels-row">
                {PIPELINE_STEPS.map((label, i) => {
                  const isDone   = progress > 0 && i <= stepIndex;
                  const isActive = isRunning && i === stepIndex;
                  return (
                    <span key={label} className={`fp-step-label-text${isDone ? " done" : ""}${isActive ? " active" : ""}`}>
                      {label}
                    </span>
                  );
                })}
              </div>
            </div>

            {/* ── Status bar ── */}
            <div className={`fp-status${statusType === "ready" ? " ready" : statusType === "error" ? " error" : ""}`}>
              <i className={`ti ${statusType === "error" ? "ti-alert-circle" : statusType === "ready" ? "ti-circle-check" : isRunning ? "ti-loader fp-spin" : "ti-info-circle"}`} aria-hidden="true" />
              <span>{isRunning ? (statusText || "Processing video. Please wait…") : statusText}</span>
            </div>

            <hr className="fp-divider" />

            {/* ── Action buttons ── */}
            <div className="fp-actions">
              <button className="fp-btn fp-btn-generate" onClick={handleGenerateClick} disabled={isRunning} type="button">
                <i className="ti ti-sparkles" aria-hidden="true" /> Generate
              </button>
              {isRunning ? (
                <button className="fp-btn fp-btn-danger" onClick={handleCancelProcessing} disabled={cancelling || !jobId} type="button">
                  <i className="ti ti-x" aria-hidden="true" /> {cancelling ? "Cancelling…" : "Cancel Processing"}
                </button>
              ) : (
                <button className="fp-btn fp-btn-danger" onClick={handleReset} disabled={isRunning} type="button">
                  <i className="ti ti-refresh" aria-hidden="true" /> Reset
                </button>
              )}
            </div>

            {/* ── Result cards ── */}
            {/* A cancelled job's message is shown once, in the status bar above. */}
            {result && result.status !== "CANCELLED" && (
              <div className="fp-results">
                <div className="fp-results-grid">
                  <ResultCard label="Workflow Steps" status={result.outputs?.workflow_steps_clean ? "READY" : "—"} path={result.outputs?.workflow_steps_clean} />
                  <ResultCard label="Manual Validation" status={result.outputs?.workflow_validation ? "READY" : "—"} path={result.outputs?.workflow_validation} />
                </div>
                {result.errors?.length > 0 && (
                  <details className="fp-error-details">
                    <summary>{result.errors.length} service error(s)</summary>
                    <ul>{result.errors.map((e, i) => <li key={i}><b>{e.service}</b>: {e.error}</li>)}</ul>
                  </details>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}

/* ── Small result card ── */
function ResultCard({ label, status, path }) {
  const ready    = status === "SUCCESS" || status === "READY" || status === "SUCCESS_NO_VALIDATION";
  const download = getDownloadUrl(path);
  return (
    <div className="fp-result-card">
      <div className="fp-result-label">{label}</div>
      <div className={`fp-result-status${ready ? " ready" : status === "SKIPPED" ? " skipped" : " failed"}`}>{status ?? "—"}</div>
      {ready && download && <a href={download} download className="fp-result-download">Download</a>}
    </div>
  );
}

export default BusinessMap;