/**
 * Core stack, shown in the hero rather than further down the page: it is the
 * first thing a technical reader looks for, and it should not need a scroll.
 * Kept to the parts that describe the system, not every library in the tree.
 */
const STACK = [
  "React",
  "TypeScript",
  "Tailwind",
  "FastAPI",
  "PostgreSQL",
  "Redis",
  "LiveKit",
  "Docker",
];

export default function TechStack() {
  return (
    <div className="flex flex-col items-center gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-400">
        Built with
      </span>
      <ul className="flex flex-wrap justify-center gap-2">
        {STACK.map((tech) => (
          <li
            key={tech}
            className="rounded-full border border-white/[0.07] bg-white/[0.03] px-3 py-1.5 font-mono text-[11px] text-ink-300"
          >
            {tech}
          </li>
        ))}
      </ul>
    </div>
  );
}
