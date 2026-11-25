import React from "react";
import DocumentationCard from "../components/DocumentationCard";
import { FaQuestionCircle, FaInfoCircle, FaStar } from "react-icons/fa";
import "../../../Styles/documentation.css";

function FAQ() {
  const faqs = [
    {
      question: "What is a process model?",
      answer: "A process model tells the system what kind of document to read and which information to extract. You create a model on the Create Process Model page, define its fields on the Create Process Fields page, and then use it to process documents."
    },
    {
      question: "What is the difference between OCR and LLM?",
      answer: "OCR reads the text directly from the document image. LLM uses a language model to understand the document content. You can choose either one when you create a model."
    },
    {
      question: "What document formats can I process?",
      answer: "You can process PDF files and image files including JPG, JPEG, PNG, TIFF, and BMP."
    },
    {
      question: "Where are my processing results saved?",
      answer: "The results are saved as CSV files in the Output Folder you enter on the Document Processing page before you start processing."
    },
    {
      question: "Why is a required field still empty after processing?",
      answer: "Sometimes the system cannot find the information on the document. You can fill the field by clicking on it and typing the value, or by clicking the field and dragging a box around the text on the document image in the Extraction Results tab."
    },
    {
      question: "Why is the Submit button unavailable?",
      answer: "The Submit button stays unavailable until every required field on the current page has a value. Check the fields marked with the red border and fill them in first."
    },
    {
      question: "What does 'Mark as Invalid' do?",
      answer: "It marks the current page as invalid and moves to the next page. Use it when the document page is unreadable or the extracted information is wrong and cannot be corrected."
    },
    {
      question: "How do I reprocess a failed document?",
      answer: "Open the History Extraction Model page, find the document with the Failed or Cancelled status, and click the Reprocess button. Choose the original file again and process it."
    },
    {
      question: "Can I edit a model after creating it?",
      answer: "Yes. Open the Document Process Model page, find your model, and click the Edit button. The system opens the model in edit mode where you can change its settings and fields."
    },
    {
      question: "Can I delete a model?",
      answer: "Yes. Open the Document Process Model page, find your model, and click the Delete button. The system asks you to confirm. If the model has processed documents, all of that processing data is also deleted permanently."
    },
    {
      question: "Why can't I process a document with a model?",
      answer: "A model can only be used for processing after it has at least one form field or one table. If you see the message 'Please create at least one Form Field or one Table before processing', go back to the Create Process Fields page and add fields first."
    },
    {
      question: "What happens if I close the processing page while it is processing?",
      answer: "The processing job is cancelled. You can find the document in the History Extraction Model page with the status Cancelled or Failed, and use the Reprocess button to try again."
    },
    {
      question: "Why is the Process Document shortcut on the Dashboard unavailable?",
      answer: "The Process Document and History shortcuts only become available after you create at least one process model. If there are no models yet, create one first."
    },
    {
      question: "What is STP on the Dashboard?",
      answer: "STP (Straight-Through Processing) is a percentage that shows how many documents were completed automatically without needing manual help during validation."
    },
    {
      question: "How do I change the language of a model?",
      answer: "Edit the model from the Document Process Model page. On the Create Process Model form, choose the language from the Language dropdown, then click Next and Save & Close."
    }
  ];

  return (
    <div className="doc-page">
      
     

      {faqs.map((faq, index) => (
        <DocumentationCard 
          key={index}
          title={faq.question}
          icon={<FaInfoCircle />}
        >
          <p>{faq.answer}</p>
        </DocumentationCard>
      ))}

      <DocumentationCard 
        title="Still Need Help?" 
        icon={<FaStar />}
      >
        <p>
          If you did not find the answer to your question, try the <strong>Troubleshooting</strong> page
          for help with common errors, or contact your system administrator for help with your specific situation.
        </p>
      </DocumentationCard>
    </div>
  );
}

export default FAQ;