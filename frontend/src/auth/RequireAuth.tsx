import { Navigate, Outlet } from "react-router-dom";
import Spinner from "../shared/Spinner";
import { useAuth } from "./AuthContext";

export default function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-950">
        <Spinner className="h-7 w-7" />
      </div>
    );
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
