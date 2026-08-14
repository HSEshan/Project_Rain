import { create } from "zustand";
import { type Guild } from "./types";
import { getUserGuilds } from "./apiClient";

export interface GuildStore {
  guilds: Guild[];
  guildChannelIds: Record<string, string[]>;
  setGuilds: (guilds: Guild[]) => void;
  setGuildChannels: (guildChannelIds: Record<string, string[]>) => void;
  getGuildChannels: (guildId: string) => string[];
  addGuild: (guild: Guild) => void;
  modalOpen: boolean;
  setModalOpen: (modalOpen: boolean) => void;
  fetchUserGuilds: () => Promise<void>;
  reset: () => void;
}

export const useGuildStore = create<GuildStore>((set, get) => ({
  guilds: [],
  guildChannelIds: {},
  setGuildChannels: (guildChannelIds) => set({ guildChannelIds }),
  getGuildChannels: (guildId) => get().guildChannelIds[guildId] ?? [],
  setGuilds: (guilds) => set({ guilds }),
  addGuild: (guild) =>
    set((state) =>
      state.guilds.some((g) => g.id === guild.id)
        ? state
        : { guilds: [...state.guilds, guild] }
    ),
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

  reset: () => set({ guilds: [], guildChannelIds: {}, modalOpen: false }),
}));
