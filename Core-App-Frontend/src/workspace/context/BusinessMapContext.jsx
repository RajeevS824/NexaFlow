import React, { createContext, useContext, useState, useRef, useEffect } from "react";
import { pollJobStatus } from "../config/businessMapApi";
import { saveJobState, loadJobState, clearJobState } from "../utils/businessMapJobPersistence";
import { getStepIndexForProgress, getFinalBarState } from "../Tool-Applications/Business-Process-Mapper/Pages/constants/pipeline";

const BusinessMapContext = createContext(null);

const SUBMIT_STEPS   = ["Upload", "Validate", "Complete"];
const GENERATE_STEPS = ["Uploaded", "Validated", "Process", "Generate", "Complete"];

/**
 * Holds all BusinessMap page state above the <Routes> tree so that:
 *   1. Navigating away and back does NOT reset upload/progress/result
 *      state (in-memory, same as before).
 *   2. A full page refresh / browser restart ALSO does not lose an
 *      active job — state is mirrored to localStorage, and on mount this
 *      provider checks for an active job and resumes polling the backend
 *      automatically instead of asking the user to re-upload.
 *
 * Only the manual Reset button (or a job reaching a terminal state)
 * clears the persisted state.
 */
export function BusinessMapProvider({ children }) {
  const [videoFile, setVideoFile]     = useState(null);
  const [audioFile, setAudioFile]     = useState(null);
  const [progress, setProgress]       = useState(0);
  const [activeSteps, setActiveSteps] = useState(SUBMIT_STEPS);
  const [stepIndex, setStepIndex]     = useState(-1);
  const [statusText, setStatusText]   = useState(
    "Upload a video file to get started. Audio is optional."
  );
  const [statusType, setStatusType]   = useState("idle");
  const [isRunning, setIsRunning]     = useState(false);
  const [result, setResult]           = useState(null);

  // Job identity — the only things we actually need to resume polling
  // after a refresh, since the File objects themselves can't survive one.
  const [jobId, setJobId]     = useState(null);
  const [jobName, setJobName] = useState(null);

  // Display-only copies of the uploaded file names, kept around so the
  // "currently processing" UI can still show what's being processed even
  // after a refresh drops the real File object.
  const [uploadedVideoName, setUploadedVideoName] = useState(null);
  const [uploadedAudioName, setUploadedAudioName] = useState(null);

  // "No Audio Detected" dialog state — lives here (not component-local)
  // so a refresh while the dialog is open restores it instead of losing
  // the paused job entirely.
  const [showNoAudioDialog, setShowNoAudioDialog] = useState(false);
  const [noAudioMessage, setNoAudioMessage]       = useState("");
  const [pendingJobId, setPendingJobId]           = useState(null);
  const [pendingJobName, setPendingJobName]       = useState(null);

  // User details (optional)
  const [showUserDetails, setShowUserDetails]   = useState(false);
  const [username, setUsername]                 = useState("");
  const [email, setEmail]                       = useState("");
  const [userDetailsError, setUserDetailsError] = useState("");

  // Refs also need to persist (interval id, file input refs)
  const intervalRef   = useRef(null);
  const videoInputRef = useRef(null);
  const audioInputRef = useRef(null);

  // Guards against React 18/19 StrictMode's double effect invocation in
  // dev, which would otherwise fire the resume logic (and its network
  // calls) twice for a single real page load.
  const hasResumedRef = useRef(false);
  // Jobs the user already cancelled on this page. A polling loop that is still
  // running for such a job must not overwrite the cancelled state when its
  // (late) CANCELLED result arrives.
  const cancelledJobsRef = useRef(new Set());

  /* ── Persist active-job state to localStorage on every relevant change ── */
  useEffect(() => {
    const hasActiveJob = Boolean(jobId) && (isRunning || showNoAudioDialog);

    if (hasActiveJob) {
      saveJobState({
        jobId,
        jobName,
        videoFileName: uploadedVideoName,
        audioFileName: uploadedAudioName,
        progress,
        stepIndex,
        statusText,
        statusType,
        isRunning,
        awaitingAudioConfirmation: showNoAudioDialog,
        noAudioMessage,
        pendingJobId,
        pendingJobName,
      });
    } else {
      // No active job (idle, or a job just reached a terminal state) —
      // nothing left worth restoring after a refresh.
      clearJobState();
    }
  }, [
    jobId, jobName, uploadedVideoName, uploadedAudioName,
    progress, stepIndex, statusText, statusType, isRunning,
    showNoAudioDialog, noAudioMessage, pendingJobId, pendingJobName,
  ]);

  /* ── On first mount, check for a job that was active before a refresh
       and resume it automatically — restore the UI, then keep polling
       the backend until it reaches a terminal state. ── */
  useEffect(() => {
    if (hasResumedRef.current) return;
    hasResumedRef.current = true;

    const saved = loadJobState();
    if (!saved || !saved.jobId) return;

    // NOTE: this batch of setState calls is intentional and runs exactly
    // once per real page load (guarded by hasResumedRef above) — it is
    // restoring state after a refresh, not synchronizing on every render,
    // so the usual "avoid setState in an effect" concern doesn't apply
    // here. React 18+ batches these into a single re-render regardless.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setJobId(saved.jobId);
    setJobName(saved.jobName || null);
    setUploadedVideoName(saved.videoFileName || null);
    setUploadedAudioName(saved.audioFileName || null);

    if (saved.awaitingAudioConfirmation) {
      // Job was paused waiting on the "No Audio Detected" popup when the
      // page was left — restore that exact dialog state. The dialog's
      // own Cancel/Continue handlers will re-validate against the
      // backend when the user acts on it.
      setPendingJobId(saved.pendingJobId || saved.jobId);
      setPendingJobName(saved.pendingJobName || saved.jobName);
      setNoAudioMessage(saved.noAudioMessage || "");
      setShowNoAudioDialog(true);
      setStatusText("Restoring your previous session…");
      setStatusType("idle");
      return;
    }

    if (saved.isRunning) {
      setIsRunning(true);
      setProgress(saved.progress ?? 0);
      setStepIndex(saved.stepIndex ?? 0);
      setStatusText("Restoring session — resuming processing…");
      setStatusType("idle");

      pollJobStatus(saved.jobId, (pct) => {
        const clipped = Math.min(pct, 95);
        setProgress((prev) => Math.max(prev, clipped));
        setStepIndex((prev) => Math.max(prev, getStepIndexForProgress(clipped)));
      })
        .then((data) => {
          // Cancelled by the user meanwhile: keep the cancelled state they see.
          if (cancelledJobsRef.current.has(saved.jobId)) return;
          if (data.status === "NEEDS_AUDIO_CONFIRMATION") {
            setIsRunning(false);
            setProgress(0);
            setStepIndex(-1);
            setPendingJobId(data.job_id || saved.jobId);
            setPendingJobName(data.job_name || saved.jobName);
            setNoAudioMessage(
              data.message ||
                "No audio track was found in the uploaded video, and no separate audio file was uploaded. Would you like to continue generating the output using only the video frames (video JSON)?"
            );
            setShowNoAudioDialog(true);
            return;
          }

          // Only a finished job fills the bar; cancelled / failed ones reset it.
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
        })
        .catch((err) => {
          if (cancelledJobsRef.current.has(saved.jobId)) return;
          setIsRunning(false);
          setProgress(0);
          setStepIndex(-1);
          setStatusText(
            err?.error || err?.detail ||
              "Couldn't reconnect to the previous job — the server may have restarted. Please upload again."
          );
          setStatusType("error");
        });
    }
  }, []);

  const value = {
    SUBMIT_STEPS, GENERATE_STEPS,
    videoFile, setVideoFile,
    audioFile, setAudioFile,
    progress, setProgress,
    activeSteps, setActiveSteps,
    stepIndex, setStepIndex,
    statusText, setStatusText,
    statusType, setStatusType,
    isRunning, setIsRunning,
    result, setResult,
    jobId, setJobId,
    jobName, setJobName,
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
  };

  return (
    <BusinessMapContext.Provider value={value}>
      {children}
    </BusinessMapContext.Provider>
  );
}

export function useBusinessMap() {
  const ctx = useContext(BusinessMapContext);
  if (!ctx) throw new Error("useBusinessMap must be inside BusinessMapProvider");
  return ctx;
}
