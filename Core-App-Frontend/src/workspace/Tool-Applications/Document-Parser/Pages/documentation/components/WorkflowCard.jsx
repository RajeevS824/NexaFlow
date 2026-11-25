import React from "react";
import "../../../Styles/documentation.css";

/**
 * WorkflowCard - Displays a visual workflow diagram
 * 
 * Props:
 *  steps {Array} - Array of workflow step strings
 */
function WorkflowCard({ steps }) {
  return (
    <div className="doc-workflow">
      <div className="doc-workflow-steps">
        {steps.map((step, index) => (
          <React.Fragment key={index}>
            <div className="doc-workflow-step">
              <div className="doc-workflow-step-number">{index + 1}</div>
              <div className="doc-workflow-step-text">{step}</div>
            </div>
            {index < steps.length - 1 && (
              <div className="doc-workflow-arrow">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 4L12 20M12 20L6 14M12 20L18 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

export default WorkflowCard;