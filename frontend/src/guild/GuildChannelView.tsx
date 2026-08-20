import { useParams } from "react-router-dom";
import { FiHash, FiUsers } from "react-icons/fi";
import { useChannelStore } from "../shared/channelStore";
import { useUiStore } from "../shared/uiStore";
import { ChannelType } from "../shared/types";
import { MessageView } from "../messages/MessageView";
import VoiceChannelView from "../voice/VoiceChannelView";
import EmptyState from "../shared/EmptyState";
import GuildMembersBar from "./GuildMembersBar";

/** Opens the members drawer below `xl`, where the column does not fit. */
function MembersToggle() {
  const setMembersOpen = useUiStore((state) => state.setMembersOpen);
  return (
    <button
      onClick={() => setMembersOpen(true)}
      aria-label="Show members"
      className="rounded-lg p-2 text-ink-300 transition-colors hover:bg-white/5 hover:text-white xl:hidden"
    >
      <FiUsers size={17} />
    </button>
  );
}

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
      <div className="flex min-w-0 flex-1 flex-col">
        <EmptyState
          title="Channel not found"
          hint="It may have been deleted, or you are not a member of it."
        />
      </div>
    );
  }

  if (channel.type === ChannelType.GUILD_VOICE) {
    return (
      <div className="flex min-w-0 flex-1">
        <VoiceChannelView channel={channel} actions={<MembersToggle />} />
        <GuildMembersBar guildId={guildId} />
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-1">
      <MessageView
        channelId={channelId}
        title={channel.name ?? "channel"}
        icon={<FiHash size={16} />}
        subtitle={channel.description || undefined}
        actions={<MembersToggle />}
      />
      <GuildMembersBar guildId={guildId} />
    </div>
  );
}
