/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from "react";
import {
  onTokenRefreshed,
  resetSessionExpiry,
} from "../shared/session";
import { postLogout } from "./apiClient";
import { refreshSession, tokenNeedsRefresh } from "./refresh";
import {
  clearSession,
  readToken,
  readUser,
  storeSession,
  type SessionUser,
} from "./tokenStore";

type User = SessionUser;

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
  getToken: () => string | null;
  getCurrentUser: () => User | null;
  initialize: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    initialize();
  }, []);

  // A refresh from module scope (the axios interceptor, the websocket, the
  // renewal timer) has already written the cookies. This is how the React tree
  // hears about it, so `getToken` does not keep handing out the token that was
  // just replaced.
  useEffect(() => onTokenRefreshed((next) => adopt(next)), []);

  /** Take a token as the current session: cookies first, then state. */
  const adopt = (next: string): User => {
    const nextUser = storeSession(next);
    setIsAuthenticated(true);
    setToken(next);
    setUser(nextUser);
    return nextUser;
  };

  const login = (token: string) => {
    // A new session can expire again; the latch in `session.ts` is closed for
    // the life of the tab otherwise, and the second sign-in of the day would
    // never be told it had ended.
    resetSessionExpiry();
    adopt(token);
  };

  const logout = () => {
    // Revoke the session server-side, not just this browser's copy of it.
    // Best effort and deliberately not awaited: the local sign-out must happen
    // whether or not the request does, and there is nothing a user could do
    // about a failure. When the session is already over — this is also the
    // path an expiry takes — the server answers 204 and nothing changes.
    void postLogout();
    clearSession();
    setIsAuthenticated(false);
    setToken(null);
    setUser(null);
  };

  const getToken = () => {
    return token;
  };

  const getCurrentUser = () => {
    return user;
  };

  /**
   * Decide, once, whether this browser is signed in.
   *
   * The interesting case is the one that used to be a sign-out: a token that
   * has expired, or is about to. Before refresh rotation the only answer was
   * to clear everything and show the login form, which is what "left the tab
   * open overnight" felt like. Now the refresh cookie outlives the access
   * token by weeks, so the honest first move is to try to use it, and only
   * treat the session as over when that fails.
   *
   * `isLoading` stays true across the attempt, which is what `RequireAuth`
   * waits on — without that, one render with `isAuthenticated: false` bounces
   * the user to the login screen before the refresh has answered.
   */
  const initialize = async () => {
    const stored = readToken();

    if (tokenNeedsRefresh(stored)) {
      const renewed = await refreshSession();
      if (renewed) {
        resetSessionExpiry();
        adopt(renewed);
      } else {
        clearSession();
        setIsAuthenticated(false);
        setToken(null);
        setUser(null);
      }
      setIsLoading(false);
      return;
    }

    setIsAuthenticated(true);
    setToken(stored);
    // Rebuilt from the token rather than trusted from the cookie, so a missing
    // or stale `user` cookie cannot leave the app authenticated as nobody.
    setUser(readUser() ?? (stored ? storeSession(stored) : null));
    setIsLoading(false);
  };

  const values = {
    isAuthenticated,
    isLoading,
    login,
    logout,
    getToken,
    getCurrentUser,
    initialize,
  };

  return <AuthContext.Provider value={values}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
};
