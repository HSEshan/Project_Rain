import apiClient from "../utils/apiClientBase";
import type { AxiosResponse } from "axios";

export const getUsers = async (ids: string[]): Promise<AxiosResponse> => {
  try {
    const response = await apiClient.post("/users/bulk", { ids });
    return response;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to get users");
  }
};
