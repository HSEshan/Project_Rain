import { create } from "zustand";
import type { Attachment, Message } from "./types";
import { getChannelMessages } from "./messageApiClient";
import { eventBus } from "../utils/EventBus";
import { onResync } from "./resync";
import {
  EventAction,
  EventType,
  eventTargetId,
  type EventPayload,
} from "../utils/eventType";

interface MessageStore {
  messages: Record<string, Message>; // messageId -> Message object
  byChannel: Record<string, string[]>; // channelId -> [messageIds]

  addMultipleMessages: (channelId: string, msgs: Message[]) => void;
  addMessage: (msg: Message) => void;
  getChannelMessages: (channelId: string) => Message[];
  updateMessage: (messageId: string, changes: Partial<Message>) => void;
  removeMessage: (messageId: string) => void;
  clearChannelMessages: (channelId: string) => void;
  clearAllMessages: () => void;

  fetchChannelMessages: (channelId: string) => void;
}

const REFETCH_MARGIN_MS = 5000;

// created_at is an ISO string; ties are broken by id so ordering is stable
const sortByCreatedAt = (ids: string[], messages: Record<string, Message>) =>
  [...ids].sort((a, b) => {
    const diff =
      Date.parse(messages[a].created_at) - Date.parse(messages[b].created_at);
    return diff !== 0 ? diff : messages[a].id.localeCompare(messages[b].id);
  });

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

      newByChannel[channelId] = sortByCreatedAt(mergedIds, newMessages);

      return { messages: newMessages, byChannel: newByChannel };
    }),

  addMessage: (msg) =>
    set((state) => {
      // REST hydration and the WS echo can both deliver the same message
      if (state.messages[msg.id]) return state;

      const newMessages = { ...state.messages, [msg.id]: msg };
      const existingIds = state.byChannel[msg.channel_id] ?? [];
      return {
        messages: newMessages,
        byChannel: {
          ...state.byChannel,
          [msg.channel_id]: sortByCreatedAt(
            [...existingIds, msg.id],
            newMessages
          ),
        },
      };
    }),

  getChannelMessages: (channelId) => {
    const state = get();
    const ids = state.byChannel[channelId] ?? [];
    return ids.map((id) => state.messages[id]);
  },

  updateMessage: (messageId, changes) =>
    set((state) => {
      const message = state.messages[messageId];
      if (!message) return state;
      return {
        messages: {
          ...state.messages,
          [messageId]: { ...message, ...changes },
        },
      };
    }),

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
    // History is the whole channel, so anything clearly older than its newest row
    // that it no longer has was deleted, most likely while the socket was down.
    // "Clearly" because a live message arriving as this was answered is absent
    // for an innocent reason, and it is stamped at ingest where a row is stamped
    // at insert. A deletion inside the margin has its own event, or the next
    // fetch. Sorted oldest first, and empty when the fetch failed.
    const newest = response[response.length - 1]?.created_at;
    if (newest) {
      const cutoff = Date.parse(newest) - REFETCH_MARGIN_MS;
      const present = new Set(response.map((m) => m.id));
      get()
        .getChannelMessages(channel_id)
        .filter((m) => !present.has(m.id) && Date.parse(m.created_at) < cutoff)
        .forEach((m) => get().removeMessage(m.id));
    }
    get().addMultipleMessages(channel_id, response);
  },
}));

eventBus.on(EventType.MESSAGE, (event: EventPayload) => {
  // The gateway rewrites a message's metadata to carry exactly the attachments
  // it claimed, as the same objects the history endpoint returns.
  const metadata = event.metadata as { attachments?: Attachment[] } | undefined;
  useMessageStore.getState().addMessage({
    id: event.event_id,
    content: event.text,
    sender_id: event.sender_id,
    channel_id: eventTargetId(event),
    created_at: event.timestamp,
    attachments: metadata?.attachments ?? [],
  });
});

eventBus.on(EventType.MESSAGE_UPDATE, (event: EventPayload) => {
  const metadata = event.metadata as
    | { action?: string; message_id?: string; edited_at?: string }
    | undefined;
  if (!metadata?.message_id) return;

  if (metadata.action === EventAction.MESSAGE_DELETED) {
    useMessageStore.getState().removeMessage(metadata.message_id);
  } else if (metadata.action === EventAction.MESSAGE_EDITED) {
    useMessageStore.getState().updateMessage(metadata.message_id, {
      content: event.text,
      edited_at: metadata.edited_at,
    });
  }
});

/**
 * Refetch every channel this session has actually opened. `byChannel` is the
 * right scope: it is exactly the set the user can currently see stale, and it
 * does not grow with the size of the account.
 */
onResync(() => {
  const channelIds = Object.keys(useMessageStore.getState().byChannel);
  channelIds.forEach((channelId) => {
    void useMessageStore.getState().fetchChannelMessages(channelId);
  });
});
