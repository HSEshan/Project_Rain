import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { MessageLayout } from "./messages/MessageLayout";
import { MessageView } from "./messages/MessageView";
import { GuildLayout } from "./guild/GuildLayout";

import AuthPage from "./auth/AuthPage";
import RequireAuth from "./auth/RequireAuth";
import { AuthProvider } from "./auth/AuthContext";
import { WebSocketProvider } from "./utils/WebsocketProvider";
import { Sidebar } from "./sidebar/Sidebar";
import AppInitializer from "./utils/AppInitializer";
import LandingPage from "./landing_page/LandingPage";
import HomePage from "./home/HomePage";

function MainLayout() {
  return (
    <div className="flex h-screen bg-gray-800">
      <AppInitializer />
      <WebSocketProvider>
        <Sidebar />

        <Outlet />
      </WebSocketProvider>
    </div>
  );
}
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<AuthPage />} />

          <Route element={<RequireAuth />}>
            <Route path="/home" element={<MainLayout />}>
              <Route index element={<HomePage />} />
            </Route>
            <Route path="/dm" element={<MainLayout />}>
              <Route index element={<MessageLayout />} />
              <Route path=":dmId" element={<MessageLayout />}>
                <Route index element={<MessageView />} />
              </Route>
            </Route>
            <Route path="/guild" element={<MainLayout />}>
              <Route index element={<GuildLayout />} />
              <Route path=":guildId" element={<GuildLayout />}>
                {/* <Route index element={<GuildView />} />
                <Route path="channel/:channelId" element={<GuildView />} /> */}
              </Route>
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
