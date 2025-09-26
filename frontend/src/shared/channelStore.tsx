import { create } from "zustand";
import type { Channel } from "./types";
import { getChannelParticipants, getUserChannels } from "./channelApiClient";
import { ChannelType } from "./types";

interface ChannelStore {
  channels: Record<string, Channel>; // store metadata only
  participants: Record<string, string[]>; // channelId -> userIds

  setChannels: (channels: Channel[]) => void;
  addChannel: (channel: Channel) => void;
  removeChannel: (channelId: string) => void;

  getChannel: (channelId: string) => Channel | undefined;
  getDMChannels: () => Channel[];
  getGuildChannels: (guildId: string) => Channel[];
  getParticipants: (channelId: string) => string[];
  setParticipants: (channelId: string, participants: string[]) => void;

  fetchUserChannels: () => void;
  fetchDMChannelParticipants: () => void;
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
}));
