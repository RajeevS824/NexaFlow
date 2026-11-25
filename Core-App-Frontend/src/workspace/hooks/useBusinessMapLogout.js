/**
 * workspace/hooks/useBusinessMapLogout.js
 * ------------------------------------------------------------
 * The ONE logout implementation for Business Map. The header/profile
 * Logout and the sidebar Logout both call this hook, so the sequence
 * lives in a single place:
 *
 *   1. ask the Business Map backend to cancel the current user's active
 *      jobs (the backend identifies the user from the Bearer token,
 *      stops the audio / video / orchestrator work, sets each job to
 *      Cancelled - or Failed on a technical error - and persists it),
 *   2. immediately reflect that outcome in the frontend state (the job
 *      leaves the active/processing state and shows Cancelled), and forget
 *      the locally stored "active job" so nothing is resumed,
 *   3. clear the auth session (AuthContext.logout),
 *   4. redirect to the dashboard sign-in page.
 *
 * Steps 2-4 run even if step 1 fails or times out, so logout always
 * completes; the failure is logged and the backend records the job's
 * final status itself.
 * ------------------------------------------------------------
 */
import { useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { useBusinessMap } from "../context/BusinessMapContext";
import { cancelActiveJobs } from "../config/businessMapApi";
import { clearJobState } from "../utils/businessMapJobPersistence";
import { DASHBOARD_LOGIN_PATH } from "../../config/dashboardRoutes.js";

const CANCEL_TIMEOUT_MS = 35000;

export function useBusinessMapLogout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const busyRef = useRef(false);
  const {
    jobId, pendingJobId,
    setIsRunning, setProgress, setStepIndex, setStatusText, setStatusType,
    setResult, setShowNoAudioDialog, setPendingJobId, setPendingJobName,
    cancelledJobsRef,
  } = useBusinessMap();

  return useCallback(async () => {
    if (busyRef.current) return; // ignore double clicks
    busyRef.current = true;
    try {
      let timer;
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("cancellation timed out")), CANCEL_TIMEOUT_MS);
      });
      try {
        const report = await Promise.race([cancelActiveJobs(), timeout]);
        if (report?.failed?.length) {
          console.warn("Some Business Map jobs could not be cancelled cleanly:", report.failed);
        }

        // Reflect the backend's answer for the job shown on screen right now:
        // it leaves the active-processing state and shows its final status.
        const mine = [jobId, pendingJobId].filter(Boolean);
        if (mine.length) {
          const wasCancelled = mine.some((id) => report?.cancelled?.includes(id));
          const failedEntry = report?.failed?.find((f) => mine.includes(f.job_id));
          if (wasCancelled) {
            setResult({ status: "CANCELLED", message: "Processing was cancelled because you logged out." });
            setStatusText("Processing was cancelled.");
            setStatusType("error");
          } else if (failedEntry) {
            setResult({ status: "FAILED", message: "Processing could not be cancelled cleanly." });
            setStatusText("Processing could not be cancelled cleanly.");
            setStatusType("error");
          }
          if (wasCancelled || failedEntry) {
            // A polling loop still running for this job must not overwrite this state.
            mine.forEach((id) => cancelledJobsRef.current.add(id));
            setIsRunning(false);
            setProgress(0);
            setStepIndex(-1);
            setShowNoAudioDialog(false);
            setPendingJobId(null);
            setPendingJobName(null);
          }
        }
      } finally {
        clearTimeout(timer);
      }
    } catch (err) {
      console.warn("Business Map job cancellation failed before logout:", err);
    } finally {
      clearJobState();
      await logout();
      navigate(DASHBOARD_LOGIN_PATH, { replace: true });
      busyRef.current = false;
    }
  }, [
    logout, navigate, jobId, pendingJobId,
    setIsRunning, setProgress, setStepIndex, setStatusText, setStatusType,
    setResult, setShowNoAudioDialog, setPendingJobId, setPendingJobName,
  ]);
}
