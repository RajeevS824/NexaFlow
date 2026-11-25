import React, { useRef, useState } from "react";
import { runPipeline } from "../../../../config/businessMapApi";

/**
 * VideoUpload
 * Drop-zone + file picker. Calls runPipeline() and passes the result
 * up to the parent via onResult(result).
 *
 * Props:
 *   onResult  (result) => void   – called when pipeline finishes
 *   onError   (msg)    => void   – called on failure
 */
export default function VideoUpload({ onResult, onError }) {
  const inputRef = useRef(null);
  const [status, setStatus] = useState("idle"); // idle | uploading | processing
  const [progress, setProgress] = useState(0);
  const [dragging, setDragging] = useState(false);

  async function process(file) {
    if (!file || !file.type.startsWith("video/")) {
      onError?.("Please select a valid video file.");
      return;
    }

    if (file.size > 500 * 1024 * 1024) {
      onError?.("File exceeds the 500 MB limit.");
      return;
    }

    setStatus("uploading");
    setProgress(0);

    try {
      // Once upload reaches 100 % the server starts processing
      const result = await runPipeline(file, (pct) => {
        setProgress(pct);
        if (pct === 100) setStatus("processing");
      });
      setStatus("idle");
      onResult?.(result);
    } catch (err) {
      setStatus("idle");
      onError?.(err?.error || err?.detail || "Pipeline failed. Check backend logs.");
    }
  }

  function onFileChange(e) {
    const file = e.target.files?.[0];
    if (file) process(file);
    // reset input so the same file can be re-selected
    e.target.value = "";
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) process(file);
  }

  const isActive = status !== "idle";

  return (
    <div
      className={`video-upload-zone ${dragging ? "drag-over" : ""} ${isActive ? "active" : ""}`}
      onClick={() => !isActive && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      style={{
        border: "2px dashed #863bff",
        borderRadius: 12,
        padding: "2rem",
        textAlign: "center",
        cursor: isActive ? "default" : "pointer",
        background: dragging ? "#f3eaff" : "#fafafa",
        transition: "background 0.2s",
        userSelect: "none",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        style={{ display: "none" }}
        onChange={onFileChange}
      />

      {status === "idle" && (
        <>
          <div style={{ fontSize: 40 }}>🎬</div>
          <p style={{ margin: "0.5rem 0 0", fontWeight: 600, color: "#1c2538" }}>
            Drop a video here or click to select
          </p>
          <p style={{ margin: "0.25rem 0 0", fontSize: 13, color: "#6b7a99" }}>
            MP4 / MOV / AVI · max 500 MB
          </p>
        </>
      )}

      {status === "uploading" && (
        <>
          <p style={{ fontWeight: 600, color: "#863bff" }}>
            Uploading… {progress}%
          </p>
          <div style={{
            height: 6, background: "#e8e0ff", borderRadius: 3, overflow: "hidden", marginTop: 8,
          }}>
            <div style={{
              width: `${progress}%`, height: "100%",
              background: "#863bff", transition: "width 0.3s",
            }} />
          </div>
        </>
      )}

      {status === "processing" && (
        <>
          <div style={{ fontSize: 32 }}>⚙️</div>
          <p style={{ fontWeight: 600, color: "#863bff" }}>
            Processing audio & video…
          </p>
          <p style={{ fontSize: 13, color: "#6b7a99" }}>
            This can take a minute. Hang tight.
          </p>
        </>
      )}
    </div>
  );
}
