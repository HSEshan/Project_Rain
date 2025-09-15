import apiClient from "../utils/apiClientBase";
import type { Message } from "./types";

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
