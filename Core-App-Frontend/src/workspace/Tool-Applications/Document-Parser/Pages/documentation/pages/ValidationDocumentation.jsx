import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import WorkflowCard from "../components/WorkflowCard";
import { FaInfoCircle, FaBullseye, FaPuzzlePiece, FaDesktop, FaMousePointer, FaHandPointer, FaCheckCircle, FaStar, FaStickyNote, FaClipboardCheck } from "react-icons/fa";
import "../../../Styles/documentation.css";

function ValidationDocumentation() {
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
          Validation is the part of the <strong>Document Processing</strong> page where you check the information
          the system extracted from your document. The validation panel appears on the right side of the page
          after the system finishes reading the document. Here you can see which fields still need a value,
          correct any wrong values, and save the results.
        </p>
      </DocumentationCard>

      {/* Purpose */}
      <DocumentationCard 
        title="Purpose" 
        icon={<FaBullseye />}
      >
        <p>
          The validation panel is used to:
        </p>
        <ul className="doc-list">
          <li>Show you every field the system was asked to extract.</li>
          <li>Highlight required fields that still have no value.</li>
          <li>Let you type a value directly into a field.</li>
          <li>Let you drag-select a value from the document image.</li>
          <li>Let you add, edit, or delete rows in tables.</li>
          <li>Prevent you from saving until all required fields are filled.</li>
        </ul>
      </DocumentationCard>

      {/* Page Layout */}
      <DocumentationCard 
        title="Page Layout" 
        icon={<FaDesktop />}
      >
        <ul className="doc-list">
          <li><strong>Fields to Validate:</strong> A heading at the top showing how many fields still need a value.</li>
          <li><strong>Filter Row:</strong> Two dropdowns — one for the field type and one for the section type.</li>
          <li><strong>Form Fields Section:</strong> A list of the individual fields with their values.</li>
          <li><strong>Table Sections:</strong> Each table shows its rows and columns with editable cells.</li>
          <li><strong>Bottom Buttons:</strong> <em>Mark as Invalid</em> and <em>Submit</em>.</li>
        </ul>
      </DocumentationCard>

      {/* Filters */}
      <DocumentationCard 
        title="Filters" 
        icon={<FaPuzzlePiece />}
      >
        <table className="doc-table">
          <thead>
            <tr>
              <th>Filter</th>
              <th>Options</th>
              <th>Purpose</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Field Filter</td>
              <td>All Fields, Required fields, Invalid fields</td>
              <td>Choose which fields to show. <em>Required fields</em> shows only the fields that must have a value. <em>Invalid fields</em> shows only the fields that are still empty.</td>
            </tr>
            <tr>
              <td>Section Filter</td>
              <td>All Sections, Form Only, Table Only</td>
              <td>Choose whether to see the form fields, the tables, or both.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

      {/* Form Fields */}
      <DocumentationCard 
        title="Form Fields" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          Each form field is shown as a row with:
        </p>
        <ul className="doc-list">
          <li><strong>Field Label:</strong> The name of the field (for example, "Invoice Number").</li>
          <li><strong>Value Box:</strong> The extracted value. You can click inside it and type a new value.</li>
          <li><strong>i (Info) Icon:</strong> Appears next to required fields that are still empty. Click it to see why the field is missing.</li>
        </ul>
        <p>
          If the field's data type is a Number, only numbers can be typed. If it is a Date, a date picker is shown.
        </p>
      </DocumentationCard>

      {/* Tables */}
      <DocumentationCard 
        title="Tables" 
        icon={<FaPuzzlePiece />}
      >
        <p>
          Each table in the model appears as its own section with:
        </p>
        <ul className="doc-list">
          <li><strong>Column Headers:</strong> The labels of each column in the table.</li>
          <li><strong>Rows:</strong> Each extracted row of the table with editable cells.</li>
          <li><strong>Action Column:</strong> A 🗑 button to delete a row.</li>
          <li><strong>+ Add Row:</strong> A button at the bottom to add a new empty row.</li>
        </ul>
        <p>
          When a table has no rows, the message "No rows available. Click Add Row." is shown.
        </p>
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
              <td>Mark as Invalid</td>
              <td>Marks the current page as invalid and saves the results as they are.</td>
              <td>Use this when the document page is unreadable or the extracted information is wrong and cannot be corrected.</td>
            </tr>
            <tr>
              <td>Submit</td>
              <td>Saves the extracted information for the current page as a CSV file in the output folder.</td>
              <td>Use this after all required fields are correctly filled. This button is unavailable while required fields are missing.</td>
            </tr>
            <tr>
              <td>+ Add Row</td>
              <td>Adds a new empty row to the table.</td>
              <td>Use this when the document has more rows than the system found.</td>
            </tr>
            <tr>
              <td>🗑 (Delete Row)</td>
              <td>Removes a row from the table.</td>
              <td>Use this to remove a row that should not be there.</td>
            </tr>
            <tr>
              <td>i (Info)</td>
              <td>Shows a message explaining why a required field is missing.</td>
              <td>Use this to understand what value is needed.</td>
            </tr>
          </tbody>
        </table>
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
              <td>X Fields to Validate</td>
              <td>The number of fields that still need a value on the current page.</td>
            </tr>
            <tr>
              <td>Data missing. Drag and select the value from the document image to populate this field.</td>
              <td>A required field is empty. Click the field, then drag a box around the text on the document image.</td>
            </tr>
            <tr>
              <td>Data missing. Click inside this field and drag-select the value from the document image. You can also enter the value manually.</td>
              <td>A required table cell is empty. You can fill it by dragging from the image or by typing directly.</td>
            </tr>
            <tr>
              <td>Please fill all required fields.</td>
              <td>You clicked Submit while required fields are still empty.</td>
            </tr>
            <tr>
              <td>Page submitted successfully. Continuing to next page...</td>
              <td>The current page was saved and the system moved to the next page.</td>
            </tr>
            <tr>
              <td>Page marked as invalid. Continuing to next page...</td>
              <td>The current page was marked as invalid and the system moved to the next page.</td>
            </tr>
          </tbody>
        </table>
      </DocumentationCard>

     

      <DocumentationCard 
        title="Complete User Workflow" 
        icon={<FaClipboardCheck />}
      >
        <ul className="doc-list">
          <li><strong>Open the validation panel:</strong> After the system finishes processing, the validation panel appears on the right.</li>
          <li><strong>Check the number of missing fields:</strong> The heading tells you how many fields still need a value.</li>
          <li><strong>Filter the fields:</strong> Use <em>Required fields</em> to see only the fields you must fill.</li>
          <li><strong>Fill in missing values:</strong> Click a field and type the value, or click the field and drag a box around the text on the document image.</li>
          <li><strong>Check the tables:</strong> Review each table's rows. Add rows with <em>+ Add Row</em> or delete rows with 🗑.</li>
          <li><strong>Submit the page:</strong> Click <em>Submit</em> when all required fields have values.</li>
          <li><strong>Mark a page as invalid:</strong> If the page cannot be corrected, click <em>Mark as Invalid</em> to move to the next page.</li>
        </ul>
      </DocumentationCard>

      {/* Notes */}
      <DocumentationCard 
        title="Notes" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            <strong>Note:</strong> The Submit button stays unavailable until every required field on the page
            has a value. This prevents you from saving incomplete results.
          </p>
        </div>
        <div className="doc-info-panel">
          <p>
            <strong>Tip:</strong> Use the <em>Invalid fields</em> filter to see only the fields that are still
            empty. This makes it faster to fill in the missing information.
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default ValidationDocumentation;