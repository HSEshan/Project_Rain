import Badge from "../shared/Badge";

interface CardProps {
  title: string;
  body?: string;
  icon: React.ReactNode;
  onClick: () => void;
  /** Rendered as a count bubble; hidden when zero or undefined. */
  badge?: number;
}

export default function Card({ title, body, icon, onClick, badge }: CardProps) {
  return (
    <button
      onClick={onClick}
      className="group relative flex items-start gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-rain-400/30 hover:bg-white/[0.05]"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-rain-400/20 to-iris-400/10 text-rain-300 transition-colors group-hover:text-rain-200">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="font-semibold text-white">{title}</span>
          <Badge count={badge} />
        </span>
        {body && (
          <span className="mt-1 block text-sm leading-relaxed text-ink-400">
            {body}
          </span>
        )}
      </span>
    </button>
  );
}
