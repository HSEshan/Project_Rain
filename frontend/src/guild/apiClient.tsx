import type { AxiosResponse } from "axios";
import apiClient from "../utils/apiClientBase";
import { type Guild } from "./types";

export const getUserGuilds = async (): Promise<Guild[]> => {
  const response = await apiClient.get("/guilds/me");
  return response.data;
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
