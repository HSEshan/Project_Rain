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
  /**
   * Whether the current route has a drawer to open at all. Home and the guild
   * picker have no secondary panel, and a menu button that opens nothing is
   * exactly the dead control this exists to hide.
   */
  hasPanel: boolean;
  setHasPanel: (hasPanel: boolean) => void;
  /** Guild members list as a drawer below `xl`. */
  membersOpen: boolean;
  setMembersOpen: (open: boolean) => void;
  /** "New group" modal, opened from the messages sidebar. */
  groupCreateOpen: boolean;
  setGroupCreateOpen: (open: boolean) => void;
  closeAll: () => void;
}

export const useUiStore = create<UiStore>((set) => ({
  panelOpen: false,
  setPanelOpen: (panelOpen) => set({ panelOpen }),
  hasPanel: false,
  setHasPanel: (hasPanel) => set({ hasPanel }),
  membersOpen: false,
  setMembersOpen: (membersOpen) => set({ membersOpen }),
  groupCreateOpen: false,
  setGroupCreateOpen: (groupCreateOpen) => set({ groupCreateOpen }),
  closeAll: () => set({ panelOpen: false, membersOpen: false }),
}));
