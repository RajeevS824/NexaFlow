import React from "react";
import { FaInfoCircle, FaStream, FaRandom, FaStopCircle } from "react-icons/fa";
import { DocumentationCard, DocList, DocTable, InfoPanel, NotePanel, WorkflowCard } from "../components/DocComponents";
import "../../../Styles/documentation.css";

export default function PipelineDocumentation() {
  return (
    <div className="bm-doc-page">
      <DocumentationCard title="Overview" icon={<FaInfoCircle />}>
        <p>
          Every job moves through five stages, shown as labels under the progress bar on the Business Flow page. The
          highlighted labels show how far the job has got.
        </p>
      </DocumentationCard>

      <WorkflowCard steps={["Upload", "Validate", "Process", "Generate", "Complete"]} />

      <DocumentationCard title="The Five Stages" icon={<FaStream />}>
        <DocTable
          columns={["Stage", "What happens"]}
          rows={[
            ["Upload", "Your video (and optional audio) is sent to the server. The first part of the progress bar fills while the upload runs."],
            ["Validate", "The server checks the files and, when needed, inspects the video for an audio track. If there is no usable audio and you did not upload any, the job pauses for your “No Audio Detected” answer."],
            ["Process", "The audio is transcribed to text, and the video is analysed frame by frame to describe the actions on screen. Both run at the same time."],
            ["Generate", "A language model combines the transcript and the frame descriptions into the Workflow Steps and Manual Validation documents."],
            ["Complete", "The documents are saved and the download links appear. If you gave an email address and email delivery is enabled, they are also emailed."],
          ]}
        />
      </DocumentationCard>

      <DocumentationCard title="Job Statuses" icon={<FaRandom />}>
        <DocTable
          columns={["Status", "Meaning"]}
          rows={[
            ["Processing", "Queued, running, or paused waiting for your No Audio Detected answer."],
            ["Completed", "Finished successfully, or finished with partial results (some stage reported an error but documents were produced)."],
            ["Failed", "Stopped because of an error."],
            ["Cancelled", "Stopped on request: Cancel Processing, leaving the page, answering Cancel in the No Audio Detected window, or logging out."],
          ]}
        />
        <InfoPanel>The audio and video stages are independent: if one fails, the other still runs, and the report is built from what is available.</InfoPanel>
      </DocumentationCard>

      <DocumentationCard title="What Cancelling Stops" icon={<FaStopCircle />}>
        <p>When a job is cancelled, the server:</p>
        <DocList items={[
          "stops the pipeline task and its audio and video polling;",
          "asks the audio service and the video service to stop the work they are doing for that job (audio transcription and its ffmpeg step, and the frame-by-frame video analysis);",
          "stops document generation before further documents are written or any email is sent;",
          "removes the job's temporary files, and saves the final status.",
        ]} />
        <NotePanel>
          Cancellation only affects the job (or, on logout, your own active jobs). A job that already completed is left
          as Completed, even if a cancel arrives at the same moment. If a stage cannot be stopped because of an actual
          error, the job is recorded as Failed instead of Cancelled.
        </NotePanel>
      </DocumentationCard>
    </div>
  );
}
