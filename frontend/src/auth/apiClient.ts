import { AxiosError, type AxiosResponse } from "axios";
import apiClient from "../utils/apiClientBase";

export const postLogin = async (
  username: string,
  password: string
): Promise<AxiosResponse> => {
  try {
    const res = await apiClient.post(
      "/auth/login",
      new URLSearchParams({
        username: username,
        password: password,
      }),
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      }
    );
    return res;
  } catch (err: unknown) {
    console.error("Failed to login", err);
    if (err instanceof AxiosError) {
      if (err.response?.status === 404) {
        throw new Error("User not found");
      }
      if (err.response?.status === 401) {
        throw new Error("Incorrect password");
      }
    }
    throw new Error("An unknown error occurred, " + err);
  }
};

export const postSignup = async (
  username: string,
  email: string,
  password: string
): Promise<AxiosResponse> => {
  try {
    const res = await apiClient.post("/auth/register", {
      username,
      email,
      password,
    });
    return res;
  } catch (err: unknown) {
    if (err instanceof AxiosError) {
      if (err.response?.status === 409) {
        throw new Error("User already exists");
      }
    }
    if (err instanceof AxiosError) {
      if (err.response?.status === 400) {
        throw new Error("Invalid credentials");
      }
    }
    throw new Error("An unknown error occurred, " + err);
  }
};
