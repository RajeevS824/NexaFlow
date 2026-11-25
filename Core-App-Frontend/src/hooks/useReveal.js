/**
 * hooks/useReveal.js
 * ------------------------------------------------------------
 * Tiny IntersectionObserver hook: returns a ref to attach to any
 * element, plus a boolean that flips to true the first time that
 * element scrolls into the viewport. Powers every scroll-reveal
 * animation in the app (see components/Reveal.jsx) without
 * pulling in an animation library.
 *
 * Fires once and disconnects — reveals aren't meant to replay
 * every time the user scrolls back up past a section.
 * ------------------------------------------------------------
 */

import { useEffect, useRef, useState } from "react";

export default function useReveal({ threshold = 0.15, rootMargin = "0px 0px -60px 0px" } = {}) {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    // Respect reduced-motion preference: show immediately, no observer needed.
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  return [ref, isVisible];
}
