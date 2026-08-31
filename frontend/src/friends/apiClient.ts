import { type AxiosResponse } from "axios";
import apiClient from "../utils/apiClientBase";
import type { FriendRequest } from "./friendStore";
import type { User } from "../shared/userStore";

/**
 * Axios errors propagate untouched, for the same reason they do in
 * `auth/apiClient.ts`: rethrowing `new Error("...")` drops `.response`, and
 * `errorText` then has no status and no `detail` to work with and reports that
 * the server is unreachable. The server already says "A friend request is
 * already pending" and "User not found"; nothing here needs to guess.
 */

export const getUserFriendRequests = async (): Promise<
  AxiosResponse<FriendRequest[]>
> => apiClient.get("/friendship/friends/request/me");

export const getOutgoingFriendRequests = async (): Promise<FriendRequest[]> => {
  const response = await apiClient.get("/friendship/friends/request/outgoing");
  return response.data;
};

export const getFriends = async (): Promise<User[]> => {
  const response = await apiClient.get("/friendship/friends/me");
  return response.data;
};

export const createFriendRequest = async (
  to_user_name: string
): Promise<AxiosResponse<FriendRequest>> =>
  apiClient.post(
    `/friendship/friends/request?to_username=${encodeURIComponent(
      to_user_name
    )}`
  );

export type FriendRequestAccepted = {
  friend_id: string;
  dm_channel_id: string;
};

export const acceptFriendRequest = async (
  friend_request_id: string
): Promise<AxiosResponse<FriendRequestAccepted>> =>
  apiClient.post(`/friendship/friends/request/${friend_request_id}/accept`);

export const rejectFriendRequest = async (
  friend_request_id: string
): Promise<AxiosResponse> =>
  apiClient.post(`/friendship/friends/request/${friend_request_id}/reject`);
