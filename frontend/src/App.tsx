import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { MessageLayout } from "./messages/MessageLayout";
import { DMView } from "./messages/DMView";
import { GuildLayout } from "./guild/GuildLayout";
import GuildsHome from "./guild/GuildsHome";
import GuildChannelView from "./guild/GuildChannelView";

import AuthPage from "./auth/AuthPage";
import RequireAuth from "./auth/RequireAuth";
import { AuthProvider } from "./auth/AuthContext";
import { WebSocketProvider } from "./utils/WebsocketProvider";
import { Sidebar } from "./sidebar/Sidebar";
import AppInitializer from "./utils/AppInitializer";
import LandingPage from "./landing_page/LandingPage";
import HomePage from "./home/HomePage";
import EmptyState from "./shared/EmptyState";
import FriendsPage from "./friends/FriendsPage";
import AddFriendModal from "./friends/AddFriendModal";
import GuildCreateModal from "./guild/GuildCreateModal";
import GuildChannelCreateModal from "./guild/GuildChannelCreateModal";
import GuildInviteModal from "./guild/GuildInviteModal";
import GuildInviteInboxModal from "./guild/GuildInviteInboxModal";

function MainLayout() {
  return (
    <div className="flex h-[100dvh] overflow-hidden bg-ink-950 text-ink-100">
      <AppInitializer />
      <WebSocketProvider>
        <Sidebar />

        {/* The rail is a fixed bottom bar below `lg`, so it is out of flow and
            the content needs its own room at the bottom. */}
        <div className="flex min-w-0 flex-1 pb-16 lg:pb-0">
          <Outlet />
        </div>

        {/* Single mount point: every modal is driven by store state, so any
            component can open one without mounting its own copy. */}
        <AddFriendModal />
        <GuildCreateModal />
        <GuildChannelCreateModal />
        <GuildInviteModal />
        <GuildInviteInboxModal />
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
              <Route element={<MessageLayout />}>
                <Route index element={<FriendsPage />} />
                <Route path=":dmId" element={<DMView />} />
              </Route>
            </Route>
            <Route path="/guild" element={<MainLayout />}>
              <Route index element={<GuildsHome />} />
              {/* The layout sits on :guildId so useParams sees the guild */}
              <Route path=":guildId" element={<GuildLayout />}>
                <Route
                  index
                  element={
                    <div className="flex min-w-0 flex-1 flex-col">
                      <EmptyState
                        title="No channel selected"
                        hint="Pick a channel on the left to start talking."
                      />
                    </div>
                  }
                />
                <Route
                  path="channel/:channelId"
                  element={<GuildChannelView />}
                />
              </Route>
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
