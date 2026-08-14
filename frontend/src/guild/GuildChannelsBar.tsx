import { useMatch, useParams } from "react-router-dom";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import { useAuth } from "../auth/AuthContext";
import { ChannelType, type Channel } from "../shared/types";
import LinkButton from "../shared/LinkButton";

function ChannelLink({
  channel,
  guildId,
  active,
}: {
  channel: Channel;
  guildId: string;
  active: boolean;
}) {
  return (
    <LinkButton
      to={`/guild/${guildId}/channel/${channel.id}`}
      active={active}
      className="justify-start"
    >
      <div className="flex items-center gap-2 w-full px-3 truncate">
        {channel.type === ChannelType.GUILD_TEXT ? "💬" : "🔊"} {channel.name}
      </div>
    </LinkButton>
  );
}

export default function GuildChannelsBar() {
  const { guildId } = useParams<{ guildId: string }>();
  // channelId belongs to a child route, so it is read from the URL directly
  const channelId = useMatch("/guild/:guildId/channel/:channelId")?.params
    .channelId;
  const { getGuild, setChannelModalGuildId } = useGuildStore();
  const { getGuildChannels } = useChannelStore();
  const { getCurrentUser } = useAuth();

  const guild = getGuild(guildId ?? "");
  const guildChannels = getGuildChannels(guildId ?? "");
  const textChannels = guildChannels.filter(
    (channel) => channel.type === ChannelType.GUILD_TEXT
  );
  const voiceChannels = guildChannels.filter(
    (channel) => channel.type === ChannelType.GUILD_VOICE
  );
  const isOwner = !!guild && guild.owner_id === getCurrentUser()?.id;

  return (
    <div className="w-1/6 bg-gray-900 text-white flex flex-col px-2 py-4 gap-4">
      <h1 className="text-lg text-white font-bold flex-shrink-0 text-center">
        {guild?.name}
      </h1>

      <div className="w-full h-full flex flex-col gap-4 overflow-y-auto">
        <div className="flex flex-col gap-2">
          <h2 className="text-xs uppercase tracking-wide text-gray-400 px-1">
            Text channels
          </h2>
          {textChannels.map((channel) => (
            <ChannelLink
              key={channel.id}
              channel={channel}
              guildId={guildId!}
              active={channelId === channel.id}
            />
          ))}
        </div>

        <div className="flex flex-col gap-2">
          <h2 className="text-xs uppercase tracking-wide text-gray-400 px-1">
            Voice channels
          </h2>
          {voiceChannels.map((channel) => (
            <ChannelLink
              key={channel.id}
              channel={channel}
              guildId={guildId!}
              active={channelId === channel.id}
            />
          ))}
        </div>
      </div>

      {isOwner && (
        <button
          className="text-sm px-2 py-2 bg-gray-800 hover:bg-gray-700 rounded-md transition-colors"
          onClick={() => setChannelModalGuildId(guildId ?? null)}
        >
          + Create channel
        </button>
      )}
    </div>
  );
}
