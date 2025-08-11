import { Link } from "react-router-dom";
import { useSidebarData } from "../hooks/useSidebarData";
import { GuildIcon } from "./GuildIcon";

export function Sidebar() {
  const { guilds, dmUnread, guildUnread, resetDMUnread, resetGuildUnread } =
    useSidebarData();

  return (
    <aside className="w-16 bg-gray-900 flex flex-col items-center py-4 space-y-4">
      {/* DM Icon */}
      <Link
        to="/dm"
        onClick={resetDMUnread}
        className="relative flex items-center justify-center w-12 h-12 bg-gray-800 rounded-full hover:bg-gray-700"
      >
        💬
        {dmUnread > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-xs px-1 rounded-full">
            {dmUnread}
          </span>
        )}
      </Link>

      {/* Divider */}
      <div className="w-8 border-t border-gray-700 my-2"></div>

      {/* Guild Icons */}
      <div className="flex flex-col space-y-3 overflow-y-auto">
        {guilds.map((guild) => (
          <Link
            key={guild.id}
            to={`/guilds/${guild.id}`}
            onClick={() => resetGuildUnread(guild.id)}
            className="relative flex items-center justify-center w-12 h-12 bg-gray-800 rounded-full hover:bg-gray-700"
          >
            <GuildIcon guild={guild} />
            {guildUnread[guild.id] > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-xs px-1 rounded-full">
                {guildUnread[guild.id]}
              </span>
            )}
          </Link>
        ))}
      </div>
    </aside>
  );
}
