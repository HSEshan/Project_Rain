/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from "react";
import { Cookies } from "react-cookie";
import { jwtDecode } from "jwt-decode";

const tokenCookies = new Cookies();
const userCookies = new Cookies();

type JWT = {
  sub: string;
  id: string;
  name: string;
  exp: number;
};

type User = {
  id: string;
  username: string;
  email: string;
  exp: number;
};

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
  getToken: () => string | null;
  getUser: () => User | null;
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

  const login = (token: string) => {
    const jwtPayload = jwtDecode<JWT>(token);
    tokenCookies.set("token", token, {
      path: "/",
      expires: new Date(jwtPayload.exp * 1000),
    });
    setIsAuthenticated(true);
    setToken(token);

    const user = {
      id: jwtPayload.id,
      username: jwtPayload.name,
      email: jwtPayload.sub,
      exp: jwtPayload.exp,
    };
    setUser(user);
    userCookies.set("user", user, {
      path: "/",
      expires: new Date(jwtPayload.exp * 1000),
    });
  };

  const logout = () => {
    tokenCookies.remove("token", { path: "/" });
    userCookies.remove("user", { path: "/" });
    setIsAuthenticated(false);
    setToken(null);
    setUser(null);
  };

  const getToken = () => {
    return token;
  };

  const getUser = () => {
    return user;
  };

  const initialize = () => {
    const token = tokenCookies.get("token");
    if (!token) {
      logout();
      setIsLoading(false);
      return;
    }
    const jwtPayload = jwtDecode<JWT>(token);
    if (jwtPayload.exp < Date.now() / 1000) {
      logout();
      setIsLoading(false);
      return;
    }
    const user = userCookies.get("user");
    setIsAuthenticated(!!token);
    setToken(token);
    setUser(user);
    setIsLoading(false);
  };

  const values = {
    isAuthenticated,
    isLoading,
    login,
    logout,
    getToken,
    getUser,
    initialize,
  };

  return <AuthContext.Provider value={values}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
};
