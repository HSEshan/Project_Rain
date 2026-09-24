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
  /**
   * Replace the open card's contents with a profile the caller already has.
   *
   * Saving an edit returns the new profile, and rest_api deliberately does not
   * send the actor their own event, so this response is the only news of the
   * change that will ever arrive. Refetching instead would work and would be a
   * second round trip for an answer already in hand.
   */
  applyProfile: (profile: UserProfile) => void;
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

  applyProfile: (profile) => {
    // Ignore a result for a card that is no longer the open one: a save can
    // land after the user has clicked through to somebody else.
    if (get().userId !== profile.id) return;
    set({ profile });
  },

  close: () => set({ userId: null, profile: null, loading: false, error: "" }),
}));
