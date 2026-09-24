import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { REFRESH_SKEW_SECONDS, refreshSession } from "./refresh";
import { useWebSocket } from "../utils/WebsocketProvider";
import { resetAllStores } from "../shared/resetStores";
import { markSessionExpired, onSessionExpired } from "../shared/session";

/**
 * Keeps the session alive while it can be, and ends it cleanly when it cannot.
 *
 * It used to only do the second half: the access token was the whole session,
 * so the timer below waited for `exp` and signed the user out. With refresh
 * rotation the same timer does the opposite — it renews a couple of minutes
 * *before* expiry, and only ends the session when the renewal is refused,
 * which is now the single thing that means "you are signed out": the refresh
 * cookie is gone, or thirty days have passed, or someone signed out elsewhere.
 *
 * The proactive half still matters most in practice, for the same reason it
 * always did. A person who leaves a tab open overnight is not clicking
 * anything, so nothing would fail and nothing would notice — before, that meant
 * they came back to an app that quietly rejected every request; now it would
 * mean they came back to a session that could have been renewed and was not.
 *
 * The reactive half is unchanged and still needed: `shared/session.ts` carries
 * a 401 whose refresh failed, and a 1008 close from the gateway.
 *
 * Mounted inside `MainLayout`, so it exists exactly where the websocket and the
 * router do.
 */
export default function SessionWatch() {
  const { getCurrentUser, getToken, logout } = useAuth();
  const { disconnect } = useWebSocket();
  const navigate = useNavigate();

  // Read during render, not inside the effect, so the effect can depend on
  // them: every renewal replaces both, and that is what schedules the next
  // timer. Depending on the accessor functions instead would re-run the effect
  // on every unrelated render and never on the one that matters.
  const token = getToken();
  const exp = getCurrentUser()?.exp;

  useEffect(() => {
    const end = () => {
      // Order matters. The reason is recorded first, because `logout` flips
      // `isAuthenticated` and `RequireAuth` redirects on its own the moment it
      // does — the navigate below may never be the one that runs. Then
      // disconnect, so the socket does not reconnect with the token that was
      // just thrown away, then clear the stores before navigating so the login
      // screen cannot flash the previous account's data.
      markSessionExpired();
      disconnect();
      resetAllStores();
      logout();
      navigate("/login", { replace: true });
    };

    const unsubscribe = onSessionExpired(end);

    if (!token || !exp) return unsubscribe;

    // `exp` is seconds since the epoch, from the JWT the client already
    // decoded. Renew ahead of it by the same margin `refresh.ts` uses, so the
    // two agree on what "close to expiry" means; clamped at zero for a token
    // that is already inside the window when this mounts, which is what a
    // laptop waking from sleep looks like.
    const renewIn = Math.max(
      exp * 1000 - REFRESH_SKEW_SECONDS * 1000 - Date.now(),
      0
    );

    // setTimeout tops out around 24 days, and an access token is measured in
    // an hour, so one timer is enough and no chaining is needed. A successful
    // renewal changes `token`, which re-runs this effect and schedules the
    // next one.
    const timer = setTimeout(async () => {
      const renewed = await refreshSession();
      if (!renewed) end();
    }, renewIn);

    return () => {
      clearTimeout(timer);
      unsubscribe();
    };
  }, [token, exp, logout, disconnect, navigate]);

  return null;
}
