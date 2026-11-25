import React, { useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal — a true modal dialog wrapper:
 *   - Locks background scroll while open.
 *   - Blocks all interaction with everything behind it (the overlay
 *     intercepts clicks; it does NOT close the modal, since these dialogs
 *     require an explicit button choice).
 *   - Traps keyboard focus inside the modal (Tab / Shift+Tab cycle only
 *     between focusable elements inside it).
 *   - Restores focus to whatever element opened the modal, once it closes.
 *
 * Props:
 *   open        {boolean}   – whether the modal is visible
 *   onClose     {function}  – optional, called on Escape key (omit to
 *                              disable Escape-to-close for dialogs that
 *                              require an explicit choice)
 *   labelledBy  {string}    – id of the element that labels the dialog
 *   children    {ReactNode}
 */
export default function Modal({ open, onClose, labelledBy, children }) {
  const overlayRef = useRef(null);
  const dialogRef = useRef(null);
  const previouslyFocusedRef = useRef(null);

  // ── Scroll lock + focus trap setup/teardown ──
  useEffect(() => {
    if (!open) return;

    previouslyFocusedRef.current = document.activeElement;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Focus the first focusable element inside the dialog (fall back to
    // the dialog itself so Tab has somewhere sane to start from).
    const focusables = dialogRef.current?.querySelectorAll(FOCUSABLE_SELECTOR);
    if (focusables && focusables.length > 0) {
      focusables[0].focus();
    } else {
      dialogRef.current?.focus();
    }

    function handleKeyDown(e) {
      if (e.key === "Escape" && onClose) {
        onClose();
        return;
      }

      if (e.key !== "Tab") return;

      const nodes = dialogRef.current?.querySelectorAll(FOCUSABLE_SELECTOR);
      if (!nodes || nodes.length === 0) {
        e.preventDefault();
        return;
      }

      const first = nodes[0];
      const last = nodes[nodes.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first || !dialogRef.current.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !dialogRef.current.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      document.body.style.overflow = previousOverflow;
      // Restore focus to whatever opened the modal.
      previouslyFocusedRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="bm-modal-overlay"
      role="presentation"
      // Background must stay completely inert — no click-through, no
      // close-on-backdrop-click, since these dialogs need an explicit
      // button choice.
      onClick={(e) => e.stopPropagation()}
      onWheel={(e) => e.preventDefault()}
      onTouchMove={(e) => e.preventDefault()}
    >
      <div
        ref={dialogRef}
        className="bm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>
  );
}
