import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import WorkflowCard from "../components/WorkflowCard";
import { FaInfoCircle, FaBullseye, FaPuzzlePiece, FaDesktop, FaMousePointer, FaHandPointer, FaCheckCircle, FaStar, FaStickyNote, FaClipboardCheck } from "react-icons/fa";
import "../../../Styles/documentation.css";

function DocumentProcessModelDocumentation() {
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
          The Document Process Model page shows all the process models you have created. From here you can search
          for a model, create a new one, process a document using a model, view its history, edit it, or delete it.
          This is the main management page for your models.
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
          <li>See a list of all your process models.</li>
          <li>Search for a specific model by name, engine, document type, or date.</li>
          <li>Create a new process model.</li>
          <li>Start processing a document using a model.</li>
          <li>View the processing history of a model.</li>
          <li>Edit a model's settings and fields.</li>
          <li>Delete a model.</li>
        </ul>
      </DocumentationCard>

      {/* Page Layout */}
      <DocumentationCard 
        title="Page Layout" 
        icon={<FaDesktop />}
      >
        <ul className="doc-list">
          <li><strong>Top Section:</strong> The page heading "Document Process Model" with a search box, the <em>+ Create</em> button, and the <em>Cancel</em> button.</li>
          <li><strong>Main Section:</strong> A card titled "Models" containing a table with all your models.</li>
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
              <td>Filters the model list as you type. It searches the model name, engine type, document type, created date, and updated date.</td>
              <td>Use this when you have many models and want to find one quickly.</td>
            </tr>
            <tr>
              <td>+ Create</td>
              <td>Takes you to the <strong>Create Process Model</strong> page to build a new model.</td>
              <td>Use this to create a new model.</td>
            </tr>
            <tr>
              <td>Cancel</td>
              <td>Returns you to the Document Parser Dashboard.</td>
              <td>Use this to leave the page.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Models Table */}
      <DocumentationCard 
        title="Models Table" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          The table lists every model you have created. Each column shows:
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
              <td>ID</td>
              <td>The row number of the model in the list.</td>
            </tr>
            <tr>
              <td>Model Name</td>
              <td>The name you gave the model when you created it.</td>
            </tr>
            <tr>
              <td>Engine Type</td>
              <td>Whether the model uses OCR or LLM to read documents.</td>
            </tr>
            <tr>
              <td>Document Type</td>
              <td>The type of document the model is set up for (Invoice, Receipt, Contract, or Other).</td>
            </tr>
            <tr>
              <td>Form Fields</td>
              <td>The number of individual fields defined in the model.</td>
            </tr>
            <tr>
              <td>Tables</td>
              <td>The number of tables defined in the model.</td>
            </tr>
            <tr>
              <td>Created</td>
              <td>The date and time the model was created.</td>
            </tr>
            <tr>
              <td>Updated</td>
              <td>The date and time the model was last updated.</td>
            </tr>
            <tr>
              <td>Action</td>
              <td>Contains the <em>Process</em>, <em>History</em>, <em>Edit</em>, and <em>Delete</em> buttons for the model.</td>
            </tr>
          </tbody>
        </table>
        <p>
          If there are no models, the message "No extraction models found." is shown.
        </p>
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
              <td>Process</td>
              <td>Opens the <strong>Document Processing</strong> page in a new tab with this model selected, so you can upload a document and process it.</td>
              <td>Use this when you want to process a document with this model. This button is unavailable if the model has no fields or tables.</td>
            </tr>
            <tr>
              <td>History</td>
              <td>Takes you to the <strong>History Extraction Model</strong> page filtered to show the processing history of this model.</td>
              <td>Use this to see the documents that were processed with this model.</td>
            </tr>
            <tr>
              <td>Edit</td>
              <td>Asks you to confirm, then opens the <strong>Create Process Model</strong> page in edit mode so you can change the model's settings and fields.</td>
              <td>Use this to update a model.</td>
            </tr>
            <tr>
              <td>Delete</td>
              <td>Asks you to confirm, then permanently removes the model. If the model has processing history, the system warns that all associated process data will also be deleted.</td>
              <td>Use this to remove a model you no longer need.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Confirmation Popups */}
      <DocumentationCard 
        title="Confirmation Popups" 
        icon={<FaCheckCircle />}
      >
        <ul className="doc-list">
          <li><strong>Edit Model:</strong> When you click <em>Edit</em>, the system asks "Do you want to edit [model name]?" with <em>No</em> and <em>Yes</em> buttons.</li>
          <li><strong>Delete Model:</strong> When you click <em>Delete</em>, the system asks "Do you want to delete [model name]?" with <em>No</em> and <em>Yes</em> buttons. If the model has processed documents, the message explains that deleting the model will also delete all associated process data permanently.</li>
          <li><strong>No Fields Available:</strong> If you click <em>Process</em> on a model that has no fields or tables, a message says "Please create at least one Form Field or one Table before processing."</li>
          <li><strong>Popup Blocked:</strong> If your browser blocks the new processing tab, a message asks you to allow popup permission.</li>
          <li><strong>Loading Error:</strong> If the models cannot be loaded, a message says "Unable to load extraction models."</li>
          <li><strong>Delete Error:</strong> If a model cannot be deleted, a message shows the reason.</li>
        </ul>
      </DocumentationCard>


      <DocumentationCard 
        title="Complete User Workflow" 
        icon={<FaClipboardCheck />}
      >
        <ul className="doc-list">
          <li><strong>Open the page:</strong> Click <em>Document Process Model</em> in the sidebar, or click <em>Process Document</em> on the Dashboard.</li>
          <li><strong>Find a model:</strong> Use the search box to filter the list by name, engine, document type, or date.</li>
          <li><strong>Process a document:</strong> Click <em>Process</em> on the model you want to use. The processing page opens in a new tab.</li>
          <li><strong>View history:</strong> Click <em>History</em> to see the documents processed with that model.</li>
          <li><strong>Edit a model:</strong> Click <em>Edit</em>, confirm, and update the model details and fields.</li>
          <li><strong>Delete a model:</strong> Click <em>Delete</em>, confirm, and the model is removed.</li>
          <li><strong>Create a new model:</strong> Click <em>+ Create</em> to start building a new model.</li>
          <li><strong>Leave the page:</strong> Click <em>Cancel</em> to return to the Dashboard.</li>
        </ul>
      </DocumentationCard>

      {/* Notes */}
      <DocumentationCard 
        title="Notes" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            <strong>Note:</strong> Deleting a model is permanent. If the model has processed documents,
            all of that processing data is deleted as well.
          </p>
        </div>
        <div className="doc-info-panel">
          <p>
            <strong>Tip:</strong> Use the search box to quickly find a model by typing part of its name
            or the document type it handles.
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default DocumentProcessModelDocumentation;