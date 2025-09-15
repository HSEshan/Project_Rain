import apiClient from "../utils/apiClientBase";
import type { Channel } from "./types";

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
