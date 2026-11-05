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

export const patchMessage = async (
  messageId: string,
  content: string
): Promise<Message> => {
  const response = await apiClient.patch(`/messages/${messageId}`, { content });
  return response.data;
};

export const deleteMessage = async (messageId: string): Promise<void> => {
  await apiClient.delete(`/messages/${messageId}`);
};
