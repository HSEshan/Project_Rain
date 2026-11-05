import type { AxiosResponse } from "axios";
import apiClient from "../utils/apiClientBase";
import type { ChannelType } from "../shared/types";
import { type Guild, type GuildMember, type GuildMemberRole } from "./types";

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

export const patchGuild = async (
  guildId: string,
  update: { name?: string; description?: string }
): Promise<Guild> => {
  const response = await apiClient.patch(`/guilds/${guildId}`, update);
  return response.data;
};

export const deleteGuild = async (guildId: string): Promise<void> => {
  await apiClient.delete(`/guilds/${guildId}`);
};

export const patchGuildMemberRole = async (
  guildId: string,
  userId: string,
  role: GuildMemberRole
): Promise<GuildMember> => {
  const response = await apiClient.patch(
    `/guilds/${guildId}/members/${userId}`,
    { role }
  );
  return response.data;
};

export const deleteGuildMember = async (
  guildId: string,
  userId: string
): Promise<void> => {
  await apiClient.delete(`/guilds/${guildId}/members/${userId}`);
};

export type GuildBan = { user_id: string; username: string; created_at: string };

export const postGuildBan = async (
  guildId: string,
  userId: string
): Promise<void> => {
  await apiClient.post(`/guilds/${guildId}/bans/${userId}`);
};

export const getGuildBans = async (guildId: string): Promise<GuildBan[]> => {
  const response = await apiClient.get(`/guilds/${guildId}/bans`);
  return response.data;
};

export const deleteGuildBan = async (
  guildId: string,
  userId: string
): Promise<void> => {
  await apiClient.delete(`/guilds/${guildId}/bans/${userId}`);
};

export const deleteLeaveGuild = async (guildId: string): Promise<void> => {
  await apiClient.delete(`/guilds/${guildId}/members/me`);
};

export const postTransferGuild = async (
  guildId: string,
  userId: string
): Promise<Guild> => {
  const response = await apiClient.post(`/guilds/${guildId}/transfer`, {
    user_id: userId,
  });
  return response.data;
};

export type InviteLink = {
  code: string;
  guild_id: string;
  /** Null once the account that made it is gone. */
  creator_id: string | null;
  max_uses: number | null;
  uses: number;
  expires_at: string | null;
  created_at: string;
};

export type InviteLinkPreview = {
  guild_name: string;
  guild_description: string;
  icon_url: string | null;
  member_count: number;
};

export const getInviteLinks = async (
  guildId: string
): Promise<InviteLink[]> => {
  const response = await apiClient.get(`/guilds/${guildId}/invite-links`);
  return response.data;
};

export const postInviteLink = async (
  guildId: string,
  options: { expires_in_hours: number | null; max_uses: number | null }
): Promise<InviteLink> => {
  const response = await apiClient.post(
    `/guilds/${guildId}/invite-links`,
    options
  );
  return response.data;
};

export const deleteInviteLink = async (
  guildId: string,
  code: string
): Promise<void> => {
  await apiClient.delete(`/guilds/${guildId}/invite-links/${code}`);
};

export const getInviteLinkPreview = async (
  code: string
): Promise<InviteLinkPreview> => {
  const response = await apiClient.get(`/invites/${encodeURIComponent(code)}`);
  return response.data;
};

export const postAcceptInviteLink = async (
  code: string
): Promise<{ guild_id: string; already_member: boolean }> => {
  const response = await apiClient.post(
    `/invites/${encodeURIComponent(code)}/accept`
  );
  return response.data;
};

export const deleteGuildChannel = async (channelId: string): Promise<void> => {
  await apiClient.delete(`/channels/${channelId}`);
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
