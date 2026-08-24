import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FiX } from "react-icons/fi";
import { Button } from "../shared/Button";
import { useGuildStore } from "../guild/guildStore";
import { useUiStore } from "../shared/uiStore";
import { TOUR_STEPS } from "./steps";
import { TOUR_STEP_COUNT, useTourStore } from "./tourStore";

/** Breathing room between the spotlight and the element it is highlighting. */
const HOLE_PADDING = 8;
const CARD_WIDTH = 330;
const GAP = 14;
/** How long to wait for a target to appear before giving up on the step. */
const TARGET_TIMEOUT_MS = 1500;

type Rect = { top: number; left: number; width: number; height: number };

function readRect(target: string): Rect | null {
  const node = document.querySelector<HTMLElement>(`[data-tour="${target}"]`);
  if (!node) return null;
  const rect = node.getBoundingClientRect();
  // A drawer that is translated off-screen still has a size, so "is it
  // visible" has to mean "is it actually within the viewport"
  if (rect.width === 0 || rect.height === 0) return null;
  if (rect.right <= 0 || rect.left >= window.innerWidth) return null;
  return {
    top: rect.top,
    left: rect.left,
    width: rect.width,
    height: rect.height,
  };
}

/**
 * Place the card beside the hole, flipping to whichever side actually has room.
 *
 * The preferred side is a hint, not a promise: the same step points at a rail
 * button on a desktop and at a bottom-bar button on a phone, and those want
 * opposite placements.
 */
function placeCard(
  hole: Rect,
  cardHeight: number,
  preferred: string | undefined
): { top: number; left: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = Math.min(CARD_WIDTH, vw - 2 * GAP);

  const fits = {
    right: hole.left + hole.width + GAP + width <= vw,
    left: hole.left - GAP - width >= 0,
    top: hole.top - GAP - cardHeight >= 0,
    bottom: hole.top + hole.height + GAP + cardHeight <= vh,
  };

  const order = [preferred, "right", "bottom", "top", "left"].filter(
    Boolean
  ) as Array<keyof typeof fits>;
  const side = order.find((candidate) => fits[candidate]) ?? "bottom";

  let top: number;
  let left: number;

  if (side === "right" || side === "left") {
    left =
      side === "right"
        ? hole.left + hole.width + GAP
        : hole.left - GAP - width;
    top = hole.top + hole.height / 2 - cardHeight / 2;
  } else {
    top =
      side === "bottom" ? hole.top + hole.height + GAP : hole.top - GAP - cardHeight;
    left = hole.left + hole.width / 2 - width / 2;
  }

  // Never let the card hang off the edge, whichever side won
  return {
    top: Math.max(GAP, Math.min(top, vh - cardHeight - GAP)),
    left: Math.max(GAP, Math.min(left, vw - width - GAP)),
  };
}

/**
 * The guided orientation.
 *
 * Mounted once in `MainLayout`, renders nothing until the tour is started
 * (by the demo login, or from the Home page). It dims the app, cuts a hole
 * around the current step's element, and explains it.
 */
