import React, { useState } from "react";
import { FaChevronDown, FaChevronUp } from "react-icons/fa";
import { DocumentationCard } from "../components/DocComponents";
import "../../../Styles/documentation.css";

const FAQS = [
  ["Which files can I upload?", "Video: .mp4, .avi, .mov, .mkv or .webm. Audio (optional): .mp3 or .wav. The maximum size for each is set in Settings → Upload Configuration."],
  ["Do I have to upload audio?", "No. If your video has a usable audio track it is used. If it has none, you can continue with video frames only, or cancel."],
  ["What is the difference between Workflow Steps and Manual Validation?", "Workflow Steps is the clean, step-by-step document. Manual Validation helps you check the narration against what is shown on screen; it is empty when no audio was used."],
  ["How long does processing take?", "It depends on the length of the video and the load on the server. Watch the progress bar and the stage labels; the Dashboard also shows the job as Processing."],
  ["What happens if I reload or close the page during processing?", "The browser warns you first. If you leave anyway, the job is cancelled on the server and shows as Cancelled."],
  ["What happens to my running jobs when I log out?", "Logout first asks the server to cancel your active jobs (only yours), waits for the result, then signs you out. Jobs that already completed stay Completed."],
  ["Why does a job show Cancelled although I did not press Cancel?", "Leaving the page, answering Cancel in the No Audio Detected window and logging out all cancel the job."],
  ["Can I delete a notification?", "Yes. Deleting only removes it from your notification list; the file and the Dashboard numbers are unchanged."],
  ["Where do I change the upload limit?", "Main NexaFlow dashboard → Settings → Business Process Mapper → Upload Configuration."],
  ["Where are the documents saved?", "On the server. Use the Download link on the result cards after the job completes."],
];

export default function FAQ() {
  const [open, setOpen] = useState(0);
  return (
    <div className="bm-doc-page">
      {FAQS.map(([q, a], i) => (
        <DocumentationCard key={q}>
          <button
            type="button"
            onClick={() => setOpen(open === i ? -1 : i)}
            aria-expanded={open === i}
            style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", background: "none", border: "none", cursor: "pointer", font: "inherit", fontWeight: 700, color: "#0F172A", fontSize: 15, textAlign: "left", padding: 0 }}
          >
            <span>{q}</span>
            {open === i ? <FaChevronUp /> : <FaChevronDown />}
          </button>
          {open === i && <p style={{ marginTop: 12 }}>{a}</p>}
        </DocumentationCard>
      ))}
    </div>
  );
}
