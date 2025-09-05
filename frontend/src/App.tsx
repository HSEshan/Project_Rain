import {
  BrowserRouter,
  Routes,
  Route,
  Outlet,
  Navigate,
} from "react-router-dom";
import { MessageLayout } from "./messages/MessageLayout";
import { MessageView } from "./messages/MessageView";
// import { GuildLayout } from "./guilds/GuildLayout";
// import { GuildView } from "./guilds/GuildView";

import AuthPage from "./auth/AuthPage";
import RequireAuth from "./auth/RequireAuth";
import { AuthProvider } from "./auth/AuthContext";
import { WebSocketProvider } from "./utils/WebsocketProvider";
import { Sidebar } from "./sidebar/Sidebar";
import AppInitializer from "./utils/AppInitializer";

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
          <Route path="/login" element={<AuthPage />} />
          <Route path="/" element={<Navigate to="/login" replace />} />

          <Route element={<RequireAuth />}>
            <Route path="/home" element={<MainLayout />} />
            <Route path="/dm" element={<MainLayout />}>
              <Route index element={<MessageLayout />} />
              <Route path=":dmId" element={<MessageLayout />}>
                <Route index element={<MessageView />} />
              </Route>
            </Route>
            {/* <Route path="/guild" element={<MainLayout />}>
            <Route index element={<GuildLayout />} />
            <Route path=":guildId" element={<GuildLayout />}>
              <Route index element={<GuildView />} />
              <Route path="channel/:channelId" element={<GuildView />} />
            </Route>
          </Route> */}
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
