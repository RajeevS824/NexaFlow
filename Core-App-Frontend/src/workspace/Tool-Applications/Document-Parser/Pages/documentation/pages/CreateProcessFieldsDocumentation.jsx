import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import WorkflowCard from "../components/WorkflowCard";
import { FaInfoCircle, FaBullseye, FaPuzzlePiece, FaDesktop, FaMousePointer, FaHandPointer, FaCheckCircle, FaStar, FaStickyNote, FaClipboardCheck } from "react-icons/fa";
import "../../../Styles/documentation.css";

function CreateProcessFieldsDocumentation() {
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
          The Create Process Fields page is where you tell the system exactly what information to capture from your
          documents. You can define individual fields (for example, Invoice Number, Date, Total Amount) and tables
          (for example, a list of line items). This page appears after you create a process model and click Next.
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
          <li>Add individual fields that the system should look for in the document.</li>
          <li>Add tables that contain repeated rows of information.</li>
          <li>Set the data type of each field (Text, Number, or Date).</li>
          <li>Mark fields as required or optional.</li>
          <li>Add alternative names (aliases) so the system can recognise the same information written differently.</li>
          <li>Save the model and move to the Document Process Model page.</li>
        </ul>
      </DocumentationCard>

      {/* Page Layout */}
      <DocumentationCard 
        title="Page Layout" 
        icon={<FaDesktop />}
      >
        <ul className="doc-list">
          <li><strong>Top Section:</strong> The page heading with the model name, the <em>Save & Close</em> button, and a close (✕) button.</li>
          <li><strong>Toolbar:</strong> The <em>+ Add Form</em> and <em>+ Add Table</em> buttons, plus a table dropdown and edit/delete icons when a table is selected.</li>
          <li><strong>Left Panel:</strong> A list of the fields (or table columns) you have added, shown in a table.</li>
          <li><strong>Right Panel:</strong> The properties form where you enter the details of the selected field.</li>
        </ul>
      </DocumentationCard>

      {/* Toolbar Buttons */}
      <DocumentationCard 
        title="Toolbar Buttons" 
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
              <td>+ Add Form</td>
              <td>Switches the page to the form fields view so you can add individual fields.</td>
              <td>Use this when you want to capture single pieces of information like Invoice Number or Date.</td>
            </tr>
            <tr>
              <td>+ Add Table</td>
              <td>Switches the page to the table view. If no table exists yet, it opens the Create Table window.</td>
              <td>Use this when your document contains repeated rows of information, like a list of items.</td>
            </tr>
            <tr>
              <td>Table Dropdown</td>
              <td>Lets you choose which table you are working on when you have more than one table.</td>
              <td>Use this to switch between tables.</td>
            </tr>
            <tr>
              <td>✎ (Edit Table)</td>
              <td>Opens the Edit Table window for the selected table.</td>
              <td>Use this to rename a table or change its start/end identifiers.</td>
            </tr>
            <tr>
              <td>🗑 (Delete Table)</td>
              <td>Asks you to confirm, then deletes the selected table.</td>
              <td>Use this to remove a table you no longer need.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Header Buttons */}
      <DocumentationCard 
        title="Header Buttons" 
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
              <td>Save & Close</td>
              <td>Saves the model with all its fields and tables, then takes you to the <strong>Document Process Model</strong> page.</td>
              <td>Use this when you have finished defining all the fields and tables.</td>
            </tr>
            <tr>
              <td>✕ (Close)</td>
              <td>Returns you to the <strong>Create Process Model</strong> page.</td>
              <td>Use this to go back without saving the fields.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Field List Table */}
      <DocumentationCard 
        title="Field List Table" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          The table on the left shows all the fields you have added. The columns are:
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
              <td>Field Name / Column Name</td>
              <td>The internal name of the field. For tables, this is called Column Name.</td>
            </tr>
            <tr>
              <td>Field Label / Column Label</td>
              <td>The display name of the field that appears in the document.</td>
            </tr>
            <tr>
              <td>Datatype</td>
              <td>The type of data: String (text), Number, or Date.</td>
            </tr>
            <tr>
              <td>Aliases</td>
              <td>The number of alternative names added for this field.</td>
            </tr>
            <tr>
              <td>Action</td>
              <td>Contains the ✎ (Edit) and 🗑 (Delete) buttons for the field.</td>
            </tr>
          </tbody>
        </table>
        <p>
          When the list is empty, the message "No fields yet. Click Add." is shown.
        </p>
      </DocumentationCard>

      {/* Field Properties */}
      <DocumentationCard 
        title="Field Properties Panel" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          The panel on the right is where you enter the details of a field. The fields are:
        </p>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Purpose</th>
              <th>Required?</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Field Name / Column Name</td>
              <td>The internal name used to identify this field.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>Field Label / Column Label</td>
              <td>The name that appears in the document and in the results.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>Datatype</td>
              <td>Choose <strong>String</strong> (text), <strong>Number</strong>, or <strong>Date</strong>.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>Required Field</td>
              <td>A checkbox. When selected, the system will not finish the job until this field has a value.</td>
              <td>No (checkbox)</td>
            </tr>
            <tr>
              <td>Aliases</td>
              <td>Alternative names the system should also recognise for this field. Type an alias and click <em>Add</em>.</td>
              <td>No</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Property Panel Buttons */}
      <DocumentationCard 
        title="Property Panel Buttons" 
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
              <td>Add / Update</td>
              <td>Adds the field to the list, or updates the field you are editing.</td>
              <td>Use this after filling in the field details.</td>
            </tr>
            <tr>
              <td>Reset</td>
              <td>Clears the form so you can start over, or restores the original values when editing.</td>
              <td>Use this to undo your changes in the panel.</td>
            </tr>
            <tr>
              <td>Add (next to Alias)</td>
              <td>Adds the typed alias to the list of alternative names.</td>
              <td>Use this to add an alternative name for the field.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Table Popups */}
      <DocumentationCard 
        title="Create Table and Edit Table Windows" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          When you click <em>+ Add Table</em> for the first time, or click the ✎ icon, a window opens with these options:
        </p>
        <table className="doc-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Purpose</th>
              <th>Required?</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Table Name</td>
              <td>A unique name for the table.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>Table Start Identifier</td>
              <td>Text or a heading that tells the system where the table begins in the document. Type it and click <em>Add</em>.</td>
              <td>No</td>
            </tr>
            <tr>
              <td>Table End Identifier</td>
              <td>Text or a heading that tells the system where the table ends. Type it and click <em>Add</em>.</td>
              <td>No</td>
            </tr>
            <tr>
              <td>Required Table</td>
              <td>A checkbox. When selected, the table must be present in the document.</td>
              <td>No (checkbox)</td>
            </tr>
          </tbody>
        </table>
        <p>
          The window has <em>Cancel</em> and <em>Save</em> buttons. <em>Save</em> creates or updates the table.
        </p>
      </DocumentationCard>

      {/* Validation Messages */}
      <DocumentationCard 
        title="Validation Messages" 
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
              <td>This is mandatory field name / column name</td>
              <td>You must enter a Field Name (or Column Name).</td>
            </tr>
            <tr>
              <td>This is mandatory field label / column label</td>
              <td>You must enter a Field Label (or Column Label).</td>
            </tr>
            <tr>
              <td>Field Name already exists. Please enter a unique Field Name.</td>
              <td>Another field already uses this name.</td>
            </tr>
            <tr>
              <td>Field Label already exists. Please enter a unique Field Label.</td>
              <td>Another field already uses this label.</td>
            </tr>
            <tr>
              <td>Column Name already exists. Please enter a unique Column Name.</td>
              <td>Another column in the table already uses this name.</td>
            </tr>
            <tr>
              <td>Column Label already exists. Please enter a unique Column Label.</td>
              <td>Another column in the table already uses this label.</td>
            </tr>
            <tr>
              <td>Alias already exists. Please enter a unique alias.</td>
              <td>This alternative name was already added.</td>
            </tr>
            <tr>
              <td>Table Name is mandatory.</td>
              <td>You must enter a table name.</td>
            </tr>
            <tr>
              <td>Table Name already exists. Please enter a unique Table Name.</td>
              <td>Another table already uses this name.</td>
            </tr>
            <tr>
              <td>Start Identifier already exists. Please enter a unique identifier.</td>
              <td>This start identifier was already added.</td>
            </tr>
            <tr>
              <td>End Identifier already exists. Please enter a unique identifier.</td>
              <td>This end identifier was already added.</td>
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
          <li><strong>Delete:</strong> When you click 🗑 on a field or table, the system asks "Are you sure you want to delete this field?" (or the table name). You can choose <em>Cancel</em> or <em>Delete</em>.</li>
          <li><strong>Unsaved Changes:</strong> When you try to leave or switch while a field has unsaved changes, the system asks what you want to do. You can choose <em>Cancel</em>, <em>Save</em>, or <em>Discard</em>.</li>
        </ul>
      </DocumentationCard>

   

      <DocumentationCard 
        title="Complete User Workflow" 
        icon={<FaClipboardCheck />}
      >
        <ul className="doc-list">
          <li><strong>Open the page:</strong> After creating a process model, click <em>Next</em> to reach this page.</li>
          <li><strong>Add a form field:</strong> Click <em>+ Add Form</em>, enter the Field Name and Field Label, choose the Datatype, and optionally mark it as Required.</li>
          <li><strong>Add aliases (optional):</strong> Type an alternative name and click <em>Add</em>.</li>
          <li><strong>Save the field:</strong> Click <em>Add</em> (or <em>Update</em> when editing).</li>
          <li><strong>Add a table:</strong> Click <em>+ Add Table</em>, enter a Table Name, add Start and End Identifiers, and click <em>Save</em>.</li>
          <li><strong>Add table columns:</strong> With the table selected, use the properties panel to add each column the same way you add form fields.</li>
          <li><strong>Edit or delete:</strong> Use the ✎ and 🗑 buttons in the list to edit or remove fields and tables.</li>
          <li><strong>Save the model:</strong> Click <em>Save & Close</em> to save everything and go to the Document Process Model page.</li>
        </ul>
      </DocumentationCard>

      {/* Notes */}
      <DocumentationCard 
        title="Notes" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            <strong>Note:</strong> Your work is saved as a draft automatically while you work on this page.
            If you close the page by accident, the system can restore your fields when you return.
          </p>
        </div>
        <div className="doc-info-panel">
          <p>
            <strong>Tip:</strong> Use aliases to help the system recognise the same information written in
            different ways. For example, for a "Date" field you could add aliases like "Invoice Date" or "Date of Issue".
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default CreateProcessFieldsDocumentation;