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

export type GuildInvite = {
  invite_id: string;
  guild_id: string;
  guild_name: string;
  /** Null for invites predating the column, or if that account is gone. */
  inviter_id: string | null;
  inviter_username: string | null;
  expires_at: string;
};

/** Invite by username (what a person types) or by id (a friend you picked). */
export const postGuildInvite = async (
  guildId: string,
  target: { username: string } | { user_id: string }
): Promise<AxiosResponse> => {
  return await apiClient.post(`/guilds/${guildId}/invite`, target);
};

export const getMyGuildInvites = async (): Promise<GuildInvite[]> => {
  const response = await apiClient.get("/guilds/invites/me");
  return response.data;
};

export const postAcceptGuildInvite = async (
  guildId: string,
  inviteId: string
): Promise<AxiosResponse> => {
  return await apiClient.post(`/guilds/${guildId}/invites/${inviteId}/accept`);
};

export const deleteGuildInvite = async (
  guildId: string,
  inviteId: string
): Promise<AxiosResponse> => {
  return await apiClient.delete(`/guilds/${guildId}/invites/${inviteId}`);
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
