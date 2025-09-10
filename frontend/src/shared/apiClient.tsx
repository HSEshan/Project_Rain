import apiClient from "../utils/apiClientBase";
import type { AxiosResponse } from "axios";

export type BulkUserRequest = {
  ids: string[];
};

export const getUsers = async (
  request: BulkUserRequest
): Promise<AxiosResponse> => {
  try {
    const response = await apiClient.post("/users/bulk", request);
    return response;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to get users");
  }
};
