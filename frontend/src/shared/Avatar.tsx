const SIZES = {
  xs: "h-6 w-6 text-[10px]",
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-14 w-14 text-lg",
  xl: "h-20 w-20 text-2xl",
} as const;

/**
 * Deterministic colour per user, so the same person is the same colour in the
 * member list, the roster and every message they send. Hashing the id rather
 * than the name keeps it stable if a display name ever changes.
 */
const PALETTES = [
  "from-rain-400 to-iris-400",
  "from-emerald-400 to-teal-500",
  "from-amber-400 to-orange-500",
  "from-fuchsia-400 to-purple-500",
  "from-sky-400 to-blue-500",
  "from-rose-400 to-pink-500",
];

function paletteFor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  return PALETTES[Math.abs(hash) % PALETTES.length];
}

export interface AvatarProps {
  name?: string | null;
  /** Hashed for the colour. Falls back to the name when absent. */
  seed?: string;
  size?: keyof typeof SIZES;
  /** Green ring for "in this channel", used by the voice roster. */
  online?: boolean;
  /** Animated ring while someone is talking. */
  speaking?: boolean;
  className?: string;
}

export default function Avatar({
  name,
  seed,
  size = "md",
  online,
  speaking,
  className = "",
}: AvatarProps) {
  const label = (name ?? "?").trim();
  const initial = label.charAt(0).toUpperCase() || "?";

  return (
    <span className={`relative inline-flex shrink-0 ${className}`}>
      {speaking && (
        <span className="absolute inset-0 rounded-full ring-2 ring-emerald-400 animate-pulse-ring" />
      )}
      <span
        className={`inline-flex items-center justify-center rounded-full bg-gradient-to-br font-semibold text-ink-950 ring-1 ring-inset ring-white/20 ${
          paletteFor(seed ?? label)
        } ${SIZES[size]}`}
      >
        {initial}
      </span>
      {online && (
        <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-ink-900 bg-emerald-400" />
      )}
    </span>
  );
}
