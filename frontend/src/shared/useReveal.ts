import { useEffect, useRef, useState } from "react";

/**
 * Reveal-on-scroll without a library. Unobserves after the first intersection —
 * the animation is a one-shot, and re-triggering it on every scroll past is the
 * thing that makes this pattern feel cheap.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T | null>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return { ref, shown };
}
