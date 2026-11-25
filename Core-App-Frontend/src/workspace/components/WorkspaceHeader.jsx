import React from "react";
import "../styles/Header.css";

/**
 * Global Header — used on every page.
 *
 * Props:
 *  title       {string}      – main heading
 *  description {string}      – optional subtitle
 *  actions     {ReactNode}   – buttons / controls rendered on the right
 *
 * Usage example:
 *   <Header
 *     title="Document Processor"
 *     actions={
 *       <>
 *         <button className="btn-secondary-dp" onClick={...}>← Back</button>
 *         <button className="btn-primary-dp"   onClick={...}>Save & Next</button>
 *       </>
 *     }
 *   />
 */
function Header({ title, description, actions }) {
  return (
    <header className="global-header">
      <div className="global-header-left">
        <h1 className="global-header-title">{title}</h1>
        {description && <p className="global-header-desc">{description}</p>}
      </div>

      {actions && (
        <div className="global-header-actions">
          {actions}
        </div>
      )}
    </header>
  );
}

export default Header;