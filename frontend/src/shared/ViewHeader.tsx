import { FiMenu } from "react-icons/fi";
import ConnectionDot from "./ConnectionDot";
import { useUiStore } from "./uiStore";

/**
 * Header strip for a main view. Owns the only control that opens the side
 * panel on small screens, so no view has to think about the drawer.
 */
export default function ViewHeader({
  icon,
  title,
  subtitle,
  actions,
}: {
  icon?: React.ReactNode;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  const setPanelOpen = useUiStore((state) => state.setPanelOpen);

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-white/[0.06] bg-ink-900/40 px-3 backdrop-blur sm:px-5">
      <button
        onClick={() => setPanelOpen(true)}
        aria-label="Open menu"
        className="-ml-1 rounded-lg p-2 text-ink-300 transition-colors hover:bg-white/5 hover:text-white lg:hidden"
      >
        <FiMenu size={18} />
      </button>

      {icon && <span className="shrink-0 text-ink-400">{icon}</span>}

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[15px] font-semibold text-white">
          {title}
        </h1>
        {subtitle && (
          <p className="truncate text-xs text-ink-400">{subtitle}</p>
        )}
      </div>

      {/* The rail carries this on desktop; on mobile the rail is a bottom bar
          with no room for it, so it lives here instead. */}
      <ConnectionDot className="shrink-0 lg:hidden" />

      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}
