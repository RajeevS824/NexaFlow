import React from "react";
import { FaInfoCircle, FaUpload, FaUserEdit, FaPlay, FaMicrophoneSlash, FaBan, FaFileDownload } from "react-icons/fa";
import { DocumentationCard, DocList, DocTable, Figure, InfoPanel, NotePanel, WorkflowCard } from "../components/DocComponents";
import "../../../Styles/documentation.css";

export default function BusinessFlowDocumentation() {
  return (
    <div className="bm-doc-page">
      <DocumentationCard title="Overview" icon={<FaInfoCircle />}>
        <p>
          Business Flow is where you create documents. On the <strong>Business Processor</strong> card you add a
          video of the business process (and optionally a separate audio file), press <strong>Generate</strong>, watch
          the progress bar, and download the results when the job completes.
        </p>
      </DocumentationCard>

      <WorkflowCard steps={["Select video", "Add audio (optional)", "Generate", "Confirm", "Track progress", "Download"]} />

      <DocumentationCard title="Uploading Files" icon={<FaUpload />}>
        <DocTable
          columns={["File", "Required", "Accepted", "Size limit"]}
          rows={[
            ["Video", "Yes", ".mp4, .avi, .mov, .mkv, .webm", "Set in Settings → Upload Configuration (1–500 MB)."],
            ["Audio", "No", ".mp3, .wav", "Set in Settings → Upload Configuration (1–500 MB)."],
          ]}
        />
        <p>
          Click an upload zone (or its Upload button) to choose a file. The file name appears under the button. If a
          file is larger than your limit you see a message with the file size and your allowed maximum, and the file is
          not selected.
        </p>
        <Figure caption="Illustration of the Business Processor card (not a live screenshot).">
          <div className="bm-fig-row two">
            <div className="bm-fig-box tall">Select Video file</div>
            <div className="bm-fig-box tall">Select Audio file (optional)</div>
          </div>
          <div className="bm-fig-progress"><i /></div>
          <div className="bm-fig-steps"><span className="on">Upload</span><span className="on">Validate</span><span className="on">Process</span><span>Generate</span><span>Complete</span></div>
        </Figure>
        <InfoPanel>While a job is running the upload controls are disabled; you can start a new job after it finishes, fails or is cancelled.</InfoPanel>
      </DocumentationCard>

      <DocumentationCard title="User Details (optional)" icon={<FaUserEdit />}>
        <p>
          Tick <strong>Provide user details</strong> to enter a username and an email address. The username is shown as
          the uploader on the Dashboard, and the email address receives the generated documents when email delivery is
          enabled on the server. The fields are validated before you can continue:
        </p>
        <DocList items={[
          "Username: 3–20 characters; letters, underscores and single spaces only; no numbers; no leading/trailing or consecutive spaces; the same character may not repeat three or more times.",
          "Email: must be a valid address (for example name@example.com).",
        ]} />
      </DocumentationCard>

      <DocumentationCard title="Generate and Confirm" icon={<FaPlay />}>
        <p>
          Press <strong>Generate</strong>. A <strong>Ready to Generate?</strong> window shows your file names. Choose
          <strong> Edit</strong> to go back, or <strong>OK, Start</strong> to upload the files and start the pipeline.
          Progress, the current stage and a status message are shown while it runs. Detailed stages are described under
          “Processing Pipeline”.
        </p>
      </DocumentationCard>

      <DocumentationCard title="No Audio Detected" icon={<FaMicrophoneSlash />}>
        <p>
          After the upload, the server checks the video itself. If you did not upload an audio file and the video has no
          usable audio (no audio track, or a track that is almost entirely silent), the job pauses and a
          <strong> No Audio Detected</strong> window appears:
        </p>
        <DocList items={[
          <><strong>Continue</strong> — generate the documents from the video frames only. The output carries a notice that no audio was used.</>,
          <><strong>Cancel</strong> — stop; nothing is processed and the job is marked Cancelled.</>,
        ]} />
      </DocumentationCard>

      <DocumentationCard title="Cancelling" icon={<FaBan />}>
        <p>
          While a job is running the <strong>Cancel Processing</strong> button stops it. The server stops the audio
          processing, the video processing and the document generation, and the job is shown as <strong>Cancelled</strong>.
          After a job ends, the button becomes <strong>Reset</strong>, which clears the page for a new upload.
        </p>
        <NotePanel>
          Reloading or closing the page while a job runs asks you to confirm and, once you leave, cancels the job.
          Logging out also cancels your running jobs. A job that has already completed is never changed to Cancelled.
        </NotePanel>
      </DocumentationCard>

      <DocumentationCard title="Results" icon={<FaFileDownload />}>
        <p>When the job finishes, two result cards appear:</p>
        <DocList items={[
          <><strong>Workflow Steps</strong> — the clean step-by-step document with screenshots.</>,
          <><strong>Manual Validation</strong> — a document for cross-checking narration against what is on screen. It is empty when no audio was used.</>,
        ]} />
        <p>
          Each card shows <code>READY</code> and a <strong>Download</strong> link. If some stages reported errors, an
          expandable “service error(s)” list shows which service failed and why; you may still receive partial output.
        </p>
      </DocumentationCard>
    </div>
  );
}
