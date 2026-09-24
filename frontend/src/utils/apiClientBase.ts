import axios, { type InternalAxiosRequestConfig } from "axios";
import { emitSessionExpired } from "../shared/session";
import { refreshSession } from "../auth/refresh";
import { readToken } from "../auth/tokenStore";

const apiUrl = "/api";

const apiClient = axios.create({
  baseURL: apiUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add Authorization header if token exists
apiClient.interceptors.request.use(
  (config) => {
    // The cookie rather than React state, so a request built before a renewal
    // lands still carries the token that renewal wrote.
    const token = readToken();
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Routes where a 401 is an answer, not an expiry.
 *
 * Signing in with the wrong password is a 401 and must leave the form alone.
 * Without this, one typo on the login screen would "expire" a session that had
 * not started and bounce the user to the page they are already on. `/auth/logout`
 * is here for the opposite reason: a 401 from it means the session was already
 * gone, which is the outcome it was asking for.
 */
const AUTH_ROUTES = [
  "/auth/login",
  "/auth/register",
  "/auth/logout",
  "/demo/login",
];

/** Marks a request that has already been retried once after a refresh. */
type RetriableConfig = InternalAxiosRequestConfig & { _retriedAfterRefresh?: boolean };

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    const config: RetriableConfig | undefined = error?.config;
    const url: string = config?.url ?? "";
    const isAuthRoute = AUTH_ROUTES.some((route) => url.startsWith(route));

    /**
     * A 401 is no longer proof that the session is over.
     *
     * With refresh rotation the ordinary cause is an access token that reached
     * the end of its hour while the app was idle, and the fix is a renewal the
     * user never sees. So: renew, replay the request that failed, and only
     * declare the session over when the renewal itself is refused. Retried at
     * most once — `refreshSession` returning a token and the retry 401ing again
     * means something other than expiry, and a loop between the two would hide
     * it behind an infinite refresh.
     *
     * `refreshSession` collapses concurrent callers, so the six requests a
     * freshly loaded page has in the air produce one refresh between them.
     */
    if (status === 401 && !isAuthRoute && config && !config._retriedAfterRefresh) {
      config._retriedAfterRefresh = true;
      // `force`, because the server has just contradicted the client's only
      // evidence. An unforced renewal judges the token by its own `exp` and
      // returns it unchanged when that still looks fine — so a token the
      // *server* rejects but the *browser* believes in renews nothing, the
      // retry fails identically, and the session ends with a valid refresh
      // cookie sitting unused. A browser clock a few minutes slow is enough to
      // cause it; so is a rotated `SECRET_KEY`.
      const token = await refreshSession({ force: true });
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
        return apiClient(config);
      }
      emitSessionExpired();
    } else if (status === 401 && !isAuthRoute) {
      emitSessionExpired();
    }

    // Rejected either way. The interceptor decides that the *session* is over;
    // what this particular caller shows about its own failed request is still
    // its business, and swallowing the error here would leave every `catch`
    // in the app waiting on a promise that never settles.
    return Promise.reject(error);
  }
);

export default apiClient;
