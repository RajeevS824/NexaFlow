/**
 * components/RequestDemoLink.jsx
 * ------------------------------------------------------------
 * Every "Request demo" / "Request a demo" call-to-action on the site
 * uses this link. It behaves exactly like the header's "Contact us":
 * it takes the visitor to the Contact section on the Home page and
 * scrolls to it (Home.jsx does the scroll on arrival, from any page).
 *
 * It also passes { demo: true } in the navigation state so the Contact
 * section can pre-fill a demo-request message and send the form to the
 * "request a demo" endpoint instead of the generic contact one.
 *
 * Renders a normal <a href="/#contact">, so open-in-new-tab and
 * copy-link still work; plain clicks are handled client-side.
 * ------------------------------------------------------------
 */
import { useNavigate } from "react-router-dom";

export default function RequestDemoLink({ children, onClick, ...rest }) {
  const navigate = useNavigate();

  function handleClick(e) {
    onClick?.(e);
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate("/#contact", { state: { demo: true } });
  }

  return (
    <a href="/#contact" onClick={handleClick} {...rest}>
      {children}
    </a>
  );
}
