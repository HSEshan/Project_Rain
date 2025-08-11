import apiClient from "../../utils/apiClientBase";

export async function fetchUserGuilds(): Promise<any> {
  return apiClient.get("/guilds/me");
}
