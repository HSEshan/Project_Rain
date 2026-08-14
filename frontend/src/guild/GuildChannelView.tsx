import { useParams } from "react-router-dom";
import { useChannelStore } from "../shared/channelStore";
import { ChannelType } from "../shared/types";
import { MessageView } from "../messages/MessageView";
import GuildMembersBar from "./GuildMembersBar";

/**
 * Route element for /guild/:guildId/channel/:channelId.
 * Text channels reuse the DM chat surface; voice is a placeholder until the
 * SFU lands in Phase 4 (see AGENTS.md — no mesh WebRTC).
 */
export default function GuildChannelView() {
  const { guildId, channelId } = useParams<{
    guildId: string;
    channelId: string;
  }>();
  const { getChannel } = useChannelStore();

  if (!guildId || !channelId) return null;

  const channel = getChannel(channelId);

  if (!channel) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        Channel not found, or you are not a member of it.
      </div>
    );
  }

  if (channel.type === ChannelType.GUILD_VOICE) {
    return (
      <div className="flex flex-1">
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-3">
          <h1 className="text-xl text-white font-bold">🔊 {channel.name}</h1>
          <p className="text-gray-400 max-w-md">
            Voice channels are not live yet. They will connect to an SFU rather
            than peer-to-peer WebRTC.
          </p>
        </div>
        <GuildMembersBar guildId={guildId} />
      </div>
    );
  }

  return (
    <div className="flex flex-1">
      <MessageView channelId={channelId} title={`# ${channel.name}`} />
      <GuildMembersBar guildId={guildId} />
    </div>
  );
}
