import { create } from "zustand";
import { getUserProfile, type UserProfile } from "./apiClient";
import { errorText } from "../shared/errors";

/**
 * Which profile card is open, and what is in it.
 *
 * A store rather than component state because the card is opened from
 * everywhere a username appears (a message, the member list, the friends page,
 * a voice roster) and those are scattered across the tree. The card itself
 * mounts once in `MainLayout`, like every other modal in this app.
 *
 * The profile is always refetched on open rather than read from `userStore`.
 * `userStore` holds id and username, which is what message rendering needs;
 * the card is about the relationship, and that changes underneath you.
 */
interface ProfileStore {
  userId: string | null;
  profile: UserProfile | null;
  loading: boolean;
  error: string;

  openProfile: (userId: string) => Promise<void>;
  refresh: () => Promise<void>;
  close: () => void;
}

export const useProfileStore = create<ProfileStore>((set, get) => ({
  userId: null,
  profile: null,
  loading: false,
  error: "",

  openProfile: async (userId) => {
    // Clear the previous card's contents: showing the last person you looked
    // at under the new person's name for a moment is worse than a spinner.
    set({ userId, profile: null, loading: true, error: "" });
    try {
      const profile = await getUserProfile(userId);
      // Another card may have been opened while this request was in flight.
      if (get().userId !== userId) return;
      set({ profile, loading: false });
    } catch (error) {
      if (get().userId !== userId) return;
      set({ loading: false, error: errorText(error, "Could not load this profile.") });
    }
  },

  refresh: async () => {
    const userId = get().userId;
    if (userId) await get().openProfile(userId);
  },

  close: () => set({ userId: null, profile: null, loading: false, error: "" }),
}));
