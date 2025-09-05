import { create } from "zustand";
import { type Guild } from "./types";
import { getUserGuilds } from "./apiClient";

export interface GuildStore {
  guilds: Guild[];
  setGuilds: (guilds: Guild[]) => void;
  initialize: () => void;
}

export const useGuildStore = create<GuildStore>((set) => ({
  guilds: [],
  setGuilds: (guilds) => set({ guilds }),
  initialize: async () => {
    const guilds = await getUserGuilds();
    set({ guilds });
  },
}));
