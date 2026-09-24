/**
 * "This session is over, sign in again."
 *
 * Three unrelated places discover an expired token and none of them can call
 * `logout`: the axios response interceptor and the websocket's `onclose` are
 * module scope, and `AuthContext` holds the only working logout. So they meet
 * here, the same way `resync.ts` lets a store subscribe to a reconnect without
 * being mounted.
 *
 * Access tokens used to last ~300 minutes with no way to renew them, so this
 * was not an edge case: it was what happened to every person who left a tab
 * open overnight. Refresh rotation (Phase 15) moved that line — a session now
 * ends because the *refresh* failed, not because an access token expired — but
 * it did not remove it. Thirty days later, or after a sign-out elsewhere, the
 * app still has to say so rather than silently failing every request.
 *
 * The same seam carries the opposite news. A refresh that *succeeds* happens
 * in module scope too, and `AuthContext` is the only thing that can tell React
 * about it, so `onTokenRefreshed` is the mirror of `onSessionExpired`.
 */

type SessionExpiredHandler = () => void;

let handler: SessionExpiredHandler | null = null;

/**
 * Once per expiry, not once per failed request.
 *
 * A dead token fails every request in flight, and a page that has just loaded
 * has six of them. Without this latch the user is logged out six times and
 * navigated six times.
 */
let expiring = false;

/**
 * Why the login screen is being shown, kept where a redirect cannot lose it.
 *
 * Not a query parameter, which was the first attempt: when the session ends,
 * `RequireAuth` sees `isAuthenticated` go false and renders its own
 * `<Navigate to="/login" replace />`, and that plain URL races the one
 * `SessionWatch` asks for. The user landed on the login page with nothing
 * saying why, which is the entire point of the feature. `sessionStorage`
 * survives the redirect, is scoped to the tab, and is gone when the tab is.
 */
const EXPIRED_KEY = "rain.session.expired";

export function markSessionExpired(): void {
  try {
    sessionStorage.setItem(EXPIRED_KEY, "1");
  } catch {
    // Private mode, or storage disabled. The sign-out still happens; only the
    // explanation is lost, and that is not worth throwing over.
  }
}

/** Reads the flag and clears it, so a later visit is not told again. */
export function consumeSessionExpired(): boolean {
  try {
    const found = sessionStorage.getItem(EXPIRED_KEY) === "1";
    sessionStorage.removeItem(EXPIRED_KEY);
    return found;
  } catch {
    return false;
  }
}

/** Registered by the component that can actually log out. */
export function onSessionExpired(next: SessionExpiredHandler): () => void {
  handler = next;
  return () => {
    if (handler === next) handler = null;
  };
}

export function emitSessionExpired(): void {
  if (expiring) return;
  expiring = true;
  handler?.();
}

/**
 * Call after a successful sign-in, so the next expiry is heard.
 *
 * Without it the latch above stays closed for the life of the tab and the
 * second session of the day never learns it has ended.
 */
export function resetSessionExpiry(): void {
  expiring = false;
}

type TokenRefreshedHandler = (token: string) => void;

let refreshHandler: TokenRefreshedHandler | null = null;

/**
 * Registered by `AuthContext`, called by `auth/refresh.ts`.
 *
 * The cookies are already written by the time this fires — this exists purely
 * so the React tree stops holding the previous token in state. Nothing here is
 * the source of truth, so a refresh that lands before the provider has
 * subscribed loses nothing but a re-render.
 */
export function onTokenRefreshed(next: TokenRefreshedHandler): () => void {
  refreshHandler = next;
  return () => {
    if (refreshHandler === next) refreshHandler = null;
  };
}

export function emitTokenRefreshed(token: string): void {
  // A renewed session is by definition not an expired one. Without this, a tab
  // that expired, was renewed, and later expires again would never announce
  // the second one: the latch below is what stops six failed requests logging
  // you out six times, and it has to be reopened by good news as well as by a
  // fresh sign-in.
  expiring = false;
  refreshHandler?.(token);
}
