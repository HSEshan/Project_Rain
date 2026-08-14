import { create } from "zustand";
import type { Channel } from "./types";
import { getChannelParticipants, getUserChannels } from "./channelApiClient";
import { ChannelType } from "./types";
import { eventBus } from "../utils/EventBus";
import { EventType, type EventPayload } from "../utils/eventType";

interface ChannelStore {
  channels: Record<string, Channel>; // store metadata only
  participants: Record<string, string[]>; // channelId -> userIds

  setChannels: (channels: Channel[]) => void;
  addChannel: (channel: Channel) => void;
  removeChannel: (channelId: string) => void;

  getChannel: (channelId: string) => Channel | undefined;
  getDMChannels: () => Channel[];
  getDMChannelWithUser: (userId: string) => Channel | undefined;
  getGuildChannels: (guildId: string) => Channel[];
  getParticipants: (channelId: string) => string[];
  setParticipants: (channelId: string, participants: string[]) => void;

  fetchUserChannels: () => Promise<void>;
  fetchDMChannelParticipants: () => Promise<void>;
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
    Object.values(get().channels).filter((ch) => ch.type === ChannelType.DM),

  getDMChannelWithUser: (userId) =>
    get()
      .getDMChannels()
      .find((ch) => get().getParticipants(ch.id).includes(userId)),

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
    const DMChannels = Object.values(get().channels).filter(
      (ch) => ch.type === ChannelType.DM
    );
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

  reset: () => set({ channels: {}, participants: {} }),
}));

/**
 * rest_api publishes a notification whenever the signed-in user's channel
 * membership changes (friend accepted, guild joined or left, channel created).
 * Refetching is cheap and always correct, unlike patching the store per action.
 */
eventBus.on(EventType.NOTIFICATION, async (event: EventPayload) => {
  const metadata = event.metadata as { channels_changed?: boolean } | undefined;
  if (!metadata?.channels_changed) return;

  await useChannelStore.getState().fetchUserChannels();
  await useChannelStore.getState().fetchDMChannelParticipants();
});
