import { createContext, useContext, useEffect, useState } from "react";
import { Cookies } from "react-cookie";

const cookies = new Cookies();

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true); // <== NEW

  useEffect(() => {
    const token = cookies.get("token");
    setIsAuthenticated(!!token);
    setIsLoading(false); // <== Done loading after checking cookie
  }, []);

  const login = (token: string) => {
    cookies.set("token", token, { path: "/" });
    setIsAuthenticated(true);
  };

  const logout = () => {
    cookies.remove("token", { path: "/" });
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
};
