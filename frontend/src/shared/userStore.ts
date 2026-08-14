import { create } from "zustand";
import { getUsers } from "./userApiClient";

export interface User {
  id: string;
  username: string;
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
      newUsers.forEach((u) => {
        updated[u.id] = u;
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
