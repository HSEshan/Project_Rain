import { create } from "zustand";
import { getUsers } from "./userApiClient";
import { eventBus } from "../utils/EventBus";
import { EventAction, EventType, type EventPayload } from "../utils/eventType";

export interface User {
  id: string;
  username: string;
  /** Null for anyone who has not uploaded one; `Avatar` falls back to initials. */
  avatar_url?: string | null;
}

export interface UserStore {
  users: Record<string, User>;
  mergeUsers: (users: User[]) => void;
  fetchUsers: (ids: string[]) => Promise<void>;
  getUser: (id: string) => User | undefined;
  getMultipleUsers: (ids: string[]) => User[];
  isUserLoaded: (id: string) => boolean;
  getMissingUserIds: (ids: string[]) => string[];
  clearUsers: () => void;
}

export const useUserStore = create<UserStore>((set, get) => ({
  users: {},

  mergeUsers: (newUsers) =>
    set((state) => {
      const updated = { ...state.users };
      // Merged into what is there, not replacing it: some callers know only an
      // id and a username (a friend-accepted event), and replacing would wipe
      // an avatar we already had. A field that is present wins, null included.
      newUsers.forEach((u) => {
        updated[u.id] = { ...updated[u.id], ...u };
      });
      return { users: updated };
    }),

  getUser: (id) => get().users[id],

  getMultipleUsers: (ids) =>
    ids.map((id) => get().users[id]).filter(Boolean) as User[],

  isUserLoaded: (id) => !!get().users[id],

  getMissingUserIds: (ids) => ids.filter((id) => !get().users[id]),

  fetchUsers: async (ids) => {
    const missingIds = get().getMissingUserIds(ids);
    if (missingIds.length === 0) {
      console.log("All users are loaded", ids);
      return;
    }

    try {
      const response = await getUsers(missingIds);
      get().mergeUsers(response.data.users);
      console.log("Users fetched and merged:", response.data.users);
    } catch (error) {
      console.error("Failed to fetch users:", error);
    }
  },

  clearUsers: () => set({ users: {} }),
}));

/**
 * An avatar changed. `fetchUsers` only asks about ids it has never seen, so
 * without this a changed picture would stay stale until a reload. Patches the
 * one row, and only if we have it: someone we have never rendered will be
 * fetched fresh when we first need them.
 */
eventBus.on(EventType.NOTIFICATION, (event: EventPayload) => {
  const metadata = event.metadata as
    | { action?: string; user_id?: string; avatar_url?: string | null }
    | undefined;
  if (metadata?.action !== EventAction.USER_UPDATED || !metadata.user_id) return;
  const existing = useUserStore.getState().users[metadata.user_id];
  if (!existing) return;
  useUserStore
    .getState()
    .mergeUsers([{ ...existing, avatar_url: metadata.avatar_url ?? null }]);
});
