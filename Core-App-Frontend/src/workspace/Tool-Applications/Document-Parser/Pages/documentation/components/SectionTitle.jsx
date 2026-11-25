import React from "react";
import "../../../Styles/documentation.css";

/**
 * SectionTitle - A reusable section heading component
 * 
 * Props:
 *  title {string} - Section title text
 *  number {string|number} - Optional section number
 */
function SectionTitle({ title, number }) {
  return (
    <div className="doc-section-title">
      {number && <span className="doc-section-number">{number}.</span>}
      <h2>{title}</h2>
    </div>
  );
}

export default SectionTitle;