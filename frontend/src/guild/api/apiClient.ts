import apiClient from "../../utils/apiClientBase";
import type { Guild } from "../types/guild";

export async function fetchUserGuilds(): Promise<Guild[]> {
  return apiClient.get("/guilds/me");
}
