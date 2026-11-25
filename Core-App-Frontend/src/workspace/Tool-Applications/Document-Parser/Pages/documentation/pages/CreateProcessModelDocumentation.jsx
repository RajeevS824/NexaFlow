import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import WorkflowCard from "../components/WorkflowCard";
import { FaInfoCircle, FaBullseye, FaPuzzlePiece, FaDesktop, FaMousePointer, FaHandPointer, FaCheckCircle, FaStar, FaStickyNote, FaClipboardCheck } from "react-icons/fa";
import "../../../Styles/documentation.css";

function CreateProcessModelDocumentation() {
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
          The Create Process Model page is where you begin building a new process model. A process model tells the
          system what kind of document you want to read and how the information should be extracted. This is the
          first step before you define the specific fields to capture.
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
          <li>Give your model a name so you can find it later.</li>
          <li>Choose the type of document the model will read (for example, Invoice or Receipt).</li>
          <li>Choose the language of the documents.</li>
          <li>Optionally add a description to explain what the model does.</li>
          <li>Move to the next step where you define the fields to extract.</li>
        </ul>
      </DocumentationCard>

      {/* Page Layout */}
      <DocumentationCard 
        title="Page Layout" 
        icon={<FaDesktop />}
      >
        <ul className="doc-list">
          <li><strong>Top Section:</strong> The page heading "Create Process Model" with the <em>Next</em> and <em>Back</em> buttons.</li>
          <li><strong>Form Section:</strong> A card containing the model settings: Select Model, Model Name, Description, Document Type, and Language.</li>
        </ul>
      </DocumentationCard>

      {/* Input Fields */}
      <DocumentationCard 
        title="Input Fields" 
        icon={<FaPuzzlePiece />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Purpose</th>
              <th>What to Enter</th>
              <th>Required?</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Select Model</td>
              <td>Chooses the reading method the system will use to understand your documents.</td>
              <td>Choose <strong>OCR</strong> or <strong>LLM</strong> from the dropdown.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>Model Name</td>
              <td>A unique name to identify this model.</td>
              <td>Type a name between 3 and 30 characters. Only letters, numbers, spaces, underscores (_) and hyphens (-) are allowed. It cannot start or end with a space, and can contain at most 2 underscores or hyphens.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>Description</td>
              <td>An optional note explaining what the model is for.</td>
              <td>Type a short description. Maximum 100 characters.</td>
              <td>No</td>
            </tr>
            <tr>
              <td>Document Type</td>
              <td>Tells the system what kind of document this model will read.</td>
              <td>Choose <strong>Invoice</strong>, <strong>Receipt</strong>, <strong>Contract</strong>, or <strong>Other</strong>.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>Language</td>
              <td>Selects the language of the documents you will process.</td>
              <td>Choose from English, Spanish, French, German, Chinese, Japanese, Korean, Italian, or Hindi.</td>
              <td>Yes</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Dropdowns */}
      <DocumentationCard 
        title="Dropdown Options" 
        icon={<FaPuzzlePiece />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Dropdown</th>
              <th>Available Options</th>
              <th>Purpose</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Select Model</td>
              <td>OCR, LLM</td>
              <td>OCR reads the text directly from the document image. LLM uses a language model to understand the document content.</td>
            </tr>
            <tr>
              <td>Document Type</td>
              <td>Invoice, Receipt, Contract, Other</td>
              <td>Helps the system apply the right reading approach for the document.</td>
            </tr>
            <tr>
              <td>Language</td>
              <td>English, Spanish, French, German, Chinese, Japanese, Korean, Italian, Hindi</td>
              <td>Sets the language the system should expect when reading the document.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Buttons */}
      <DocumentationCard 
        title="Buttons" 
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
              <td>Next</td>
              <td>Saves the model settings you entered and takes you to the <strong>Create Process Fields</strong> page.</td>
              <td>Use this after you have filled in all the required fields correctly.</td>
            </tr>
            <tr>
              <td>Back</td>
              <td>Discards the current form and returns you to the page you came from (usually the Dashboard or the Document Process Model page).</td>
              <td>Use this if you want to leave without saving.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Validation Messages */}
      <DocumentationCard 
        title="Validation Messages" 
        icon={<FaCheckCircle />}
      >
        <p>
          The system checks your entries before you can continue. You may see these messages:
        </p>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Message</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Select Model is required</td>
              <td>You must choose OCR or LLM.</td>
            </tr>
            <tr>
              <td>Model Name is required</td>
              <td>You must enter a model name.</td>
            </tr>
            <tr>
              <td>Model Name must be at least 3 characters long</td>
              <td>Your model name is too short.</td>
            </tr>
            <tr>
              <td>Model Name cannot exceed 30 characters</td>
              <td>Your model name is too long.</td>
            </tr>
            <tr>
              <td>Model Name can contain only letters, numbers, spaces, underscores (_) and hyphens (-)</td>
              <td>You used a character that is not allowed.</td>
            </tr>
            <tr>
              <td>Model Name can contain a maximum of 2 underscores (_) or hyphens (-)</td>
              <td>You used too many special characters.</td>
            </tr>
            <tr>
              <td>Model Name must contain at least 3 letters or numbers</td>
              <td>Your name needs at least 3 actual letters or numbers.</td>
            </tr>
            <tr>
              <td>Model Name cannot start or end with a space</td>
              <td>Remove the space at the beginning or end of the name.</td>
            </tr>
            <tr>
              <td>Document Type is required</td>
              <td>You must choose a document type.</td>
            </tr>
            <tr>
              <td>Description cannot exceed 100 characters</td>
              <td>Your description is too long.</td>
            </tr>
            <tr>
              <td>Please enter a meaningful description</td>
              <td>The description contains only repeated characters or spaces.</td>
            </tr>
            <tr>
              <td>Language is required</td>
              <td>You must choose a language.</td>
            </tr>
            <tr>
              <td>Already model created. Type another name.</td>
              <td>A model with this name already exists. Choose a different name.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

   
      <DocumentationCard 
        title="Complete User Workflow" 
        icon={<FaClipboardCheck />}
      >
        <ul className="doc-list">
          <li><strong>Open the page:</strong> Click <em>Create Model</em> on the Dashboard, or use the sidebar.</li>
          <li><strong>Choose the reading method:</strong> Select <em>OCR</em> or <em>LLM</em> from the Select Model dropdown.</li>
          <li><strong>Enter a model name:</strong> Type a unique name that follows the rules above.</li>
          <li><strong>Add a description (optional):</strong> Explain what the model is for.</li>
          <li><strong>Choose the document type:</strong> Select Invoice, Receipt, Contract, or Other.</li>
          <li><strong>Choose the language:</strong> Select the language of your documents.</li>
          <li><strong>Click Next:</strong> The system saves your settings and takes you to the Create Process Fields page.</li>
          <li><strong>To leave without saving:</strong> Click <em>Back</em>.</li>
        </ul>
      </DocumentationCard>

      {/* Notes */}
      <DocumentationCard 
        title="Notes" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            <strong>Note:</strong> The model name you choose will be visible in the list of models on the
            Document Process Model page. Use a clear, descriptive name.
          </p>
        </div>
        <div className="doc-info-panel">
          <p>
            <strong>Tip:</strong> If you are editing an existing model, the page heading changes to
            "Edit Process Model" and the same form is used to update the model details.
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default CreateProcessModelDocumentation;