export default function TourOverlay() {
  const { active, index, next, back, end, skipStep, skipped } = useTourStore();
  const step = TOUR_STEPS[index];

  const navigate = useNavigate();
  const { pathname } = useLocation();
  const guilds = useGuildStore((state) => state.guilds);
  const setPanelOpen = useUiStore((state) => state.setPanelOpen);

  const [hole, setHole] = useState<Rect | null>(null);
  const [cardHeight, setCardHeight] = useState(190);
  const cardRef = useRef<HTMLDivElement>(null);

  const firstGuildId = guilds[0]?.id;

  // --- put the app where the step needs it -----------------------------
  useEffect(() => {
    if (!active || !step) return;

    if (step.route) {
      const target = step.route.replace(":guild", firstGuildId ?? "");
      // A step anchored to a guild is meaningless for an account with none
      if (step.route.includes(":guild") && !firstGuildId) {
        skipStep(step.id);
        next();
        return;
      }
      // Exact, not a prefix. Every step names the screen it is describing, so
      // "close enough" is wrong in both directions: going back from the guild
      // channel step to the guild list would stay on the channel, and a step
      // for /dm would accept /dm/<some-conversation>.
      if (pathname !== target) navigate(target);
    }
    // `pathname` is deliberately not a dependency: navigating would re-run this
    // and fight any redirect the app itself performs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, step?.id, firstGuildId]);

  // --- find the element, and keep the hole on it ------------------------
  useEffect(() => {
    if (!active || !step) {
      // Drop the last rect once the tour stops, or restarting it would open on
      // the previous run's final element and fly across the screen from there.
      setHole(null);
      return;
    }

    let raf = 0;
    const deadline = performance.now() + TARGET_TIMEOUT_MS;

    const measure = () => {
      const rect = readRect(step.target);
      if (rect) {
        setHole(rect);
        return true;
      }
      return false;
    };

    // The element may not exist yet: a route change has to render first, and a
    // drawer has a transition. Poll until it turns up, then give up on the step
    // rather than stalling the tour on a UI that never appears.
    const poll = () => {
      if (measure()) return;

      // Only once measuring has failed, which on a desktop it never does: the
      // panel is in flow there and this is left alone. Below `lg` it is an
      // off-canvas drawer that `SidePanel` closes on every navigation,
      // including the one this step just performed. Nudging it from here
      // rather than beside the navigate call avoids depending on which effect
      // runs first; it simply keeps asking until the panel is on screen.
      // Writing only when it is shut keeps this from looping.
      if (step.needsPanel && !useUiStore.getState().panelOpen) {
        useUiStore.getState().setPanelOpen(true);
      }

      if (performance.now() > deadline) {
        skipStep(step.id);
        next();
        return;
      }
      raf = requestAnimationFrame(poll);
    };
    poll();

    const onViewportChange = () => measure();
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("scroll", onViewportChange, true);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, step?.id, pathname]);

  // The previous step's rect is deliberately kept until the next one is
  // measured. Clearing it unmounted the whole overlay for the frames between
  // two steps, so the dim blinked off and the spotlight vanished and
  // reappeared. Holding it lets the CSS transition slide the spotlight from
  // one element to the next, which is the movement that makes the tour read as
  // progressing rather than stuck.
  useLayoutEffect(() => {
    if (cardRef.current) setCardHeight(cardRef.current.offsetHeight);
  }, [step?.id, hole]);

  const handleEnd = useCallback(() => {
    setPanelOpen(false);
    end();
  }, [end, setPanelOpen]);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleEnd();
      if (e.key === "ArrowRight" || e.key === "Enter") next();
      if (e.key === "ArrowLeft") back();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [active, next, back, handleEnd]);

  if (!active || !step || !hole) return null;

  const padded: Rect = {
    top: hole.top - HOLE_PADDING,
    left: hole.left - HOLE_PADDING,
    width: hole.width + HOLE_PADDING * 2,
    height: hole.height + HOLE_PADDING * 2,
  };
  const card = placeCard(padded, cardHeight, step.placement);
  const shown = index - skipped.length + 1;
  const total = TOUR_STEP_COUNT - skipped.length;
  const isLast = index >= TOUR_STEPS.length - 1;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Product tour"
      className="fixed inset-0 z-[90]"
    >
      {/* Swallows clicks on the app underneath: the tour drives itself, and a
          stray click would leave the spotlight pointing at the wrong screen.
          It does not end the tour — the spotlight invites clicking the thing it
          is highlighting, and having that quietly close the tour was the worst
          possible answer to the most likely gesture. Escape, the X and "Skip
          tour" are the ways out. */}
      <div className="absolute inset-0" />

      {/* The dim *is* this element's shadow. One box with a huge spread costs
          nothing and cuts a rounded hole no four-div overlay can match. */}
      <div
        aria-hidden
        className="pointer-events-none absolute rounded-xl ring-2 ring-rain-400/70 transition-all duration-300 ease-out"
        style={{
          top: padded.top,
          left: padded.left,
          width: padded.width,
          height: padded.height,
          boxShadow: "0 0 0 9999px rgba(3, 7, 18, 0.78)",
        }}
      />

      <div
        ref={cardRef}
        // Travels with the spotlight rather than jumping, for the same reason
        className="absolute rounded-2xl border border-white/10 bg-ink-900 p-5 shadow-lift transition-all duration-300 ease-out"
        style={{
          top: card.top,
          left: card.left,
          width: Math.min(CARD_WIDTH, window.innerWidth - 2 * GAP),
        }}
      >
        <button
          onClick={handleEnd}
          aria-label="End tour"
          className="absolute right-3 top-3 rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          <FiX size={16} />
        </button>

        <p className="font-mono text-[10px] uppercase tracking-widest text-rain-300">
          Step {shown} of {total}
        </p>
        <h3 className="mt-2 pr-6 text-[15px] font-semibold text-white">
          {step.title}
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-ink-300">{step.body}</p>

        <div className="mt-5 flex items-center justify-between gap-2">
          <button
            onClick={handleEnd}
            className="text-xs text-ink-400 transition-colors hover:text-white"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {index > 0 && (
              <Button size="sm" variant="ghost" onClick={back}>
                Back
              </Button>
            )}
            <Button size="sm" variant="primary" onClick={isLast ? handleEnd : next}>
              {isLast ? "Done" : "Next"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
