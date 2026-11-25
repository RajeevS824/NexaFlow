import React from "react";
import "../../../Styles/documentation.css";

/** Card with icon + title — one block of a documentation page. */
export function DocumentationCard({ title, icon, children }) {
  return (
    <div className="bm-doc-card">
      {(title || icon) && (
        <div className="bm-doc-card-header">
          {icon && <div className="bm-doc-card-icon">{icon}</div>}
          {title && <h3 className="bm-doc-card-title">{title}</h3>}
        </div>
      )}
      <div className="bm-doc-card-body">{children}</div>
    </div>
  );
}

/** Horizontal step diagram (wraps / stacks on small screens). */
export function WorkflowCard({ steps }) {
  return (
    <div className="bm-doc-workflow">
      <div className="bm-doc-workflow-steps">
        {steps.map((step, i) => (
          <React.Fragment key={step}>
            <div className="bm-doc-workflow-step">
              <div className="bm-doc-workflow-step-number">{i + 1}</div>
              <div className="bm-doc-workflow-step-text">{step}</div>
            </div>
            {i < steps.length - 1 && <div className="bm-doc-workflow-arrow" aria-hidden="true">→</div>}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

/** Simple table: columns = ["A","B"], rows = [["a1","b1"], ...] (cells may be JSX). */
export function DocTable({ columns, rows }) {
  return (
    <div className="bm-doc-table-wrap">
      <table className="bm-doc-table">
        <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DocList({ items }) {
  return (
    <ul className="bm-doc-list">
      {items.map((it, i) => <li key={i}>{it}</li>)}
    </ul>
  );
}

export function InfoPanel({ children }) {
  return <div className="bm-doc-info-panel"><p>{children}</p></div>;
}

export function NotePanel({ children }) {
  return <div className="bm-doc-note-panel"><p>{children}</p></div>;
}

/** Figure frame for the illustrations drawn from the real screen structure. */
export function Figure({ caption, children }) {
  return (
    <figure className="bm-doc-figure">
      <div className="bm-doc-figure-frame">{children}</div>
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
