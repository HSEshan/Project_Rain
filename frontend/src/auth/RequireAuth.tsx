import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div className="text-white p-4">Loading...</div>; // or a spinner
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" />;
}
