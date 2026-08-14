import type { AxiosResponse } from "axios";
import apiClient from "../utils/apiClientBase";
import type { ChannelType } from "../shared/types";
import { type Guild, type GuildMember } from "./types";

export const getUserGuilds = async (): Promise<Guild[]> => {
  const response = await apiClient.get("/guilds/me");
  return response.data;
};

export const getGuildMembers = async (
  guildId: string
): Promise<GuildMember[]> => {
  const response = await apiClient.get(`/guilds/${guildId}/members`);
  return response.data;
};

export type GuildChannelCreate = {
  name: string;
  type: ChannelType;
  description?: string;
};

export const postCreateGuildChannel = async (
  guildId: string,
  channel: GuildChannelCreate
): Promise<AxiosResponse> => {
  return await apiClient.post(`/channels/guild/${guildId}`, channel);
};

export type GuildCreate = {
  name: string;
  description: string;
};

export const postCreateGuild = async (
  guild: GuildCreate
): Promise<AxiosResponse> => {
  try {
    const res = await apiClient.post("/guilds/", guild);
    return res;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to create guild");
  }
};
