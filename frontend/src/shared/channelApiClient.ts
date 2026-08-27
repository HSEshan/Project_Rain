import apiClient from "../utils/apiClientBase";
import type { Channel, ChannelMember } from "./types";

export const getUserChannels = async (): Promise<Channel[]> => {
  try {
    const response = await apiClient.get("/channels/me");
    return response.data;
  } catch (error) {
    console.error(" Failed to fetch user channels", error);
    return [];
  }
};

export type ChannelParticipantResponse = Record<string, string[]>;

export const getChannelParticipants = async (
  channelIds: string[]
): Promise<ChannelParticipantResponse> => {
  try {
    const response = await apiClient.post(
      `/channels/bulk/participants`,
      channelIds
    );
    return response.data;
  } catch (error) {
    console.error(" Failed to fetch channel participants", error);
    return {};
  }
};

/** One channel's current metadata. Used after a group DM is renamed. */
export const getChannel = async (channelId: string): Promise<Channel | null> => {
  try {
    const response = await apiClient.get(`/channels/${channelId}`);
    return response.data;
  } catch (error) {
    console.error(" Failed to fetch channel", error);
    return null;
  }
};

/**
 * The full roster including yourself, unlike `getChannelParticipants`, which
 * leaves the caller out because it exists to title a DM.
 */
export const getChannelMembers = async (
  channelId: string
): Promise<ChannelMember[]> => {
  const response = await apiClient.get(`/channels/${channelId}/members`);
  return response.data.members;
};

/**
 * These four throw rather than swallowing. They are mutations the user is
 * watching happen, and a silent failure leaves the UI asserting something that
 * did not happen. The read helpers above are the opposite case: a failed
 * refresh should leave the last known state on screen.
 */
export const createGroupDM = async (
  userIds: string[],
  name?: string
): Promise<Channel> => {
  const response = await apiClient.post("/channels/group", {
    user_ids: userIds,
    name: name?.trim() || null,
  });
  return response.data;
};

export const addGroupDMMember = async (
  channelId: string,
  userId: string
): Promise<ChannelMember[]> => {
  const response = await apiClient.post(`/channels/${channelId}/members`, {
    user_id: userId,
  });
  return response.data.members;
};

export const renameGroupDM = async (
  channelId: string,
  name: string
): Promise<Channel> => {
  const response = await apiClient.patch(`/channels/${channelId}`, { name });
  return response.data;
};

export const leaveGroupDM = async (channelId: string): Promise<void> => {
  await apiClient.delete(`/channels/${channelId}/members/me`);
};
