import { AxiosError } from "axios";
import apiClient from "../utils/apiClientBase";

export type DemoStatus = {
  enabled: boolean;
  username?: string | null;
  notice?: string | null;
};

export type DemoSession = {
  access_token: string;
  token_type: string;
  username: string;
  notice: string;
};

/**
 * Whether this deployment offers a demo account.
 *
 * Asked before the button is rendered, so a private deployment shows nothing
 * rather than a control that fails when clicked. A network failure is treated
 * as "not available" for the same reason.
 */
export const getDemoStatus = async (): Promise<DemoStatus> => {
  try {
    const res = await apiClient.get<DemoStatus>("/demo/status");
    return res.data;
  } catch {
    return { enabled: false };
  }
};

/** Reset the shared demo account and return a token for it. */
export const postDemoLogin = async (): Promise<DemoSession> => {
  try {
    const res = await apiClient.post<DemoSession>("/demo/login");
    return res.data;
  } catch (err: unknown) {
    if (err instanceof AxiosError && err.response?.status === 503) {
      throw new Error("The demo is not enabled on this server");
    }
    throw new Error("Could not start the demo. Please try again.");
  }
};
