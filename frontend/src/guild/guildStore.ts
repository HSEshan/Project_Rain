import { create } from "zustand";
import { type Guild, type GuildMember } from "./types";
import {
  deleteGuildInvite,
  getGuildMembers,
  getMyGuildInvites,
  getUserGuilds,
  postAcceptGuildInvite,
  type GuildInvite,
} from "./apiClient";
import { eventBus } from "../utils/EventBus";
import { onResync } from "../shared/resync";
import { EventAction, EventType, type EventPayload } from "../utils/eventType";

export interface GuildStore {
  guilds: Guild[];
  /** True once `guilds` is an answer, so empty can mean empty. */
  guildsLoaded: boolean;
  guildChannelIds: Record<string, string[]>;
  members: Record<string, GuildMember[]>; // guildId -> members
  invites: GuildInvite[]; // guild invites waiting for this user
  setGuilds: (guilds: Guild[]) => void;
  setGuildChannels: (guildChannelIds: Record<string, string[]>) => void;
  getGuildChannels: (guildId: string) => string[];
  getGuild: (guildId: string) => Guild | undefined;
  getMembers: (guildId: string) => GuildMember[];
  addGuild: (guild: Guild) => void;
  /** Swap in a guild the server just returned, e.g. after an icon change. */
  replaceGuild: (guild: Guild) => void;
  removeGuild: (guildId: string) => void;
  /** Swap in a member the server just returned, e.g. after a role change. */
  setMember: (member: GuildMember) => void;
  removeMember: (guildId: string, userId: string) => void;
  modalOpen: boolean;
  setModalOpen: (modalOpen: boolean) => void;
  channelModalGuildId: string | null;
  setChannelModalGuildId: (guildId: string | null) => void;
  inviteModalGuildId: string | null;
  setInviteModalGuildId: (guildId: string | null) => void;
  inviteInboxOpen: boolean;
  setInviteInboxOpen: (open: boolean) => void;
  settingsModalGuildId: string | null;
  setSettingsModalGuildId: (guildId: string | null) => void;
  fetchUserGuilds: () => Promise<void>;
  fetchGuildMembers: (guildId: string) => Promise<void>;
  fetchInvites: () => Promise<void>;
  acceptInvite: (invite: GuildInvite) => Promise<void>;
  declineInvite: (invite: GuildInvite) => Promise<void>;
  removeInvite: (inviteId: string) => void;
  reset: () => void;
}

export const useGuildStore = create<GuildStore>((set, get) => ({
  guilds: [],
  guildsLoaded: false,
  guildChannelIds: {},
  members: {},
  invites: [],
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
  replaceGuild: (guild) =>
    set((state) => ({
      guilds: state.guilds.map((g) => (g.id === guild.id ? guild : g)),
    })),
  removeGuild: (guildId) =>
    set((state) => ({
      guilds: state.guilds.filter((g) => g.id !== guildId),
    })),
  setMember: (member) =>
    set((state) => ({
      members: {
        ...state.members,
        [member.guild_id]: (state.members[member.guild_id] ?? []).map((m) =>
          m.user_id === member.user_id ? member : m
        ),
      },
    })),
  removeMember: (guildId, userId) =>
    set((state) => ({
      members: {
        ...state.members,
        [guildId]: (state.members[guildId] ?? []).filter(
          (m) => m.user_id !== userId
        ),
      },
    })),
  modalOpen: false,
  setModalOpen: (modalOpen) => set({ modalOpen }),
  channelModalGuildId: null,
  setChannelModalGuildId: (guildId) => set({ channelModalGuildId: guildId }),
  inviteModalGuildId: null,
  setInviteModalGuildId: (guildId) => set({ inviteModalGuildId: guildId }),
  inviteInboxOpen: false,
  setInviteInboxOpen: (open) => set({ inviteInboxOpen: open }),
  settingsModalGuildId: null,
  setSettingsModalGuildId: (guildId) => set({ settingsModalGuildId: guildId }),
  fetchUserGuilds: async () => {
    try {
      const guilds = await getUserGuilds();
      set({ guilds, guildsLoaded: true });
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

  fetchInvites: async () => {
    try {
      set({ invites: await getMyGuildInvites() });
    } catch (error) {
      console.error("Failed to fetch guild invites:", error);
    }
  },

  removeInvite: (inviteId) =>
    set((state) => ({
      invites: state.invites.filter((i) => i.invite_id !== inviteId),
    })),

  acceptInvite: async (invite) => {
    await postAcceptGuildInvite(invite.guild_id, invite.invite_id);
    // Accepting consumes the invite, so drop it here rather than refetching.
    get().removeInvite(invite.invite_id);
    // Not left to the channels_changed event: the caller navigates straight
    // into the guild, and `GuildLayout` sends away anyone not in it.
    await get().fetchUserGuilds();
  },

  declineInvite: async (invite) => {
    await deleteGuildInvite(invite.guild_id, invite.invite_id);
    get().removeInvite(invite.invite_id);
  },

  reset: () =>
    set({
      guilds: [],
      guildsLoaded: false,
      guildChannelIds: {},
      members: {},
      invites: [],
      modalOpen: false,
      channelModalGuildId: null,
      inviteModalGuildId: null,
      inviteInboxOpen: false,
      settingsModalGuildId: null,
    }),
}));

// Joining or leaving a guild arrives as a membership change carrying a guild id.
eventBus.on(EventType.NOTIFICATION, async (event: EventPayload) => {
  const metadata = event.metadata as
    | {
        action?: string;
        channels_changed?: boolean;
        guild_id?: string;
        invite_id?: string;
      }
    | undefined;

  // An invite is not a membership change — it is an offer, and it has to show
  // up without a reload the same way a friend request does.
  if (metadata?.action === EventAction.GUILD_INVITE_RECEIVED) {
    await useGuildStore.getState().fetchInvites();
    return;
  }

  // Declined somewhere else — this tab is still showing the offer.
  if (metadata?.action === EventAction.GUILD_INVITE_REMOVED) {
    if (metadata.invite_id) {
      useGuildStore.getState().removeInvite(metadata.invite_id);
    }
    return;
  }

  // Renamed, or someone's role or membership moved. Yours may be the role, so
  // both the guild and its member list are re-read.
  if (metadata?.action === EventAction.GUILD_UPDATED) {
    if (metadata.guild_id) {
      const store = useGuildStore.getState();
      await store.fetchUserGuilds();
      await store.fetchGuildMembers(metadata.guild_id);
    }
    return;
  }

  if (!metadata?.channels_changed || !metadata.guild_id) return;

  // Joining a guild consumes any invite to it, including one accepted in
  // another tab, where nothing local dropped the row.
  const guildId = metadata.guild_id;
  const stale = useGuildStore
    .getState()
    .invites.filter((invite) => invite.guild_id === guildId);
  stale.forEach((invite) =>
    useGuildStore.getState().removeInvite(invite.invite_id)
  );

  await useGuildStore.getState().fetchUserGuilds();
  // Skip the member fetch when the change was us being removed from the guild
  if (useGuildStore.getState().getGuild(metadata.guild_id)) {
    useGuildStore.getState().fetchGuildMembers(metadata.guild_id);
  }
});

onResync(async () => {
  await useGuildStore.getState().fetchUserGuilds();
  await useGuildStore.getState().fetchInvites();
});
