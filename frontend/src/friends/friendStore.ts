import { create } from "zustand";
import {
  getUserFriendRequests,
  getOutgoingFriendRequests,
  getFriends,
} from "./apiClient";
import type { User } from "../shared/userStore";
import { eventBus } from "../utils/EventBus";
import { EventType, type EventPayload } from "../utils/eventType";
import { useUserStore } from "../shared/userStore";

export interface FriendRequest {
  id: string;
  from_user_id: string;
  to_user_id: string;
  created_at: string;
}

export interface FriendStore {
  friends: User[];
  friendRequests: FriendRequest[]; // incoming
  outgoingRequests: FriendRequest[];

  setFriendRequests: (friendRequests: FriendRequest[]) => void;
  addFriendRequest: (friendRequest: FriendRequest) => void;
  removeFriendRequest: (id: string) => void;

  isModalOpen: boolean;
  setIsModalOpen: (isModalOpen: boolean) => void;

  fetchFriends: () => Promise<void>;
  fetchFriendRequests: () => Promise<void>;
  fetchOutgoingRequests: () => Promise<void>;
  reset: () => void;
}

export const useFriendStore = create<FriendStore>((set) => ({
  friends: [],
  friendRequests: [],
  outgoingRequests: [],

  setFriendRequests: (friendRequests) => set({ friendRequests }),
  addFriendRequest: (friendRequest) =>
    set((state) =>
      state.friendRequests.some((r) => r.id === friendRequest.id)
        ? state
        : { friendRequests: [...state.friendRequests, friendRequest] }
    ),
  removeFriendRequest: (id) =>
    set((state) => ({
      friendRequests: state.friendRequests.filter(
        (friendRequest) => friendRequest.id !== id
      ),
    })),

  isModalOpen: false,
  setIsModalOpen: (isModalOpen) => set({ isModalOpen }),

  fetchFriends: async () => {
    try {
      set({ friends: await getFriends() });
    } catch (error) {
      console.error("Failed to fetch friends:", error);
    }
  },
  fetchFriendRequests: async () => {
    const friendRequests = await getUserFriendRequests();
    set({ friendRequests: friendRequests.data });
  },
  fetchOutgoingRequests: async () => {
    try {
      set({ outgoingRequests: await getOutgoingFriendRequests() });
    } catch (error) {
      console.error("Failed to fetch outgoing friend requests:", error);
    }
  },

  reset: () =>
    set({
      friends: [],
      friendRequests: [],
      outgoingRequests: [],
      isModalOpen: false,
    }),
}));

// A friend request arriving over the websocket should show up without a reload.
eventBus.on(EventType.FRIEND_REQUEST, (event: EventPayload) => {
  const metadata = event.metadata as
    | { request_id?: string; from_username?: string }
    | undefined;
  if (!metadata?.request_id) return;

  useFriendStore.getState().addFriendRequest({
    id: metadata.request_id,
    from_user_id: event.sender_id,
    to_user_id: event.receiver_id,
    created_at: event.timestamp,
  });

  if (metadata.from_username) {
    useUserStore
      .getState()
      .mergeUsers([{ id: event.sender_id, username: metadata.from_username }]);
  }
});

// The other side accepting is the only way a sent request disappears without
// this tab doing anything, so refresh both lists when it happens.
eventBus.on(EventType.NOTIFICATION, (event: EventPayload) => {
  const metadata = event.metadata as
    | { action?: string; friend_id?: string; friend_username?: string }
    | undefined;
  if (metadata?.action !== "friend_request_accepted") return;

  if (metadata.friend_id && metadata.friend_username) {
    useUserStore
      .getState()
      .mergeUsers([
        { id: metadata.friend_id, username: metadata.friend_username },
      ]);
  }
  useFriendStore.getState().fetchFriends();
  useFriendStore.getState().fetchOutgoingRequests();
});
