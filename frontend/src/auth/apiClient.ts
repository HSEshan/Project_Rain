import { type AxiosResponse } from "axios";
import apiClient from "../utils/apiClientBase";

/**
 * Both of these deliberately let the axios error through untouched.
 *
 * They used to catch it and rethrow `new Error("User already exists")`, which
 * reads like an improvement and is the opposite: the new error carries no
 * `response`, so `errorText` could not see the status or the server's `detail`
 * and fell through to its no-response branch. Every failed signup and login
 * said "Cannot reach the server. Check your connection.", including a taken
 * username and a password that failed validation.
 *
 * The transport layer's job is to make the request. Deciding what a person
 * should read about a 409 belongs in one place, `shared/errors.ts`, not spread
 * across every api client that happens to know a status code.
 */

export const postLogin = async (
  username: string,
  password: string
): Promise<AxiosResponse> =>
  apiClient.post(
    "/auth/login",
    new URLSearchParams({ username, password }),
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
  );

export const postSignup = async (
  username: string,
  email: string,
  password: string
): Promise<AxiosResponse> =>
  apiClient.post("/auth/register", { username, email, password });

/**
 * End the session on the server as well as in this browser.
 *
 * Swallows everything. Sign-out is the one action a user must never be told
 * failed: the local half has already happened by the time this settles, the
 * server half is a revocation they cannot retry, and an error toast on the way
 * to the login screen would be pure noise. The refresh cookie is httpOnly, so
 * this request is the only way to reach it.
 */
export const postLogout = async (): Promise<void> => {
  try {
    await apiClient.post("/auth/logout");
  } catch {
    // Offline, or a session that was already over. Nothing to do either way.
  }
};
