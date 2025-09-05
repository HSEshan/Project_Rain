import { useWebSocket } from "../utils/WebsocketProvider";
import { useGuildStore } from "../guild/guildStore";
import { Link } from "react-router-dom";

export function Sidebar() {
  const { isConnected } = useWebSocket();
  const { guilds } = useGuildStore();

  return (
    <div className="w-20 bg-gray-900 text-white flex flex-col items-center py-4 gap-4">
      {isConnected ? (
        <div className="w-3 h-3 bg-green-500 rounded-full" />
      ) : (
        <div className="w-3 h-3 bg-red-500 rounded-full" />
      )}
      <Link
        to="/dm"
        className="w-12 h-12 flex flex-col items-center justify-center rounded-xl bg-gray-700"
      >
        DM
      </Link>
      {guilds.map((guild) => (
        <Link
          to={`/guild/${guild.id}`}
          key={guild.id}
          className="w-12 h-12 flex flex-col items-center justify-center rounded-xl bg-gray-700"
        >
          {guild.name}
        </Link>
      ))}
    </div>
  );
}
