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

/** Mirrors BIO_MAX_LENGTH in `libs.db`, which is where the real cap lives. */
export const BIO_MAX_LENGTH = 190;

export type UserProfile = {
  id: string;
  username: string;
  /** Null when nobody has written one. Never HTML, and never rendered as any. */
  bio: string | null;
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

/**
 * Change your own profile. There is no route for changing anyone else's.
 *
 * Sends only the fields being changed, which is what `PATCH` means and what the
 * server reads: omitting `bio` leaves it alone, sending `null` clears it. The
 * updated profile comes back rather than a bare 204, because the person who
 * made the change is the one client rest_api does *not* send an event to.
 */
export const updateMyProfile = async (update: {
  bio?: string | null;
}): Promise<UserProfile> => {
  const response = await apiClient.patch("/users/me", update);
  return response.data;
};
