import { create } from "zustand";
import type { ChannelMember } from "../shared/types";
import { getChannelMembers } from "../shared/channelApiClient";
import { eventBus } from "../utils/EventBus";
import { onResync } from "../shared/resync";
import { EventAction, EventType, type EventPayload } from "../utils/eventType";

/**
 * Rosters for group DMs, keyed by channel.
 *
 * Separate from `channelStore.participants` on purpose: that map holds ids and
 * deliberately leaves the current user out, because it exists to title a DM
 * ("alice, bob"). A group's member panel has to show everyone, with usernames
 * and who owns the room, so it reads the real roster endpoint.
 */
interface GroupDMStore {
  members: Record<string, ChannelMember[]>;
  loading: Record<string, boolean>;

  getMembers: (channelId: string) => ChannelMember[];
  setMembers: (channelId: string, members: ChannelMember[]) => void;
  fetchMembers: (channelId: string) => Promise<void>;
  forget: (channelId: string) => void;
  reset: () => void;
}

export const useGroupDMStore = create<GroupDMStore>((set, get) => ({
  members: {},
  loading: {},

  getMembers: (channelId) => get().members[channelId] ?? [],

  setMembers: (channelId, members) =>
    set((state) => ({ members: { ...state.members, [channelId]: members } })),

  fetchMembers: async (channelId) => {
    if (get().loading[channelId]) return;
    set((state) => ({ loading: { ...state.loading, [channelId]: true } }));
    try {
      get().setMembers(channelId, await getChannelMembers(channelId));
    } catch (error) {
      console.error("Failed to fetch group members", error);
    } finally {
      set((state) => ({ loading: { ...state.loading, [channelId]: false } }));
    }
  },

  forget: (channelId) =>
    set((state) => {
      const members = { ...state.members };
      delete members[channelId];
      return { members };
    }),

  reset: () => set({ members: {}, loading: {} }),
}));

/**
 * Someone joined, left or renamed a group we are in. The event carries the
 * channel, not the new roster: re-reading it is one request and is right even
 * when two changes land at once, which patching a local array is not.
 */
eventBus.on(EventType.NOTIFICATION, (event: EventPayload) => {
  const metadata = event.metadata as
    | { action?: string; channel_id?: string }
    | undefined;
  if (metadata?.action !== EventAction.GROUP_DM_UPDATED) return;
  if (!metadata.channel_id) return;
  // Only for groups already on screen. Fetching a roster nobody is looking at
  // would be a request per event for every group the user is in.
  if (!useGroupDMStore.getState().members[metadata.channel_id]) return;
  void useGroupDMStore.getState().fetchMembers(metadata.channel_id);
});

// Roster changes that happened while the socket was down arrive as nothing at
// all, so a reconnect has to re-read every roster being shown.
onResync(() => {
  Object.keys(useGroupDMStore.getState().members).forEach((channelId) => {
    void useGroupDMStore.getState().fetchMembers(channelId);
  });
});
