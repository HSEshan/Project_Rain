import { Outlet } from "react-router-dom";
import GuildChannelsBar from "./GuildChannelsBar";

/** Layout for /guild/:guildId — channel list plus the selected channel. */
export function GuildLayout() {
  return (
    <div className="flex flex-1">
      <GuildChannelsBar />

      <Outlet />
    </div>
  );
}
