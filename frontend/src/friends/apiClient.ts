import { AxiosError, type AxiosResponse } from "axios";
import apiClient from "../utils/apiClientBase";
import type { FriendRequest } from "./friendStore";
import type { User } from "../shared/userStore";

export const getUserFriendRequests = async (): Promise<
  AxiosResponse<FriendRequest[]>
> => {
  try {
    const response = await apiClient.get("/friendship/friends/request/me");
    return response;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to get user friend requests");
  }
};

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
): Promise<AxiosResponse<FriendRequest>> => {
  try {
    const response = await apiClient.post(
      `/friendship/friends/request?to_username=${to_user_name}`
    );
    return response;
  } catch (error) {
    if (error instanceof AxiosError) {
      if (error.response?.status === 404) {
        throw new Error(`User "${to_user_name}" not found`);
      }
      if (error.response?.status === 409) {
        throw new Error("You are already friends with this user");
      }
    }
    throw new Error("Failed to create friend request");
  }
};

export type FriendRequestAccepted = {
  friend_id: string;
  dm_channel_id: string;
};

export const acceptFriendRequest = async (
  friend_request_id: string
): Promise<AxiosResponse<FriendRequestAccepted>> => {
  try {
    const response = await apiClient.post(
      `/friendship/friends/request/${friend_request_id}/accept`
    );
    return response;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to accept friend request");
  }
};

export const rejectFriendRequest = async (
  friend_request_id: string
): Promise<AxiosResponse> => {
  try {
    const response = await apiClient.post(
      `/friendship/friends/request/${friend_request_id}/reject`
    );
    return response;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to reject friend request");
  }
};
