import { useEffect, useState } from "react";

/**
 * Tailwind's `lg` breakpoint in JS. Layout that only needs CSS should stay in
 * CSS; this exists for the cases where behaviour changes too, like closing a
 * navigation drawer once it becomes a permanent sidebar.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches
  );

  useEffect(() => {
    const list = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(list.matches);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

export const useIsDesktop = () => useMediaQuery("(min-width: 1024px)");
