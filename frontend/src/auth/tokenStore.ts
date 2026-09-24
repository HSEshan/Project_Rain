import { Cookies } from "react-cookie";
import { jwtDecode } from "jwt-decode";

/**
 * The session's cookies, in one place.
 *
 * `AuthContext` used to own this, which was fine while signing in was the only
 * thing that ever wrote a token. Refresh rotation adds a second writer that is
 * not a React component and cannot be one: it runs from an axios interceptor
 * and from the websocket's `onclose`, both module scope. Two writers copying
 * the same three lines is how the `user` cookie ends up outliving the `token`
 * cookie by a rotation, so there is one writer here and both callers use it.
 *
 * Only the **access** token is here. The refresh token is an httpOnly cookie
 * set by the server and this file could not read it if it tried, which is the
 * point — see `backend/rest_api/src/auth/cookies.py`.
 */

const cookies = new Cookies();

const TOKEN_COOKIE = "token";
const USER_COOKIE = "user";

/**
 * Set by the server beside the refresh cookie, and readable, which the refresh
 * cookie deliberately is not. It answers one question — is there a session in
 * this browser worth asking about — so that a visitor who has never signed in
 * does not send a refresh request from the public landing page and collect a
 * 401 for it. It is not a credential and is never treated as one.
 */
const SESSION_HINT_COOKIE = "rain_session";

type JWT = {
  sub: string;
  id: string;
  name: string;
  exp: number;
};

export type SessionUser = {
  id: string;
  username: string;
  email: string;
  /** Seconds since the epoch, straight off the JWT. */
  exp: number;
};

export function decodeToken(token: string): SessionUser {
  const payload = jwtDecode<JWT>(token);
  return {
    id: payload.id,
    username: payload.name,
    email: payload.sub,
    exp: payload.exp,
  };
}

/**
 * Write both cookies from one token, and return who it says you are.
 *
 * Both get the token's own expiry, so neither can outlive the other. The
 * `user` cookie is a convenience copy of claims already inside the JWT — it is
 * not a credential, and nothing trusts it that would not equally trust the
 * token it came from.
 */
export function storeSession(token: string): SessionUser {
  const user = decodeToken(token);
  const expires = new Date(user.exp * 1000);
  cookies.set(TOKEN_COOKIE, token, { path: "/", expires });
  cookies.set(USER_COOKIE, user, { path: "/", expires });
  return user;
}

export function hasSessionHint(): boolean {
  return Boolean(cookies.get(SESSION_HINT_COOKIE));
}

export function readToken(): string | null {
  return cookies.get(TOKEN_COOKIE) ?? null;
}

export function readUser(): SessionUser | null {
  return cookies.get(USER_COOKIE) ?? null;
}

export function clearSession(): void {
  cookies.remove(TOKEN_COOKIE, { path: "/" });
  cookies.remove(USER_COOKIE, { path: "/" });
  // The server clears this too, on logout and on a refused refresh. Clearing
  // it here as well covers the local sign-out that happens before, or without,
  // that request landing.
  cookies.remove(SESSION_HINT_COOKIE, { path: "/" });
}

/** Negative once the token is past its expiry. */
export function secondsUntilExpiry(token: string): number {
  try {
    return decodeToken(token).exp - Date.now() / 1000;
  } catch {
    // A cookie that is not a JWT is not a session. Treating it as long expired
    // sends every caller down the refresh path, which is the right answer.
    return -1;
  }
}
