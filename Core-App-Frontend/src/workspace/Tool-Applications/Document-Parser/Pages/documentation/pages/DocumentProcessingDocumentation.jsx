import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import WorkflowCard from "../components/WorkflowCard";
import { FaInfoCircle, FaBullseye, FaPuzzlePiece, FaDesktop, FaMousePointer, FaHandPointer, FaCheckCircle, FaStar, FaStickyNote, FaClipboardCheck } from "react-icons/fa";
import "../../../Styles/documentation.css";

function DocumentProcessingDocumentation() {
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
          The Document Processing page is where you upload a document and the system reads it using the process
          model you selected. After the system reads the document, you can review the extracted information,
          correct any missing values, and save the results. This page opens in a new tab when you click
          <em>Process</em> on a model in the Document Process Model page.
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
          <li>Choose a document to process (PDF, JPG, JPEG, PNG, TIFF, or BMP).</li>
          <li>Choose where the results should be saved (Output Folder).</li>
          <li>Start the processing of the document.</li>
          <li>View the original document and the extraction results side by side.</li>
          <li>Review and correct the extracted information before saving.</li>
          <li>Save the results as a CSV file in the output folder.</li>
        </ul>
      </DocumentationCard>

      {/* Page Layout */}
      <DocumentationCard 
        title="Page Layout" 
        icon={<FaDesktop />}
      >
        <ul className="doc-list">
          <li><strong>Top Bar:</strong> Shows the model name and the document processing title, the file chooser, the Output Folder box, and the <em>Process</em> button.</li>
          <li><strong>Left Panel:</strong> The document viewer with tabs for <em>Original Document</em> and <em>Extraction Results</em>.</li>
          <li><strong>Right Panel:</strong> The validation panel where you review and correct the extracted information.</li>
          <li><strong>Bottom of Right Panel:</strong> The <em>Mark as Invalid</em> and <em>Submit</em> buttons.</li>
        </ul>
      </DocumentationCard>

      {/* Top Bar Controls */}
      <DocumentationCard 
        title="Top Bar Controls" 
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
              <td>📁 Choose Document</td>
              <td>Opens your file browser so you can select a document to process.</td>
              <td>Use this to choose the document you want to read. Supported formats are PDF, JPG, JPEG, PNG, TIFF, and BMP.</td>
            </tr>
            <tr>
              <td>Output Folder</td>
              <td>A text box where you enter the folder path where the results (CSV files) should be saved.</td>
              <td>Enter the full folder path, for example <em>C:\Exports</em> or <em>/home/user/exports</em>. This is required before processing.</td>
            </tr>
            <tr>
              <td>▶ Process</td>
              <td>Starts the processing of the selected document using the selected model.</td>
              <td>Use this after choosing a document and entering the output folder. The button shows "Processing..." while the document is being read.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Document Viewer */}
      <DocumentationCard 
        title="Document Viewer" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          The left panel shows your document. It has two tabs:
        </p>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Tab</th>
              <th>What It Shows</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Original Document</td>
              <td>The document as you uploaded it. You can zoom in and out and move between pages.</td>
            </tr>
            <tr>
              <td>Extraction Results</td>
              <td>The document with the extracted information highlighted. You can also drag a box around text on the image to fill in a selected field.</td>
            </tr>
          </tbody>
        </table>
        <p>
          Above the document you will find:
        </p>
        <ul className="doc-list">
          <li><strong>Zoom Controls:</strong> The − and + buttons let you zoom out and in (from 25% to 300%).</li>
          <li><strong>Previous / Next:</strong> Buttons to move between pages of a multi-page document.</li>
          <li><strong>Page Counter:</strong> Shows which page you are viewing, for example "Page 1 / 3".</li>
        </ul>
      </DocumentationCard>

      {/* Validation Panel */}
      <DocumentationCard 
        title="Validation Panel" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          The right panel is where you check the information the system extracted. It shows:
        </p>
        <ul className="doc-list">
          <li><strong>Fields to Validate:</strong> A heading showing how many fields still need a value, for example "3 Fields to Validate".</li>
          <li><strong>Field Filter:</strong> A dropdown with <em>All Fields</em>, <em>Required fields</em>, and <em>Invalid fields</em>.</li>
          <li><strong>Section Filter:</strong> A dropdown with <em>All Sections</em>, <em>Form Only</em>, and <em>Table Only</em>.</li>
          <li><strong>Form Fields:</strong> A list of the individual fields with their extracted values. You can click inside a field and type a value, or drag-select text from the document image.</li>
          <li><strong>Tables:</strong> Each table shows its columns and rows. You can edit cell values, add rows, or delete rows.</li>
        </ul>
      </DocumentationCard>

      {/* Validation Panel Buttons */}
      <DocumentationCard 
        title="Validation Panel Buttons" 
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
              <td>+ Add Row</td>
              <td>Adds a new empty row to a table.</td>
              <td>Use this when the document has more rows than the system found.</td>
            </tr>
            <tr>
              <td>🗑 (Delete Row)</td>
              <td>Removes a row from a table.</td>
              <td>Use this to remove a row that should not be there.</td>
            </tr>
            <tr>
              <td>i (Info)</td>
              <td>Shows a message explaining why a required field is missing.</td>
              <td>Use this when you see the "i" icon next to a field to understand what is missing.</td>
            </tr>
            <tr>
              <td>Mark as Invalid</td>
              <td>Marks the current page as invalid and moves to the next page.</td>
              <td>Use this when the document page is unreadable or the extracted information is wrong and cannot be corrected.</td>
            </tr>
            <tr>
              <td>Submit</td>
              <td>Saves the extracted information for the current page as a CSV file in the output folder.</td>
              <td>Use this after you have reviewed and corrected all the required fields. This button is unavailable while required fields are missing.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Popups */}
      <DocumentationCard 
        title="Popups and Messages" 
        icon={<FaCheckCircle />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Message</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Processing Document — Please wait while the document is being processed...</td>
              <td>The system is reading your document. Do not close the page.</td>
            </tr>
            <tr>
              <td>Start Processing — Do you want to start document processing?</td>
              <td>Confirmation before processing begins. Choose <em>Process</em> or <em>Cancel</em>.</td>
            </tr>
            <tr>
              <td>Please choose a document to upload (PDF, JPG, PNG, TIFF, or BMP).</td>
              <td>You clicked Process without choosing a document.</td>
            </tr>
            <tr>
              <td>File format not supported.</td>
              <td>The file you chose is not a supported format.</td>
            </tr>
            <tr>
              <td>Please select an extraction model before processing.</td>
              <td>No model is selected for this processing job.</td>
            </tr>
            <tr>
              <td>Please enter a valid output folder path.</td>
              <td>The Output Folder box is empty or the path is not valid.</td>
            </tr>
            <tr>
              <td>Please fill all required fields.</td>
              <td>You tried to submit while required fields are still empty.</td>
            </tr>
            <tr>
              <td>Data missing. Drag and select the value from the document image to populate this field.</td>
              <td>A required field has no value. Select the field, then drag a box around the text on the document image.</td>
            </tr>
            <tr>
              <td>Page submitted successfully. Continuing to next page...</td>
              <td>The current page was saved and the system moved to the next page.</td>
            </tr>
            <tr>
              <td>Job Completed Successfully — The CSV has been saved to the selected output path and the document has been recorded in process history.</td>
              <td>All pages were saved. Click <em>OK</em> to return to the Document Process Model page.</td>
            </tr>
            <tr>
              <td>Validation Error</td>
              <td>Shown when something needs your attention before continuing.</td>
            </tr>
            <tr>
              <td>Reprocess Required — This job was interrupted due to a client disconnect. Please select the original file and reprocess the document using the previously selected model.</td>
              <td>A previous processing job was interrupted. Choose the original file again and click Process.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Statuses */}
      <DocumentationCard 
        title="Processing Statuses" 
        icon={<FaCheckCircle />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Pending</td>
              <td>The document is waiting to be processed.</td>
            </tr>
            <tr>
              <td>Processing</td>
              <td>The document is currently being read by the system.</td>
            </tr>
            <tr>
              <td>Completed</td>
              <td>The document was processed and the results were saved.</td>
            </tr>
            <tr>
              <td>Failed</td>
              <td>The processing could not be completed.</td>
            </tr>
            <tr>
              <td>Cancelled</td>
              <td>The processing was stopped before it finished.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      

      <DocumentationCard 
        title="Complete User Workflow" 
        icon={<FaClipboardCheck />}
      >
        <ul className="doc-list">
          <li><strong>Open the page:</strong> Click <em>Process</em> on a model in the Document Process Model page. The page opens in a new tab.</li>
          <li><strong>Choose a document:</strong> Click <em>📁 Choose Document</em> and select a PDF or image file.</li>
          <li><strong>Enter the output folder:</strong> Type the folder path where the results should be saved.</li>
          <li><strong>Start processing:</strong> Click <em>▶ Process</em> and confirm in the popup.</li>
          <li><strong>Wait for the system to read the document:</strong> A progress message appears while the document is being processed.</li>
          <li><strong>Review the extracted information:</strong> Check the fields and tables in the validation panel.</li>
          <li><strong>Correct missing values:</strong> Click inside a field and type the value, or select the field and drag a box around the text on the document image.</li>
          <li><strong>Add or remove table rows:</strong> Use <em>+ Add Row</em> and the 🗑 button as needed.</li>
          <li><strong>Submit the page:</strong> Click <em>Submit</em> to save the results. The system moves to the next page if there is one.</li>
          <li><strong>Finish:</strong> When all pages are done, the "Job Completed Successfully" message appears. Click <em>OK</em> to return to the models page.</li>
        </ul>
      </DocumentationCard>

      {/* Notes */}
      <DocumentationCard 
        title="Notes" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            <strong>Note:</strong> The uploaded document is deleted automatically after processing finishes.
            The results are saved as CSV files in the output folder you entered.
          </p>
        </div>
        <div className="doc-info-panel">
          <p>
            <strong>Tip:</strong> For best results, use clear and legible documents. If a required field is
            missing, click the "i" icon to see why, then drag-select the value from the document image.
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default DocumentProcessingDocumentation;