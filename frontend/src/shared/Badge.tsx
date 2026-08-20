/** Count bubble. Renders nothing at zero so callers can pass a raw length. */
export default function Badge({
  count,
  className = "",
}: {
  count?: number;
  className?: string;
}) {
  if (!count) return null;
  return (
    <span
      className={`inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-rain-400 px-1.5 text-[11px] font-bold text-ink-950 shadow-[0_0_12px_rgba(34,211,238,0.5)] ${className}`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}
