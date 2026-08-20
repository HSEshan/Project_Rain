import { useReveal } from "../shared/useReveal";

/**
 * Fades a section up the first time it enters the viewport. `delay` staggers
 * siblings; anything above the fold should skip this and animate immediately.
 *
 * The classes are written out rather than interpolated: Tailwind purges custom
 * utilities it cannot find as literal strings in the source, so a template
 * like `delay-${n}` silently produces no delay in a production build.
 */
const DELAYS = {
  0: "",
  70: "delay-70",
  140: "delay-140",
  210: "delay-210",
  280: "delay-280",
} as const;

export default function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  delay?: keyof typeof DELAYS;
  className?: string;
}) {
  const { ref, shown } = useReveal<HTMLDivElement>();

  return (
    <div
      ref={ref}
      className={`${
        shown ? `animate-fade-up ${DELAYS[delay]}` : "opacity-0"
      } ${className}`}
    >
      {children}
    </div>
  );
}
