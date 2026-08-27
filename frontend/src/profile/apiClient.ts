import apiClient from "../utils/apiClientBase";

export enum FriendState {
  SELF = "self",
  FRIENDS = "friends",
  REQUEST_SENT = "request_sent",
  REQUEST_RECEIVED = "request_received",
  NONE = "none",
}

export type MutualGuild = {
  id: string;
  name: string;
};

export type UserProfile = {
  id: string;
  username: string;
  created_at: string;
  friend_state: FriendState;
  /** An existing two-person DM, if there is one. Never a group. */
  dm_channel_id: string | null;
  mutual_guilds: MutualGuild[];
};

export const getUserProfile = async (userId: string): Promise<UserProfile> => {
  const response = await apiClient.get(`/users/${userId}/profile`);
  return response.data;
};
