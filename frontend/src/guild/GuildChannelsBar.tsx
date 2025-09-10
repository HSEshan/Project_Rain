import { useParams } from "react-router-dom";
import { useGuildStore } from "./guildStore";

export default function GuildChannelsBar() {
  const { guildId } = useParams<{ guildId: string }>();
  const { guilds } = useGuildStore();
  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-4">
      Guild Channels Bar for{" "}
      {guilds.find((guild) => guild.id === guildId)?.name}
    </div>
  );
}
