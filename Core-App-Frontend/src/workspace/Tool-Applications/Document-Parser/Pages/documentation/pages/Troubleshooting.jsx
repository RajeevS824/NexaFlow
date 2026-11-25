import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import { FaWrench, FaCheckCircle, FaStickyNote } from "react-icons/fa";
import "../../../Styles/documentation.css";

function Troubleshooting() {
  const issues = [
    {
      problem: "I cannot create a model because \u201CModel Name is required\u201D is shown.",
      solution: "Enter a model name in the Model Name field. The name must be between 3 and 30 characters and can only contain letters, numbers, spaces, underscores (_) and hyphens (-)."
    },
    {
      problem: "I see \u201CAlready model created. Type another name.\u201D",
      solution: "A model with the same name already exists. Type a different model name and try again."
    },
    {
      problem: "The Process button on a model is unavailable.",
      solution: "A model must have at least one form field or one table before it can be processed. Open the model in edit mode, go to the Create Process Fields page, and add at least one field or table."
    },
    {
      problem: "The Process Document shortcut on the Dashboard is unavailable.",
      solution: "The Process Document and History shortcuts become available only after you create at least one process model. Create a model first."
    },
    {
      problem: "I clicked Process but nothing happened.",
      solution: "The processing page opens in a new tab. Your browser may be blocking popups. Allow popup permission for this site and click Process again."
    },
    {
      problem: "I see \u201CFile format not supported.\u201D",
      solution: "Only PDF and image files (JPG, JPEG, PNG, TIFF, BMP) can be processed. Choose a file in one of these formats."
    },
    {
      problem: "I see \u201CPlease enter a valid output folder path.\u201D",
      solution: "Enter the full folder path where you want the results to be saved in the Output Folder box. For example, C:\\Exports on Windows or /home/user/exports on another system."
    },
    {
      problem: "A required field is empty and I cannot Submit.",
      solution: "Click inside the empty field, then drag a box around the correct text on the document image in the Extraction Results tab. You can also type the value directly into the field."
    },
    {
      problem: "I see \u201CSelect input field first\u201D when I try to drag on the document.",
      solution: "You must click inside the field in the right panel first, and then drag a box on the document image. The field becomes active after you click it."
    },
    {
      problem: "The Submit button stays greyed out.",
      solution: "The Submit button becomes available only when every required field on the current page has a value. Fill in all the fields marked as required, and then Submit will become available."
    },
    {
      problem: "I see \u201CNo data available yet\u201D on the Dashboard charts.",
      solution: "This message means there are no processed documents yet. After you process at least one document, the charts will show the data."
    },
    {
      problem: "I see \u201CNo extraction models found.\u201D on the Document Process Model page.",
      solution: "This message means you have not created any models yet. Click the + Create button to create your first model."
    },
    {
      problem: "I see \u201CNo history found\u201D on the History Extraction Model page.",
      solution: "This message means no documents have been processed yet. After you process a document, it will appear in the history list."
    },
    {
      problem: "A document has the status Failed or Cancelled in the history.",
      solution: "Click the Reprocess button for that document. The system will ask you to confirm, then take you to the processing page where you can choose the original file and try again."
    },
    {
      problem: "The document processing was interrupted because the browser tab was closed.",
      solution: "Go to the History Extraction Model page, find the document with the Cancelled or Failed status, and click Reprocess. Choose the original file and process it again."
    },
    {
      problem: "I see \u201CUnable to load extraction models.\u201D",
      solution: "The system could not load your models. This is usually a temporary problem. Refresh the page and try again. If the problem continues, contact your system administrator."
    },
    {
      problem: "I see \u201CDelete Error\u201D when trying to delete a model.",
      solution: "The model could not be deleted. This can happen if the system is busy. Try again. If the problem continues, contact your system administrator."
    },
    {
      problem: "The page shows \u201CMarked as Invalid\u201D and returns to the models page.",
      solution: "This happens after you mark the last page of a document as invalid. The system saves the results and returns you to the Document Process Model page."
    }
  ];

  return (
    <div className="doc-page">
    



      {issues.map((issue, index) => (
        <DocumentationCard 
          key={index}
          title={issue.problem}
          icon={<FaCheckCircle />}
        >
          <p><strong>Solution:</strong> {issue.solution}</p>
        </DocumentationCard>
      ))}

      <DocumentationCard 
        title="Still Not Working?" 
        icon={<FaStickyNote />}
      >
        <div className="doc-note-panel">
          <p>
            If none of these solutions help, contact your system administrator. Include the details of what
            you were doing when the problem occurred, the document name, and the model name.
          </p>
        </div>
      </DocumentationCard>
    </div>
  );
}

export default Troubleshooting;