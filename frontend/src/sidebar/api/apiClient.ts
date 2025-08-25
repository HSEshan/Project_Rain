import apiClient from "../../utils/apiClientBase";

export async function fetchUserGuilds(): Promise<any> {
  const response = await apiClient.get("/guilds/me");
  return response.data;
}

export async function fetchGuildById(guildId: string): Promise<any> {
  const response = await apiClient.get(`/guilds/${guildId}`);
  return response.data;
}
