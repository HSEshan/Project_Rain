import { create } from "zustand";
import { type Guild } from "./types";
import { getUserGuilds } from "./apiClient";

export interface GuildStore {
  guilds: Guild[];
  guildChannelIds: Record<string, string[]>;
  setGuilds: (guilds: Guild[]) => void;
  setGuildChannels: (guildChannelIds: Record<string, string[]>) => void;
  getGuildChannels: (guildId: string) => string[];
  modalOpen: boolean;
  setModalOpen: (modalOpen: boolean) => void;
  fetchUserGuilds: () => Promise<void>;
}

export const useGuildStore = create<GuildStore>((set, get) => ({
  guilds: [],
  guildChannelIds: {},
  setGuildChannels: (guildChannelIds) => set({ guildChannelIds }),
  getGuildChannels: (guildId) => get().guildChannelIds[guildId] ?? [],
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
