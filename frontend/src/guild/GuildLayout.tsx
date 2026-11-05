import { useEffect } from "react";
import { Navigate, Outlet, useParams } from "react-router-dom";
import GuildChannelsBar from "./GuildChannelsBar";
import { useGuildStore } from "./guildStore";

/** Layout for /guild/:guildId — channel list plus the selected channel. */
export function GuildLayout() {
  const { guildId } = useParams<{ guildId: string }>();
  const fetchGuildMembers = useGuildStore((state) => state.fetchGuildMembers);
  const guildsLoaded = useGuildStore((state) => state.guildsLoaded);
  const inGuild = useGuildStore((state) =>
    state.guilds.some((guild) => guild.id === guildId)
  );

  // Here rather than in the members panel, which only exists with a channel
  // open: the channel bar needs your role to know what to offer.
  useEffect(() => {
    if (guildId && inGuild) void fetchGuildMembers(guildId);
  }, [guildId, inGuild, fetchGuildMembers]);

  // Deleted under you, or you were removed. Without this the page stays up as
  // an empty shell of a guild that is no longer yours.
  if (guildsLoaded && !inGuild) return <Navigate to="/guild" replace />;

  return (
    <div className="flex min-w-0 flex-1">
      <GuildChannelsBar />
      <Outlet />
    </div>
  );
}
