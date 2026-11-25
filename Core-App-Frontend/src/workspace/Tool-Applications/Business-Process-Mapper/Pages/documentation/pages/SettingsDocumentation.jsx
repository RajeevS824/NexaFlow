import React from "react";
import { FaInfoCircle, FaFileAlt, FaUpload, FaKey, FaSave } from "react-icons/fa";
import { DocumentationCard, DocList, DocTable, InfoPanel, NotePanel } from "../components/DocComponents";
import "../../../Styles/documentation.css";

export default function SettingsDocumentation() {
  return (
    <div className="bm-doc-page">
      <DocumentationCard title="Overview" icon={<FaInfoCircle />}>
        <p>
          Business Map settings are opened from the main NexaFlow dashboard: click <strong>Settings</strong> in its
          sidebar and choose <strong>Business Process Mapper</strong>. The page opens in the same browser tab and has
          three sections plus <strong>Save</strong> and <strong>Reset to Default</strong> buttons.
        </p>
      </DocumentationCard>

      <DocumentationCard title="Logging Configuration" icon={<FaFileAlt />}>
        <DocTable
          columns={["Setting", "Description"]}
          rows={[
            ["Logging Path", "The folder where log files are stored. Click Change to edit it."],
            ["Logging Type", "Debug, Info or Error. With Debug or Error, all logs of that type are stored in the logging path. With Info you can switch Enable Logging on or off; when it is off, Info logs are kept on the server."],
          ]}
        />
      </DocumentationCard>

      <DocumentationCard title="Upload Configuration" icon={<FaUpload />}>
        <DocTable
          columns={["Setting", "Range", "Used by"]}
          rows={[
            ["Maximum Upload File Size for Video (MB)", "1–500", "The video upload zone on Business Flow, and the server."],
            ["Maximum Upload File Size for Audio (MB)", "1–500", "The audio upload zone on Business Flow, and the server."],
          ]}
        />
        <InfoPanel>Files above the limit are rejected immediately with a message that shows the file size and your allowed maximum.</InfoPanel>
      </DocumentationCard>

      <DocumentationCard title="LLM Configuration" icon={<FaKey />}>
        <p>Choose which credentials are used when the Generate stage calls the language model:</p>
        <DocList items={[
          <><strong>Default Application API Key</strong> — uses the key configured by the system; you need to enter nothing.</>,
          <><strong>Custom API key</strong> — use your own key. The saved key is never shown back; only a masked preview appears, and typing a new value is the way to change it.</>,
        ]} />
        <NotePanel>If custom keys are not available on your installation, a banner says so and the default credentials are used.</NotePanel>
      </DocumentationCard>

      <DocumentationCard title="Saving and Resetting" icon={<FaSave />}>
        <p>
          <strong>Save</strong> validates every field and saves only the sections you changed. <strong>Reset to Default</strong>
          asks for confirmation and then restores the logging, upload and LLM defaults.
        </p>
      </DocumentationCard>
    </div>
  );
}
