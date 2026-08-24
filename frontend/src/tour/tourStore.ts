import { create } from "zustand";
import { TOUR_STEPS, type TourStep } from "./steps";

/**
 * Which orientation step is showing.
 *
 * State only. Navigating between steps and measuring the target element are
 * effects, so they live in `TourOverlay` where the router hooks are available.
 *
 * "Seen" is remembered in localStorage so the tour does not reappear on every
 * visit, while the demo login starts it explicitly regardless.
 */

const SEEN_KEY = "rain.tour.seen";

function markSeen() {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    // Private mode or a blocked store. Losing the flag only means the tour can
    // be offered again, which is harmless.
  }
}

export function hasSeenTour(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

interface TourStore {
  active: boolean;
  index: number;
  /** Steps whose target never appeared, so Back does not return to them. */
  skipped: string[];

  start: () => void;
  next: () => void;
  back: () => void;
  end: () => void;
  skipStep: (id: string) => void;

  currentStep: () => TourStep | undefined;
  isLast: () => boolean;
}

export const useTourStore = create<TourStore>((set, get) => ({
  active: false,
  index: 0,
  skipped: [],

  start: () => set({ active: true, index: 0, skipped: [] }),

  next: () => {
    const { index } = get();
    if (index >= TOUR_STEPS.length - 1) {
      get().end();
      return;
    }
    set({ index: index + 1 });
  },

  back: () => set((state) => ({ index: Math.max(0, state.index - 1) })),

  end: () => {
    markSeen();
    set({ active: false, index: 0 });
  },

  // A step is dropped rather than blocking the tour when its target is not on
  // the page — an account with no guilds has no channel list to point at.
  skipStep: (id) =>
    set((state) =>
      state.skipped.includes(id) ? state : { skipped: [...state.skipped, id] }
    ),

  currentStep: () => TOUR_STEPS[get().index],

  isLast: () => get().index >= TOUR_STEPS.length - 1,
}));

export const TOUR_STEP_COUNT = TOUR_STEPS.length;
