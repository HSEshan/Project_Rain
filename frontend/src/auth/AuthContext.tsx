import { createContext, useContext, useEffect, useState } from "react";
import { Cookies } from "react-cookie";

const cookies = new Cookies();

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
  getToken: () => string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const token = cookies.get("token");
    setIsAuthenticated(!!token);
    setToken(token);
    setIsLoading(false);
  }, []);

  const login = (token: string) => {
    cookies.set("token", token, { path: "/" });
    setIsAuthenticated(true);
    setToken(token);
  };

  const logout = () => {
    cookies.remove("token", { path: "/" });
    setIsAuthenticated(false);
    setToken(null);
  };

  const getToken = () => {
    return token;
  };

  const values = {
    isAuthenticated,
    isLoading,
    login,
    logout,
    getToken,
  };

  return <AuthContext.Provider value={values}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
};
