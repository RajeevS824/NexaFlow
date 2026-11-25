import React from "react";
import { FaExclamationTriangle } from "react-icons/fa";
import { DocumentationCard, DocList } from "../components/DocComponents";
import "../../../Styles/documentation.css";

const ISSUES = [
  ["“File upload failed … maximum allowed upload size”", ["The file is larger than your limit. Choose a smaller file or raise the limit in Settings → Upload Configuration (maximum 500 MB)."]],
  ["“Network error – is the backend running?”", ["The Business Map server could not be reached. Check that it is running and that you are connected, then try again."]],
  ["The Dashboard shows an error banner or stays empty", ["“Couldn't reach the backend” means the statistics request failed. “Job list unavailable” means the file list could not be loaded. Both clear on their own once the server is reachable again (the page retries every 5 seconds)."]],
  ["Username or email rejected", ["Follow the rules shown in red under the fields: 3–20 letters/underscores/single spaces, no numbers, no character repeated three times, and a valid email address."]],
  ["The job is Failed", ["Open the job's result card and expand the “service error(s)” list to see which stage failed. Upload again; if it keeps failing, send the error text to your administrator."]],
  ["Completed with some errors", ["A stage reported an error but documents were still produced from the rest. Check the error list; the documents may be incomplete."]],
  ["“Couldn't reconnect to the previous job”", ["The server was restarted while a job was running. Upload the files again."]],
  ["The job shows Cancelled unexpectedly", ["The page was reloaded or closed, you answered Cancel in the No Audio Detected window, or you logged out while it was running. Upload again."]],
  ["The No Audio Detected window appears for a video with sound", ["The audio track was missing or almost entirely silent. Upload a separate audio file together with the video, or choose Continue to use video frames only."]],
  ["No documents were emailed", ["Email is sent only when you provided user details and email delivery is enabled on the server. You can always use the Download links."]],
  ["Logout takes a few seconds", ["If a job was running, Logout waits for the server to stop it first. It signs you out even if the cancellation reports a problem."]],
];

export default function Troubleshooting() {
  return (
    <div className="bm-doc-page">
      {ISSUES.map(([title, items]) => (
        <DocumentationCard key={title} title={title} icon={<FaExclamationTriangle />}>
          <DocList items={items} />
        </DocumentationCard>
      ))}
    </div>
  );
}
