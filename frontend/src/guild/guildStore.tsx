import { create } from "zustand";
import { type Guild } from "./types";
import { getUserGuilds } from "./apiClient";

export interface GuildStore {
  guilds: Guild[];
  setGuilds: (guilds: Guild[]) => void;
  modalOpen: boolean;
  setModalOpen: (modalOpen: boolean) => void;
  fetchUserGuilds: () => Promise<void>;
}

export const useGuildStore = create<GuildStore>((set) => ({
  guilds: [],
  setGuilds: (guilds) => set({ guilds }),
  modalOpen: false,
  setModalOpen: (modalOpen) => set({ modalOpen }),
  fetchUserGuilds: async () => {
    try {
      const guilds = await getUserGuilds();
      set({ guilds });
    } catch (error) {
      console.error("Failed to fetch guilds:", error);
    }
  },
}));
