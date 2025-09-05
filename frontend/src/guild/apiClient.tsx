import apiClient from "../utils/apiClientBase";
import { type Guild } from "./types";

export const getUserGuilds = async (): Promise<Guild[]> => {
  const response = await apiClient.get("/guilds/me");
  return response.data;
};
