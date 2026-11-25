import React from "react";
import { useNavigate } from "react-router-dom";
import { useBasePath } from "../../../../../utils/useBasePath";
import { FaHome, FaPlusSquare, FaListUl, FaCog, FaFileImport, FaHistory, FaSearch, FaCheckCircle, FaQuestionCircle, FaWrench } from "react-icons/fa";
import "../../../Styles/documentation.css";


function Overview() {
  const navigate = useNavigate();
  const basePath = useBasePath();
  const docsBase = `${basePath}/document-parser/documentation`;

  const docSections = [
    {
      title: "Dashboard",
      description: "Learn about the Document Parser dashboard, its statistics, charts, and quick actions.",
      icon: <FaHome />,
      path: "/dashboard",
    },
    {
      title: "Create Process Model",
      description: "Understand how to create and configure a new process model for extracting information from documents.",
      icon: <FaPlusSquare />,
      path: "/create-process-model",
    },
    {
      title: "Create Process Fields",
      description: "Detailed guide on defining the information fields and tables your model will extract from documents.",
      icon: <FaListUl />,
      path: "/create-process-fields",
    },
    {
      title: "Document Process Model",
      description: "Learn how to view, edit, process, and delete your saved process models.",
      icon: <FaCog />,
      path: "/document-process-model",
    },
    {
      title: "Document Processing",
      description: "Complete guide to uploading a document, choosing an output folder, and processing it using a model.",
      icon: <FaFileImport />,
      path: "/document-processing",
    },
    {
      title: "History Extraction Model",
      description: "View the history of all processed documents, their status, output location, and available actions.",
      icon: <FaHistory />,
      path: "/history",
    },
    {
      title: "Validation",
      description: "Understand how the validation panel helps you check and fill in required information before saving.",
      icon: <FaCheckCircle />,
      path: "/validation",
    },
    {
      title: "FAQ",
      description: "Answers to common questions about using the Document Parser module.",
      icon: <FaQuestionCircle />,
      path: "/faq",
    },
    {
      title: "Troubleshooting",
      description: "Help with common issues and error messages you may encounter.",
      icon: <FaWrench />,
      path: "/troubleshooting",
    },
  ];

  return (
    <div className="doc-home">
      <div className="doc-sections-grid">
        {docSections.map((section, index) => (
          <div
            key={index}
            className="doc-section-card"
            onClick={() => navigate(`${docsBase}${section.path}`)}
          >
            <div className="doc-section-card-icon">{section.icon}</div>
            <h3 className="doc-section-card-title">{section.title}</h3>
            <p className="doc-section-card-desc">{section.description}</p>
            <div className="doc-section-card-link">
              Learn More →
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Overview;