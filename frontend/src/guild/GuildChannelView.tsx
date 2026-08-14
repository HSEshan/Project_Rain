import { useParams } from "react-router-dom";
import { useChannelStore } from "../shared/channelStore";
import { ChannelType } from "../shared/types";
import { MessageView } from "../messages/MessageView";
import VoiceChannelView from "../voice/VoiceChannelView";
import GuildMembersBar from "./GuildMembersBar";

/**
 * Route element for /guild/:guildId/channel/:channelId.
 * Text channels reuse the DM chat surface; voice channels connect to the
 * LiveKit SFU (see AGENTS.md — no mesh WebRTC).
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
        <VoiceChannelView channel={channel} />
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
