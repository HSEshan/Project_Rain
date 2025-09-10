import { Outlet } from "react-router-dom";
import GuildSelectionBar from "./GuildSelectionBar";
import GuildChannelsBar from "./GuildChannelsBar";
import { useParams } from "react-router-dom";

export function GuildLayout() {
  const { guildId } = useParams<{ guildId: string }>();

  return (
    <div className="flex flex-1">
      {!guildId && <GuildSelectionBar />}
      {guildId && <GuildChannelsBar />}

      <Outlet />
    </div>
  );
}
