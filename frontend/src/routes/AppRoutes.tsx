import { Routes, Route, Navigate } from "react-router-dom";
import MainLayout from "../layouts/MainLayout";
import HomeLayout from "../pages/Home/HomeLayout";
import WhatsNew from "../pages/Home/WhatsNew";
import Trending from "../pages/Home/Trending";
import Friends from "../pages/Friends";
import Settings from "../pages/Settings";
import AuthPage from "../auth/AuthPage";
import RequireAuth from "../auth/RequireAuth";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/" element={<Navigate to="/auth" replace />} />

      <Route element={<RequireAuth />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<HomeLayout />}>
            <Route index element={<WhatsNew />} />
            <Route path="trending" element={<Trending />} />
          </Route>
          <Route path="/friends" element={<Friends />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
    </Routes>
  );
}
