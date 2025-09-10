import { create } from "zustand";
import { getUserFriendRequests } from "./apiClient";

export interface FriendRequest {
  id: string;
  from_user_id: string;
  to_user_id: string;
  created_at: string;
}

export interface FriendRequestStore {
  friendRequests: FriendRequest[];
  setFriendRequests: (friendRequests: FriendRequest[]) => void;
  addFriendRequests: (friendRequests: FriendRequest[]) => void;
  removeFriendRequest: (id: string) => void;
  isModalOpen: boolean;
  setIsModalOpen: (isModalOpen: boolean) => void;
  initialize: () => void;
}

export const useFriendRequestStore = create<FriendRequestStore>((set) => ({
  friendRequests: [],
  setFriendRequests: (friendRequests) => set({ friendRequests }),
  addFriendRequests: (friendRequests) =>
    set((state) => ({
      friendRequests: [...state.friendRequests, ...friendRequests],
    })),
  removeFriendRequest: (id) =>
    set((state) => ({
      friendRequests: state.friendRequests.filter(
        (friendRequest) => friendRequest.id !== id
      ),
    })),
  isModalOpen: false,
  setIsModalOpen: (isModalOpen) => set({ isModalOpen }),
  initialize: async () => {
    const friendRequests = await getUserFriendRequests();
    set({ friendRequests: friendRequests.data });
  },
}));
