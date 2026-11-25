import React from "react";
import "../../../Styles/documentation.css";

/**
 * DocumentationCard - A reusable card component for documentation sections
 * 
 * Props:
 *  title   {string}  - Section title
 *  icon    {ReactNode} - Optional icon to display
 *  children {ReactNode} - Card content
 */
function DocumentationCard({ title, icon, children }) {
  return (
    <div className="doc-card">
      {(title || icon) && (
        <div className="doc-card-header">
          {icon && <div className="doc-card-icon">{icon}</div>}
          {title && <h3 className="doc-card-title">{title}</h3>}
        </div>
      )}
      <div className="doc-card-body">
        {children}
      </div>
    </div>
  );
}

export default DocumentationCard;