import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { FiX } from "react-icons/fi";
import { useUiStore } from "./uiStore";

/**
 * Secondary navigation column — the DM list, the guild channel list.
 *
 * A permanent column from `lg` up, a slide-over drawer below it. Navigating
 * closes the drawer, because on a phone every link in here leads somewhere
 * that replaces the panel anyway.
 */
export default function SidePanel({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  const { panelOpen, setPanelOpen } = useUiStore();
  const { pathname } = useLocation();

  useEffect(() => {
    setPanelOpen(false);
  }, [pathname, setPanelOpen]);

  useEffect(() => {
    if (!panelOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setPanelOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [panelOpen, setPanelOpen]);

  return (
    <>
      {panelOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink-950/70 backdrop-blur-sm animate-fade-in lg:hidden"
          onClick={() => setPanelOpen(false)}
          role="presentation"
        />
      )}

      <aside
        aria-label={label}
        className={`fixed inset-y-0 left-0 z-40 flex w-[17rem] shrink-0 flex-col border-r border-white/[0.06] bg-ink-900 transition-transform duration-300 ease-out lg:static lg:z-auto lg:w-64 lg:translate-x-0 lg:bg-ink-900/60 ${
          panelOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <button
          onClick={() => setPanelOpen(false)}
          aria-label="Close menu"
          className="absolute right-3 top-3 rounded-lg p-2 text-ink-400 hover:bg-white/5 hover:text-white lg:hidden"
        >
          <FiX size={18} />
        </button>
        {children}
      </aside>
    </>
  );
}
