import { create } from "zustand";
import { type Guild, type GuildMember } from "./types";
import { getGuildMembers, getUserGuilds } from "./apiClient";
import { eventBus } from "../utils/EventBus";
import { EventType, type EventPayload } from "../utils/eventType";

export interface GuildStore {
  guilds: Guild[];
  guildChannelIds: Record<string, string[]>;
  members: Record<string, GuildMember[]>; // guildId -> members
  setGuilds: (guilds: Guild[]) => void;
  setGuildChannels: (guildChannelIds: Record<string, string[]>) => void;
  getGuildChannels: (guildId: string) => string[];
  getGuild: (guildId: string) => Guild | undefined;
  getMembers: (guildId: string) => GuildMember[];
  addGuild: (guild: Guild) => void;
  modalOpen: boolean;
  setModalOpen: (modalOpen: boolean) => void;
  channelModalGuildId: string | null;
  setChannelModalGuildId: (guildId: string | null) => void;
  fetchUserGuilds: () => Promise<void>;
  fetchGuildMembers: (guildId: string) => Promise<void>;
  reset: () => void;
}

export const useGuildStore = create<GuildStore>((set, get) => ({
  guilds: [],
  guildChannelIds: {},
  members: {},
  setGuildChannels: (guildChannelIds) => set({ guildChannelIds }),
  getGuildChannels: (guildId) => get().guildChannelIds[guildId] ?? [],
  getGuild: (guildId) => get().guilds.find((guild) => guild.id === guildId),
  getMembers: (guildId) => get().members[guildId] ?? [],
  setGuilds: (guilds) => set({ guilds }),
  addGuild: (guild) =>
    set((state) =>
      state.guilds.some((g) => g.id === guild.id)
        ? state
        : { guilds: [...state.guilds, guild] }
    ),
  modalOpen: false,
  setModalOpen: (modalOpen) => set({ modalOpen }),
  channelModalGuildId: null,
  setChannelModalGuildId: (guildId) => set({ channelModalGuildId: guildId }),
  fetchUserGuilds: async () => {
    try {
      const guilds = await getUserGuilds();
      set({ guilds });
    } catch (error) {
      console.error("Failed to fetch guilds:", error);
    }
  },
  fetchGuildMembers: async (guildId) => {
    try {
      const members = await getGuildMembers(guildId);
      set((state) => ({ members: { ...state.members, [guildId]: members } }));
    } catch (error) {
      console.error("Failed to fetch guild members:", error);
    }
  },

  reset: () =>
    set({
      guilds: [],
      guildChannelIds: {},
      members: {},
      modalOpen: false,
      channelModalGuildId: null,
    }),
}));

// Joining or leaving a guild arrives as a membership change carrying a guild id.
eventBus.on(EventType.NOTIFICATION, async (event: EventPayload) => {
  const metadata = event.metadata as
    | { channels_changed?: boolean; guild_id?: string }
    | undefined;
  if (!metadata?.channels_changed || !metadata.guild_id) return;

  await useGuildStore.getState().fetchUserGuilds();
  // Skip the member fetch when the change was us being removed from the guild
  if (useGuildStore.getState().getGuild(metadata.guild_id)) {
    useGuildStore.getState().fetchGuildMembers(metadata.guild_id);
  }
});
