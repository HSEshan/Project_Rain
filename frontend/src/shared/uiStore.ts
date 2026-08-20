import { create } from "zustand";

/**
 * Purely presentational state — which responsive drawer is open.
 *
 * It lives in a store rather than in each layout because the button that opens
 * a panel sits in the view header, which is a sibling of the panel, not a
 * parent. Nothing here needs resetting on logout.
 */
interface UiStore {
  /** Secondary sidebar (DM list, channel list) as a drawer below `lg`. */
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
  /** Guild members list as a drawer below `xl`. */
  membersOpen: boolean;
  setMembersOpen: (open: boolean) => void;
  closeAll: () => void;
}

export const useUiStore = create<UiStore>((set) => ({
  panelOpen: false,
  setPanelOpen: (panelOpen) => set({ panelOpen }),
  membersOpen: false,
  setMembersOpen: (membersOpen) => set({ membersOpen }),
  closeAll: () => set({ panelOpen: false, membersOpen: false }),
}));
