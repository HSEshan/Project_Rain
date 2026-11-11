import { useEffect, useMemo, useRef, useState } from "react";
import { FiSmile } from "react-icons/fi";
import { ALL_EMOJI, EMOJI_CATEGORIES, type EmojiEntry } from "./emoji";

/**
 * The composer's emoji button and its popover.
 *
 * Picking inserts at the caret and leaves the popover open, so several can go in
 * one after another; Escape or a click outside closes it. Recently used emoji are
 * kept in `localStorage`: which ones a person reaches for is a habit of theirs on
 * this device, not account data, the same reasoning as the voice volume settings.
 */

const RECENT_KEY = "rain.emoji.recent";
/** Search bar, the h-64 grid and the category bar, roughly. */
const POPOVER_HEIGHT_PX = 340;
const RECENT_LIMIT = 16;

function readRecent(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
    // Rebuilt rather than trusted, like every hand-editable store input
    return Array.isArray(stored)
      ? stored.filter((value): value is string => typeof value === "string").slice(0, RECENT_LIMIT)
      : [];
  } catch {
    return [];
  }
}

function rememberRecent(char: string): string[] {
  const next = [char, ...readRecent().filter((value) => value !== char)].slice(0, RECENT_LIMIT);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // Private mode or full storage: the pick still works, it just is not remembered
  }
  return next;
}

/**
 * Whether there is room above the button, measured against whatever clips the
 * popover: the nearest scrolling ancestor (the message list, for the editor) or
 * else the window. Opens below only when above is too short and below is roomier.
 */
function opensBelow(anchor: HTMLElement): boolean {
  let clip: HTMLElement | null = anchor.parentElement;
  while (clip && !/(auto|scroll|hidden)/.test(getComputedStyle(clip).overflowY)) {
    clip = clip.parentElement;
  }
  const bounds = clip
    ? clip.getBoundingClientRect()
    : { top: 0, bottom: window.innerHeight };
  const rect = anchor.getBoundingClientRect();
  const above = rect.top - bounds.top;
  const below = bounds.bottom - rect.bottom;
  return above < POPOVER_HEIGHT_PX && below > above;
}

const NAMES = new Map(ALL_EMOJI.map((entry) => [entry.char, entry.names]));

type Props = {
  onPick: (emoji: string) => void;
  disabled?: boolean;
};

export default function EmojiPicker({ onPick, disabled }: Props) {
  const [open, setOpen] = useState(false);
  // Upwards by default, which suits the composer at the bottom of the screen.
  // Downwards when there is not room above, which is the message editor on a
  // message near the top of the list, where upwards would go under the header.
  const [below, setBelow] = useState(false);
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<string[]>(readRecent);
  const container = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    // Search is where a keyboard user starts. Not on touch screens, where it
    // would pull up the keyboard over the grid they opened this to see.
    if (window.matchMedia("(pointer: fine)").matches) searchRef.current?.focus();
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const results = useMemo(() => {
    const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (words.length === 0) return null;
    return ALL_EMOJI.filter((entry) =>
      words.every((word) => entry.names.split(" ").some((name) => name.startsWith(word)))
    );
  }, [query]);

  const pick = (char: string) => {
    onPick(char);
    setRecent(rememberRecent(char));
  };

  const pickFirstResult = () => {
    if (results && results.length > 0) pick(results[0].char);
  };

  const recentEntries: EmojiEntry[] = recent.map((char) => ({
    char,
    names: NAMES.get(char) ?? "",
  }));

  return (
    // Not `relative`: the popover positions against the composer box around
    // this, so it lines up with the composer's left edge. Anchored to the
    // button, which sits a button's width in, it ran off a phone screen.
    <div ref={container} className="shrink-0">
      <button
        type="button"
        onClick={() => {
          if (container.current) setBelow(opensBelow(container.current));
          setOpen((wasOpen) => !wasOpen);
        }}
        disabled={disabled}
        aria-label="Emoji"
        title="Emoji"
        aria-expanded={open}
        className={`flex h-9 w-9 items-center justify-center rounded-xl transition-colors disabled:opacity-40 ${
          open ? "bg-white/[0.08] text-white" : "text-ink-300 hover:bg-white/5 hover:text-white"
        }`}
      >
        <FiSmile size={17} />
      </button>

      {open && (
        <div
          // Opens upwards from the composer's left edge, never wider than the
          // composer itself, so it fits a phone screen.
          className={`glass absolute left-0 z-30 flex w-full max-w-[20rem] ${
            below ? "top-full mt-2" : "bottom-full mb-2"
          } flex-col rounded-2xl border-white/10 bg-ink-850/95 shadow-lift animate-scale-in`}
          role="dialog"
          aria-label="Emoji"
        >
          <div className="border-b border-white/[0.07] p-2.5">
            <input
              ref={searchRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  pickFirstResult();
                }
              }}
              placeholder="Search emoji"
              aria-label="Search emoji"
              className="w-full rounded-lg border border-white/[0.07] bg-ink-950/60 px-3 py-1.5 text-sm text-white placeholder-ink-500 focus:border-rain-400/50 focus:outline-none"
            />
          </div>

          <div className="h-64 overflow-y-auto overscroll-contain px-2 pb-2">
            {results ? (
              results.length > 0 ? (
                <EmojiGrid entries={results} onPick={pick} />
              ) : (
                <p className="px-2 py-8 text-center text-sm text-ink-400">
                  No emoji match "{query.trim()}"
                </p>
              )
            ) : (
              <>
                {recentEntries.length > 0 && (
                  <Section label="Recent">
                    <EmojiGrid entries={recentEntries} onPick={pick} />
                  </Section>
                )}
                {EMOJI_CATEGORIES.map((category) => (
                  <div
                    key={category.id}
                    ref={(node) => {
                      sectionRefs.current[category.id] = node;
                    }}
                  >
                    <Section label={category.label}>
                      <EmojiGrid entries={category.emoji} onPick={pick} />
                    </Section>
                  </div>
                ))}
              </>
            )}
          </div>

          {!results && (
            <div className="flex justify-between border-t border-white/[0.07] px-2 py-1.5">
              {EMOJI_CATEGORIES.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() =>
                    sectionRefs.current[category.id]?.scrollIntoView({ block: "start" })
                  }
                  aria-label={category.label}
                  title={category.label}
                  className="rounded-lg px-1.5 py-1 text-base leading-none grayscale transition hover:bg-white/5 hover:grayscale-0"
                >
                  {category.icon}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="sticky top-0 z-10 bg-ink-850/95 px-1.5 pb-1 pt-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
        {label}
      </p>
      {children}
    </div>
  );
}

function EmojiGrid({
  entries,
  onPick,
}: {
  entries: EmojiEntry[];
  onPick: (char: string) => void;
}) {
  return (
    <div className="grid grid-cols-8 gap-0.5">
      {entries.map((entry) => (
        <button
          key={entry.char}
          type="button"
          onClick={() => onPick(entry.char)}
          title={entry.names.split(" ")[0]}
          aria-label={entry.names.split(" ")[0]}
          className="flex aspect-square items-center justify-center rounded-lg text-xl leading-none transition-colors hover:bg-white/[0.08]"
        >
          {entry.char}
        </button>
      ))}
    </div>
  );
}
