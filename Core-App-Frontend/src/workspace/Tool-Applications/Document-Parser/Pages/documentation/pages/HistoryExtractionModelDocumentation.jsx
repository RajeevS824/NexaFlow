import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import WorkflowCard from "../components/WorkflowCard";
import { FaInfoCircle, FaBullseye, FaPuzzlePiece, FaDesktop, FaMousePointer, FaHandPointer, FaCheckCircle, FaStar, FaStickyNote, FaClipboardCheck } from "react-icons/fa";
import "../../../Styles/documentation.css";

function HistoryExtractionModelDocumentation() {
  const workflowSteps = [
    "Dashboard",
    "Create Model",
    "Configure Fields",
    "Process Document",
    "Validate Results",
    "View History"
  ];

  return (
    <div className="doc-page">
      

      {/* Overview */}
      <DocumentationCard 
        title="Overview" 
        icon={<FaInfoCircle />}
      >
        <p>
          The History Extraction Model page shows a list of all the documents that have been processed using your
          models. For each document, you can see its status, the model that was used, the document type, the date
          it was processed, and where the results were saved. From this page you can also reprocess a failed or
          cancelled document, or validate a document that is still waiting.
        </p>
      </DocumentationCard>

      {/* Purpose */}
      <DocumentationCard 
        title="Purpose" 
        icon={<FaBullseye />}
      >
        <p>
          This page is used to:
        </p>
        <ul className="doc-list">
          <li>See every document that has been processed.</li>
          <li>Check the status of each processing job.</li>
          <li>Find out which model was used for each document.</li>
          <li>See where the results were saved (Output Folder).</li>
          <li>Reprocess a document that failed or was cancelled.</li>
          <li>Validate a document that is still processing or waiting.</li>
        </ul>
      </DocumentationCard>

      {/* Page Layout */}
      <DocumentationCard 
        title="Page Layout" 
        icon={<FaDesktop />}
      >
        <ul className="doc-list">
          <li><strong>Top Section:</strong> The page heading (showing the model name when opened from a specific model) with a search box and the <em>Back</em> button.</li>
          <li><strong>Main Section:</strong> A card titled "History" containing a table with all processed documents.</li>
        </ul>
      </DocumentationCard>

      {/* Header Controls */}
      <DocumentationCard 
        title="Header Controls" 
        icon={<FaHandPointer />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Control</th>
              <th>What It Does</th>
              <th>When to Use It</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Search Box</td>
              <td>Filters the history list as you type. It searches the model name, engine type, document type, status, and process date.</td>
              <td>Use this when you have many history entries and want to find one quickly.</td>
            </tr>
            <tr>
              <td>Back</td>
              <td>Returns you to the page you came from. If you opened history from a specific model, it returns to the Document Process Model page. Otherwise it returns to the Dashboard.</td>
              <td>Use this to leave the history page.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* History Table */}
      <DocumentationCard 
        title="History Table" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          The table lists every processed document. Each column shows:
        </p>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Column</th>
              <th>What It Shows</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Status</td>
              <td>The current status of the processing job. See the statuses table below.</td>
            </tr>
            <tr>
              <td>Model Name</td>
              <td>The name of the model that was used to process the document.</td>
            </tr>
            <tr>
              <td>Document Type</td>
              <td>The type of document that was processed (for example, Invoice or Receipt).</td>
            </tr>
            <tr>
              <td>Document Name</td>
              <td>The name of the document file that was processed.</td>
            </tr>
            <tr>
              <td>Process Date & Time</td>
              <td>The date and time the document was processed.</td>
            </tr>
            <tr>
              <td>Output Folder</td>
              <td>The folder where the results (CSV files) were saved.</td>
            </tr>
            <tr>
              <td>Actions</td>
              <td>Contains the <em>Reprocess</em> or <em>Validate</em> button depending on the status.</td>
            </tr>
          </tbody>
        </table>
        <p>
          If there are no history entries, the message "No history found" is shown.
        </p>
      </DocumentationCard>

      {/* Statuses */}
      <DocumentationCard 
        title="Statuses" 
        icon={<FaCheckCircle />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Meaning</th>
              <th>Available Action</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Pending</td>
              <td>The document is waiting to be processed.</td>
              <td>Validate</td>
            </tr>
            <tr>
              <td>Processing</td>
              <td>The document is currently being read by the system.</td>
              <td>Validate</td>
            </tr>
            <tr>
              <td>Completed</td>
              <td>The document was processed and the results were saved.</td>
              <td>None</td>
            </tr>
            <tr>
              <td>Failed</td>
              <td>The processing could not be completed.</td>
              <td>Reprocess</td>
            </tr>
            <tr>
              <td>Cancelled</td>
              <td>The processing was stopped before it finished.</td>
              <td>Reprocess</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Action Buttons */}
      <DocumentationCard 
        title="Action Buttons" 
        icon={<FaHandPointer />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Button</th>
              <th>What It Does</th>
              <th>When to Use It</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Reprocess</td>
              <td>Shows a confirmation message, then opens the <strong>Document Processing</strong> page with the same model selected so you can choose the original file again and process it.</td>
              <td>Use this when a document has the status <em>Failed</em> or <em>Cancelled</em> and you want to try again.</td>
            </tr>
            <tr>
              <td>Validate</td>
              <td>Opens the <strong>Document Processing</strong> page with the same model selected so you can review and correct the extracted information.</td>
              <td>Use this when a document has the status <em>Pending</em> or <em>Processing</em> and needs your review.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Confirmation Message */}
      <DocumentationCard 
        title="Confirmation Message" 
        icon={<FaCheckCircle />}
      >
        <p>
          When you click <em>Reprocess</em>, the system shows this message:
        </p>
        <div className="doc-note-panel">
          <p>
            "This job was interrupted due to a client disconnect. Please select the original file and reprocess
            the document using the previously selected model: [model name]."
          </p>
        </div>
        <p>
          Click <em>OK</em> to continue to the processing page, or <em>Cancel</em> to stay on the history page.
        </p>
      </DocumentationCard>

      
      <DocumentationCard 
        title="Complete User Workflow" 
        icon={<FaClipboardCheck />}
      >
        <ul className="doc-list">
          <li><strong>Open the page:</strong> Click <em>History</em> on the Dashboard, or click <em>History</em> on a model in the Document Process Model page.</li>
          <li><strong>Find a document:</strong> Use the search box to filter by model name, engine, document type, status, or date.</li>
          <li><strong>Check the status:</strong> Look at the Status column to see if the document is Pending, Processing, Completed, Failed, or Cancelled.</li>
          <li><strong>Reprocess a failed document:</strong> Click <em>Reprocess</em>, confirm, choose the original file, and process it again.</li>
          <li><strong>Validate a pending document:</strong> Click <em>Validate</em> to open the processing page and review the extracted information.</li>
          <li><strong>Leave the page:</strong> Click <em>Back</em> to return to where you came from.</li>
        </ul>
      </DocumentationCard>

      {/* Notes */}
      <DocumentationCard 
        title="Notes" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            <strong>Note:</strong> The Output Folder column shows where the results were saved. You can hover
            over the folder path to see the full path if it is too long.
          </p>
        </div>
        <div className="doc-info-panel">
          <p>
            <strong>Tip:</strong> Use the search box to quickly find documents by their status, for example
            type "failed" to see only the documents that need to be reprocessed.
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default HistoryExtractionModelDocumentation;