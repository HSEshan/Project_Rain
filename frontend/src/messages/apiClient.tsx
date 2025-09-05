import apiClient from "../utils/apiClientBase";
import { type DMChannel, type Message } from "./types";

export const getUserDMChannels = async (): Promise<DMChannel[]> => {
  const response = await apiClient.get(`/channels/dms/me`);
  return response.data;
};

export const getChannelMessages = async (
  channelId: string
): Promise<Message[]> => {
  try {
    const response = await apiClient.get(`/messages/${channelId}`);
    return response.data;
  } catch (error) {
    console.error(" Failed to fetch channel messages", error);
    return [];
  }
};
