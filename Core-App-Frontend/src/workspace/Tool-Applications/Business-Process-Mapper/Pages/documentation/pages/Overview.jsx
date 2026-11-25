import React from "react";
import { useNavigate } from "react-router-dom";
import { FaTachometerAlt, FaMapSigns, FaStream, FaCog, FaQuestionCircle, FaWrench } from "react-icons/fa";
import { useBasePath } from "../../../../../utils/useBasePath";
import { DocumentationCard, DocList } from "../components/DocComponents";
import "../../../Styles/documentation.css";

const SECTIONS = [
  { title: "Dashboard", path: "/dashboard", icon: <FaTachometerAlt />, description: "The six statistic cards, the three charts and the Recent Files table that summarise your processing activity." },
  { title: "Business Flow", path: "/business-flow", icon: <FaMapSigns />, description: "Upload a video (and optional audio), start the pipeline, follow progress, cancel, and download the generated documents." },
  { title: "Processing Pipeline", path: "/pipeline", icon: <FaStream />, description: "What happens in each stage: Upload → Validate → Process → Generate → Complete." },
  { title: "Settings", path: "/settings", icon: <FaCog />, description: "Logging, upload size limits and LLM credentials for Business Map." },
  { title: "FAQ", path: "/faq", icon: <FaQuestionCircle />, description: "Answers to common questions about uploads, audio, cancelling and logout." },
  { title: "Troubleshooting", path: "/troubleshooting", icon: <FaWrench />, description: "What to do when an upload is rejected, a job fails, or the dashboard looks empty." },
];

export default function Overview() {
  const navigate = useNavigate();
  const basePath = useBasePath();
  const docsBase = `${basePath}/BusinessMap/documentation`;

  return (
    <div className="bm-doc-home">
      <DocumentationCard title="About Business Map Process">
        <p>
          Business Map Process turns a screen-recording of a business process into structured documents. You upload a
          video (and, optionally, a separate audio file); the application transcribes the narration, analyses the
          video frames, and uses a language model to generate a <strong>Workflow Steps</strong> document and a
          <strong> Manual Validation</strong> document that you can download.
        </p>
        <p>The application has two pages. Use the sidebar to switch between them; the header shows the name of the page you are on:</p>
        <DocList items={[
          <><strong>Dashboard</strong> — an overview of everything you have uploaded and how it went.</>,
          <><strong>Business Flow</strong> — where you upload files and run the pipeline.</>,
        ]} />
        <p>
          The top-right corner of every page has three buttons: <strong>Notifications</strong> (bell),
          <strong> Home</strong> and your <strong>Profile</strong>. The sidebar has <strong>Documentation</strong> and
          <strong> Logout</strong> at the bottom. Logging out cancels any of your jobs that are still processing.
        </p>
      </DocumentationCard>

      <div className="bm-doc-sections-grid">
        {SECTIONS.map((s) => (
          <div key={s.path} className="bm-doc-section-card" onClick={() => navigate(`${docsBase}${s.path}`)}>
            <div className="bm-doc-section-card-icon">{s.icon}</div>
            <h3 className="bm-doc-section-card-title">{s.title}</h3>
            <p className="bm-doc-section-card-desc">{s.description}</p>
            <div className="bm-doc-section-card-link">Learn More →</div>
          </div>
        ))}
      </div>
    </div>
  );
}
