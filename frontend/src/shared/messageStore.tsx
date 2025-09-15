import { create } from "zustand";
import type { Message } from "./types";
import { getChannelMessages } from "./messageApiClient";
import { eventBus } from "../utils/EventBus";
import { EventType, type EventPayload } from "../utils/eventType";

interface MessageStore {
  messages: Record<string, Message>; // messageId -> message
  byChannel: Record<string, string[]>; // channelId -> [messageIds]

  addMultipleMessages: (channelId: string, msgs: Message[]) => void;
  addMessage: (msg: Message) => void;
  getChannelMessages: (channelId: string) => Message[];
  removeMessage: (messageId: string) => void;
  clearChannelMessages: (channelId: string) => void;
  clearAllMessages: () => void;

  fetchChannelMessages: (channelId: string) => void;
}

export const useMessageStore = create<MessageStore>((set, get) => ({
  messages: {},
  byChannel: {},

  addMultipleMessages: (channelId, msgs) =>
    set((state) => {
      const newMessages = { ...state.messages };
      const newByChannel = { ...state.byChannel };

      msgs.forEach((m) => {
        newMessages[m.id] = m;
      });

      const existingIds = newByChannel[channelId] ?? [];
      const mergedIds = [
        ...new Set([...existingIds, ...msgs.map((m) => m.id)]),
      ];

      newByChannel[channelId] = mergedIds.sort(
        (a, b) =>
          (newMessages[a].created_at as unknown as number) -
          (newMessages[b].created_at as unknown as number)
      );

      return { messages: newMessages, byChannel: newByChannel };
    }),

  addMessage: (msg) =>
    set((state) => {
      const newMessages = { ...state.messages, [msg.id]: msg };
      const existingIds = state.byChannel[msg.channel_id] ?? [];
      return {
        messages: newMessages,
        byChannel: {
          ...state.byChannel,
          [msg.channel_id]: [...existingIds, msg.id],
        },
      };
    }),

  getChannelMessages: (channelId) => {
    const state = get();
    const ids = state.byChannel[channelId] ?? [];
    return ids.map((id) => state.messages[id]);
  },

  removeMessage: (messageId) =>
    set((state) => {
      const newMessages = { ...state.messages };
      const msg = newMessages[messageId];
      if (!msg) return state;

      delete newMessages[messageId];

      const newByChannel = { ...state.byChannel };
      newByChannel[msg.channel_id] = (
        newByChannel[msg.channel_id] ?? []
      ).filter((id) => id !== messageId);

      return { messages: newMessages, byChannel: newByChannel };
    }),

  clearChannelMessages: (channelId) => {
    set((state) => {
      const newByChannel = { ...state.byChannel };
      const idsToDelete = newByChannel[channelId] ?? [];
      const newMessages = { ...state.messages };

      idsToDelete.forEach((id) => {
        delete newMessages[id];
      });

      delete newByChannel[channelId];
      return { messages: newMessages, byChannel: newByChannel };
    });
  },

  clearAllMessages: () => set({ messages: {}, byChannel: {} }),

  fetchChannelMessages: async (channel_id: string) => {
    const response = await getChannelMessages(channel_id);
    get().addMultipleMessages(channel_id, response);
  },
}));

eventBus.on(EventType.MESSAGE, (event: EventPayload) => {
  useMessageStore.getState().addMessage({
    id: event.event_id,
    content: event.text,
    sender_id: event.sender_id,
    channel_id: event.receiver_id,
    created_at: event.timestamp,
  });
});
