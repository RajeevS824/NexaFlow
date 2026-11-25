/**
 * components/Reveal.jsx
 * ------------------------------------------------------------
 * Wraps any content and fades/slides it in the first time it
 * scrolls into view (see hooks/useReveal.js). Used throughout
 * the app for scroll animations: product rows, section
 * headings, the contact form, etc.
 *
 * Props:
 *   - as: element/component to render as the wrapper (default "div")
 *   - delay: ms to hold before animating in - use this to stagger
 *     a group of siblings (e.g. delay={i * 100} in a .map)
 *   - className: merged onto the wrapper alongside the reveal classes
 * ------------------------------------------------------------
 */

import useReveal from "../hooks/useReveal.js";

export default function Reveal({ as: Tag = "div", delay = 0, className = "", children, ...rest }) {
  const [ref, isVisible] = useReveal();

  return (
    <Tag
      ref={ref}
      className={`reveal ${isVisible ? "reveal-visible" : ""} ${className}`}
      style={{ transitionDelay: isVisible ? `${delay}ms` : "0ms" }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
