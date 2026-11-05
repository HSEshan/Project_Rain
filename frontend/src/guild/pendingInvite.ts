/**
 * An invite link followed before signing in, kept until sign-in is done.
 *
 * Here and not in a `?next=` query parameter, for two reasons. It survives the
 * signup path, which goes through a second page on its way to the login form. And
 * what is stored is a code rather than a location, so there is no way to turn the
 * login page into a redirect to somewhere else.
 */
const KEY = "rain_pending_invite";

export function rememberInvite(code: string): void {
  sessionStorage.setItem(KEY, code);
}

/** Where to go after signing in. Read once, so it cannot fire twice. */
export function takeInvitePath(): string | null {
  const code = sessionStorage.getItem(KEY);
  if (!code) return null;
  sessionStorage.removeItem(KEY);
  return `/invite/${encodeURIComponent(code)}`;
}
