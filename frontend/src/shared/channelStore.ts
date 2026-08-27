import { create } from "zustand";
import type { Channel } from "./types";
import {
  getChannel,
  getChannelParticipants,
  getUserChannels,
} from "./channelApiClient";
import { ChannelType, DIRECT_CHANNEL_TYPES } from "./types";
import { eventBus } from "../utils/EventBus";
import { onResync } from "./resync";
import { EventAction, EventType, type EventPayload } from "../utils/eventType";

interface ChannelStore {
  channels: Record<string, Channel>; // store metadata only
  participants: Record<string, string[]>; // channelId -> userIds

  setChannels: (channels: Channel[]) => void;
  addChannel: (channel: Channel) => void;
  removeChannel: (channelId: string) => void;

  getChannel: (channelId: string) => Channel | undefined;
  /** DMs and group DMs, which is what the messages sidebar lists. */
  getDMChannels: () => Channel[];
  /** The two-person DM with someone, never a group they happen to share. */
  getDMChannelWithUser: (userId: string) => Channel | undefined;
  getGuildChannels: (guildId: string) => Channel[];
  getParticipants: (channelId: string) => string[];
  setParticipants: (channelId: string, participants: string[]) => void;

  fetchUserChannels: () => Promise<void>;
  fetchDMChannelParticipants: () => Promise<void>;
  /** Re-read one channel, after a rename or a roster change. */
  refreshChannel: (channelId: string) => Promise<void>;
  reset: () => void;
}

export const useChannelStore = create<ChannelStore>((set, get) => ({
  channels: {},
  participants: {},

  setChannels: (channels) =>
    set((state) => {
      const newChannels = { ...state.channels };
      channels.forEach((ch) => {
        newChannels[ch.id] = ch;
      });
      return { channels: newChannels };
    }),

  addChannel: (channel) =>
    set((state) => ({
      channels: { ...state.channels, [channel.id]: channel },
    })),

  removeChannel: (channelId) =>
    set((state) => {
      const newChannels = { ...state.channels };
      delete newChannels[channelId];
      return { channels: newChannels };
    }),

  getChannel: (channelId) => get().channels[channelId],

  getDMChannels: () =>
    Object.values(get().channels).filter((ch) =>
      DIRECT_CHANNEL_TYPES.includes(ch.type)
    ),

  getDMChannelWithUser: (userId) =>
    Object.values(get().channels).find(
      (ch) =>
        ch.type === ChannelType.DM &&
        get().getParticipants(ch.id).includes(userId)
    ),

  getGuildChannels: (guildId) =>
    Object.values(get().channels).filter((ch) => ch.guild_id === guildId),

  getParticipants: (channelId) => get().participants[channelId] ?? [],

  setParticipants: (channelId, participants) =>
    set((state) => ({
      participants: { ...state.participants, [channelId]: participants },
    })),

  fetchUserChannels: async () => {
    try {
      const channels = await getUserChannels();
      set({
        channels: channels.reduce((acc, channel) => {
          acc[channel.id] = channel;
          return acc;
        }, {} as Record<string, Channel>),
      });
      console.log("Channels fetched and set:", channels);
    } catch (error) {
      console.error(" Failed to initialize channels", error);
    }
  },
  fetchDMChannelParticipants: async () => {
    const DMChannels = get().getDMChannels();
    console.log("DM Channels found:", DMChannels);

    if (DMChannels.length === 0) {
      console.log("No DM channels found, skipping participant fetch");
      return;
    }

    const participants = await getChannelParticipants(
      DMChannels.map((ch) => ch.id)
    );
    console.log("Participants fetched:", participants);

    set({
      participants: {
        ...get().participants,
        ...Object.entries(participants).reduce((acc, [channelId, userIds]) => {
          acc[channelId] = userIds;
          return acc;
        }, {} as Record<string, string[]>),
      },
    });
    console.log("Participants set in store");
  },

  refreshChannel: async (channelId) => {
    const [channel, participants] = await Promise.all([
      getChannel(channelId),
      getChannelParticipants([channelId]),
    ]);
    if (channel) get().addChannel(channel);
    if (participants[channelId]) {
      get().setParticipants(channelId, participants[channelId]);
    }
  },

  reset: () => set({ channels: {}, participants: {} }),
}));

/**
 * rest_api publishes a notification whenever the signed-in user's channel
 * membership changes (friend accepted, guild joined or left, channel created).
 * Refetching is cheap and always correct, unlike patching the store per action.
 */
eventBus.on(EventType.NOTIFICATION, async (event: EventPayload) => {
  const metadata = event.metadata as
    | { channels_changed?: boolean; action?: string; channel_id?: string }
    | undefined;

  // A group DM you are already in moved its name or its roster. Nothing about
  // *which* channels you are in changed, so re-reading one channel is both
  // enough and cheaper than rebuilding the list.
  if (metadata?.action === EventAction.GROUP_DM_UPDATED) {
    if (metadata.channel_id) {
      await useChannelStore.getState().refreshChannel(metadata.channel_id);
    }
    return;
  }

  if (!metadata?.channels_changed) return;

  await useChannelStore.getState().fetchUserChannels();
  await useChannelStore.getState().fetchDMChannelParticipants();
});

// A membership change that happened while the socket was down arrives as
// nothing at all, so the reconnect has to assume the worst and re-read.
onResync(async () => {
  await useChannelStore.getState().fetchUserChannels();
  await useChannelStore.getState().fetchDMChannelParticipants();
});
