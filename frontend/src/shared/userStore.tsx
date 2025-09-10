import { create } from "zustand";
import { getUsers } from "./apiClient";

export interface User {
  id: string;
  username: string;
}

export interface UserStore {
  users: Map<string, User>;
  setUsers: (users: User[]) => void;
  addUsers: (ids: string[]) => Promise<void>;
  getUser: (id: string) => User | undefined;
  getUsers: (ids: string[]) => User[];
  isUserLoaded: (id: string) => boolean;
  getMissingUserIds: (ids: string[]) => string[];
}

export const useUserStore = create<UserStore>((set, get) => ({
  users: new Map(),

  setUsers: (newUsers) => {
    const currentUsers = get().users;
    newUsers.forEach((user) => {
      currentUsers.set(user.id, user);
    });
    set({ users: currentUsers });
  },

  getUser: (id) => get().users.get(id),

  getUsers: (ids) => {
    const users = get().users;
    return ids.map((id) => users.get(id)).filter(Boolean) as User[];
  },

  isUserLoaded: (id) => get().users.has(id),

  getMissingUserIds: (ids) => {
    const users = get().users;
    return ids.filter((id) => !users.has(id));
  },

  addUsers: async (ids) => {
    const { getMissingUserIds, setUsers } = get();
    const missingIds = getMissingUserIds(ids);

    if (missingIds.length === 0) {
      console.log("All users already loaded");
      return; // All users already loaded
    }

    try {
      const response = await getUsers({ ids: missingIds });
      setUsers(response.data.users);
    } catch (error) {
      console.error("Failed to fetch users:", error);
    }
  },
}));
