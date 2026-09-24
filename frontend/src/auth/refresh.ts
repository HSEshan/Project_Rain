import axios from "axios";
import {
  hasSessionHint,
  readToken,
  secondsUntilExpiry,
  storeSession,
} from "./tokenStore";
import { emitTokenRefreshed } from "../shared/session";

/**
 * Renewing the access token, from anywhere, without renewing it twice.
 *
 * Three callers, none of them a component: the axios interceptor on a 401, the
 * websocket when the gateway refuses its token, and the timer in
 * `SessionWatch` that renews before either of those can happen. They can all
 * fire at once, and a refresh token may only be spent once — the server
 * revokes the whole family if one is presented twice, which is the entire
 * point of rotation. So the concurrency control is not an optimisation here,
 * it is what stops the app logging itself out.
 *
 * Two layers of it, because there are two kinds of "at once":
 *
 * 1. **Within a tab**, `inFlight` collapses concurrent callers onto one
 *    request. A page that has just loaded has half a dozen requests in the
 *    air, and a stale token fails every one of them.
 * 2. **Across tabs**, the Web Locks API. Two tabs of the same app are two
 *    independent JavaScript worlds sharing one cookie jar, and their renewal
 *    timers were set at the same sign-in, so they wake up together. The lock
 *    is per origin, so only one tab is inside `renew` at a time; the others
 *    then find the cookie already fresh and make no request at all.
 *
 * Requests go through plain `axios` rather than `apiClientBase`, deliberately.
 * That client's response interceptor calls *this* on a 401, and a refresh that
 * is itself refreshed on failure is an infinite loop. It also needs no
 * `Authorization` header: the credential is the httpOnly cookie the browser
 * attaches, and the whole reason this endpoint exists is that the access token
 * has expired.
 */

const REFRESH_URL = "/api/auth/refresh";
const LOCK_NAME = "rain.session.refresh";

/**
 * Renew this far ahead of expiry rather than at it.
 *
 * Two minutes covers a slow request, a laptop whose clock is a little off, and
 * the gap between deciding to send a request and it arriving. Renewing exactly
 * at expiry means every renewal is a race with the thing it is preventing.
 */
export const REFRESH_SKEW_SECONDS = 120;

let inFlight: Promise<string | null> | null = null;

export function tokenNeedsRefresh(token: string | null): boolean {
  return !token || secondsUntilExpiry(token) <= REFRESH_SKEW_SECONDS;
}

/**
 * The current access token, renewed if it is close to expiry.
 *
 * Returns null when the session is genuinely over — no refresh cookie, an
 * expired one, or one the server refused. That is the caller's cue to end the
 * session, and the only thing that should end it: a failed request is not
 * evidence of an expired session any more, because the failure may simply mean
 * it was time to renew.
 */
export async function refreshSession(
  options: { force?: boolean } = {}
): Promise<string | null> {
  // Nothing to renew, and nothing to ask. Without this every visitor to the
  // public landing page would send one refresh request and be answered 401,
  // because the cookie that would have said otherwise is unreadable by design.
  if (!hasSessionHint()) return null;
  // A forced renewal must not join a request that is not forced: that one is
  // allowed to short-circuit on a token the caller has already been told is
  // unusable, which is exactly what `force` exists to override.
  if (inFlight && !options.force) return inFlight;
  const request = withLock(() => renew(options.force ?? false)).finally(() => {
    if (inFlight === request) inFlight = null;
  });
  inFlight = request;
  return request;
}

async function withLock<T>(fn: () => Promise<T>): Promise<T> {
  // Available in every browser this app supports, but it is a capability
  // check rather than an assumption: without it the single-tab guard above
  // still holds, and the server's grace window covers the cross-tab race.
  if (!navigator.locks?.request) return fn();
  return navigator.locks.request(LOCK_NAME, fn) as Promise<T>;
}

async function renew(force: boolean): Promise<string | null> {
  // Re-read after taking the lock. Whoever held it before us has already
  // written a new token to the shared cookie, so there is nothing to do —
  // this is the check that turns four tabs waking up together into one
  // request instead of four rotations.
  //
  // `force` skips it, and the websocket is why. `tokenNeedsRefresh` judges a
  // token by its own `exp`, which is the client's only evidence — and when the
  // gateway answers 1008 that evidence has just been contradicted by a server.
  // A token can be refused while still looking fresh here: the two services'
  // clocks disagree, `SECRET_KEY` was rotated, or the env files drifted apart.
  // Without this the socket renewed nothing, reconnected with the same refused
  // token, and stayed disconnected for the life of the tab.
  const existing = readToken();
  if (!force && existing && !tokenNeedsRefresh(existing)) return existing;

  try {
    const response = await axios.post(REFRESH_URL, null, {
      headers: { "Content-Type": "application/json" },
    });
    const token: string | undefined = response.data?.access_token;
    if (!token) return null;

    storeSession(token);
    // The cookies are written first, so anything that reads them mid-render
    // already sees the new session; this only tells React about it.
    emitTokenRefreshed(token);
    return token;
  } catch {
    // 401 means the session is over and the server has already cleared the
    // refresh cookie. Anything else is an outage, and the caller's retry or
    // the next timer will come back here — treating both as "no token" is
    // right because neither leaves us with one.
    return null;
  }
}
