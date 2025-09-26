import { useParams } from "react-router-dom";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import { ChannelType } from "../shared/types";
export default function GuildChannelsBar() {
  const { guildId } = useParams<{ guildId: string }>();
  const { guilds } = useGuildStore();
  const { getGuildChannels } = useChannelStore();
  const guildChannels = getGuildChannels(guildId ?? "");
  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col items-center px-2 py-4 gap-4">
      <h1 className="text-lg text-white font-bold mb-4 flex-shrink-0">
        {guilds.find((guild) => guild.id === guildId)?.name}
      </h1>
      <div className="h-64 w-full text-center border-2 border-white rounded-md">
        Guild Banner
      </div>
      <div className="w-full h-full flex flex-col gap-2 overflow-y-auto">
        {guildChannels.map((channel) => (
          <div
            key={channel.id}
            className="w-full h-10 bg-gray-800 rounded-md flex items-center justify-start px-4"
          >
            {channel.type === ChannelType.GUILD_TEXT
              ? `💬 ${channel.name}`
              : `🔊 ${channel.name}`}
          </div>
        ))}
      </div>
    </div>
  );
}
