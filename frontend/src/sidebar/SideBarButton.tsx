import { Link } from "react-router-dom";
import Badge from "../shared/Badge";

export interface SideBarButtonProps {
  to?: string;
  children?: React.ReactNode;
  label: string;
  onClick?: () => void;
  active?: boolean;
  badge?: number;
  /** Danger styling for destructive actions like logout. */
  destructive?: boolean;
}

/**
 * One rail destination. Renders a Link when it navigates and a button when it
 * acts — a `Link to=""` would navigate to the current route and race whatever
 * the click handler is doing.
 */
export default function SideBarButton({
  to,
  children,
  label,
  onClick,
  active,
  badge,
  destructive,
}: SideBarButtonProps) {
  const className = `group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all duration-200 ${
    active
      ? "bg-gradient-to-br from-rain-400/20 to-iris-400/10 text-rain-300 ring-1 ring-inset ring-rain-400/30"
      : destructive
      ? "text-ink-400 hover:bg-red-500/10 hover:text-red-300"
      : "text-ink-400 hover:bg-white/[0.07] hover:text-white"
  }`;

  const inner = (
    <>
      {children}
      {!!badge && (
        <Badge count={badge} className="absolute -right-1 -top-1" />
      )}
      {/* Active pill on the rail edge, the way Discord marks the current server */}
      <span
        className={`absolute -left-2 h-5 w-1 rounded-r-full bg-rain-400 transition-all duration-200 ${
          active ? "opacity-100" : "opacity-0 group-hover:opacity-40"
        }`}
      />
      {/* Tooltip. Pointer-events-none so it never eats the click. */}
      <span className="pointer-events-none absolute left-full z-50 ml-3 hidden whitespace-nowrap rounded-lg border border-white/10 bg-ink-800 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-lift transition-opacity duration-150 group-hover:opacity-100 lg:block">
        {label}
      </span>
    </>
  );

  return to ? (
    <Link to={to} className={className} aria-label={label} onClick={onClick}>
      {inner}
    </Link>
  ) : (
    <button
      type="button"
      onClick={onClick}
      className={className}
      aria-label={label}
    >
      {inner}
    </button>
  );
}
