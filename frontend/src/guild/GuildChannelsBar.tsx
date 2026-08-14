import { useEffect } from "react";
import { useMatch, useParams } from "react-router-dom";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import { useAuth } from "../auth/AuthContext";
import { ChannelType, type Channel } from "../shared/types";
import LinkButton from "../shared/LinkButton";
import { useVoiceStore } from "../voice/voiceStore";

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

/**
 * Who is talking in a voice channel, listed under it Discord-style. This is the
 * server roster, not the SFU room, so it renders for people who have not joined.
 */
function VoiceRoster({ channelId }: { channelId: string }) {
  const participants = useVoiceStore((state) => state.rosters[channelId]);
  const users = useUserStore((state) => state.users);

  if (!participants?.length) return null;

  return (
    <ul className="pl-8 flex flex-col gap-1">
      {participants.map((userId) => (
        <li key={userId} className="text-xs text-gray-400 truncate">
          {users[userId]?.username ?? "…"}
        </li>
      ))}
    </ul>
  );
}

export default function GuildChannelsBar() {
  const { guildId } = useParams<{ guildId: string }>();
  // channelId belongs to a child route, so it is read from the URL directly
  const channelId = useMatch("/guild/:guildId/channel/:channelId")?.params
    .channelId;
  const { getGuild, setChannelModalGuildId, setInviteModalGuildId } =
    useGuildStore();
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

  const { fetchRoster, rosters } = useVoiceStore();
  const fetchUsers = useUserStore((state) => state.fetchUsers);
  const voiceChannelIds = voiceChannels.map((channel) => channel.id).join(",");

  // VOICE_STATE events keep the rosters live once we have them; this is the
  // initial read for channels the user has not opened.
  useEffect(() => {
    voiceChannelIds
      .split(",")
      .filter(Boolean)
      .forEach((id) => void fetchRoster(id));
  }, [voiceChannelIds, fetchRoster]);

  useEffect(() => {
    const userIds = Object.values(rosters).flat();
    if (userIds.length) void fetchUsers(userIds);
  }, [rosters, fetchUsers]);

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
            <div key={channel.id} className="flex flex-col gap-1">
              <ChannelLink
                channel={channel}
                guildId={guildId!}
                active={channelId === channel.id}
              />
              <VoiceRoster channelId={channel.id} />
            </div>
          ))}
        </div>
      </div>

      {/* In the channel bar rather than the members panel so it is reachable
          with no channel selected — otherwise a fresh guild has no way in. */}
      <button
        className="text-sm px-2 py-2 bg-gray-800 hover:bg-gray-700 rounded-md transition-colors"
        onClick={() => setInviteModalGuildId(guildId ?? null)}
      >
        + Invite people
      </button>

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
