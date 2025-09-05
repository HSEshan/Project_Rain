import { create } from "zustand";
import { type DMChannel, type Message } from "./types";
import { getUserDMChannels, getChannelMessages } from "./apiClient";
import { eventBus } from "../utils/EventBus";
import { EventType, type EventPayload } from "../utils/eventType";
export interface MessageStore {
  channels: DMChannel[];
  setChannels: (channels: DMChannel[]) => void;
  messages: Record<string, Message[]>;
  setMessages: (messages: Record<string, Message[]>) => void;
  unReads: string[];
  setUnReads: (unReads: string[]) => void;
  addUnRead: (channelId: string) => void;
  removeUnRead: (channelId: string) => void;
  addMessage: (message: Message, unread: boolean) => void;
  removeMessage: (message: Message) => void;
  getMessages: (channelId: string | undefined) => Message[];
  fetchChannelMessages: (channelId: string) => void;
  initialize: () => void;
}

export const useMessageStore = create<MessageStore>((set, get) => ({
  channels: [],
  setChannels: (channels) => set({ channels }),
  messages: {},
  setMessages: (messages) => set({ messages }),
  unReads: [],
  setUnReads: (unReads) => set({ unReads }),
  addUnRead: (channelId) =>
    set((state) => ({ unReads: [...state.unReads, channelId] })),
  removeUnRead: (channelId) =>
    set((state) => ({
      unReads: state.unReads.filter((id) => id !== channelId),
    })),
  addMessage: (message, unread) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [message.channel_id]: [...state.messages[message.channel_id], message],
      },
      unReads: unread
        ? [...state.unReads, message.channel_id]
        : [...state.unReads],
    })),

  removeMessage: (message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [message.channel_id]: state.messages[message.channel_id].filter(
          (m) => m.id !== message.id
        ),
      },
    })),
  getMessages: (channelId) => {
    if (!channelId) {
      return [];
    }
    const messages = get().messages[channelId];
    if (!messages) {
      get().fetchChannelMessages(channelId);
    }
    return messages;
  },
  fetchChannelMessages: async (channelId) => {
    try {
      const messages = await getChannelMessages(channelId);
      set((state) => ({
        messages: { ...state.messages, [channelId]: messages },
      }));
    } catch (error) {
      console.error(" Failed to fetch channel messages", error);
    }
  },

  initialize: async () => {
    try {
      const channels = await getUserDMChannels();
      set({ channels });
    } catch (error) {
      console.error(" Failed to initialize messages", error);
    }
  },
}));

eventBus.on(EventType.MESSAGE, (event: EventPayload) => {
  const currentDmId = window.location.pathname.split("/").pop() ?? "";
  const isUnread = currentDmId !== event.receiver_id;
  useMessageStore.getState().addMessage(
    {
      id: event.event_id,
      content: event.text,
      sender_id: event.sender_id,
      channel_id: event.receiver_id,
      created_at: event.timestamp,
    },
    isUnread
  );
});
