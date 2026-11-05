import { useEffect, useState } from "react";
import { Link, useMatch, useNavigate, useParams } from "react-router-dom";
import {
  FiHash,
  FiLogOut,
  FiPlus,
  FiSettings,
  FiUserPlus,
  FiVolume2,
} from "react-icons/fi";
import { useGuildStore } from "./guildStore";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import { ChannelType, type Channel } from "../shared/types";
import { useVoiceStore } from "../voice/voiceStore";
import Avatar from "../shared/Avatar";
import SidePanel from "../shared/SidePanel";
import ImageEditButton from "../media/ImageEditButton";
import { putGuildIcon } from "../media/apiClient";
import { errorText } from "../shared/errors";
import { deleteLeaveGuild } from "./apiClient";
import { GuildPermission, allows, useGuildStanding } from "./permissions";

function ChannelLink({
  channel,
  guildId,
  active,
}: {
  channel: Channel;
  guildId: string;
  active: boolean;
}) {
  const isVoice = channel.type === ChannelType.GUILD_VOICE;
  return (
    <Link
      to={`/guild/${guildId}/channel/${channel.id}`}
      className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm transition-colors ${
        active
          ? "bg-white/[0.07] text-white"
          : "text-ink-300 hover:bg-white/[0.04] hover:text-white"
      }`}
    >
      {isVoice ? (
        <FiVolume2 size={14} className="shrink-0 opacity-70" />
      ) : (
        <FiHash size={14} className="shrink-0 opacity-70" />
      )}
      <span className="truncate">{channel.name}</span>
    </Link>
  );
}

/**
 * Who is talking in a voice channel, listed under it Discord-style. This is the
 * server roster, not the SFU room, so it renders for people who have not joined.
 */
function VoiceRoster({ channelId }: { channelId: string }) {
  const participants = useVoiceStore((state) => state.rosters[channelId]);
  const users = useUserStore((state) => state.users);
  // Only ever populated for the channel we are connected to: LiveKit reports
  // audio levels for the room we are in and no other, so a channel you have
  // not joined lists its people without saying which of them is talking.
  const speaking = useVoiceStore((state) => state.speaking);

  if (!participants?.length) return null;

  return (
    <ul className="mt-0.5 space-y-1 pl-8">
      {participants.map((userId) => (
        <li key={userId} className="flex items-center gap-2">
          <Avatar
            name={users[userId]?.username}
            seed={userId}
            size="xs"
            online
            speaking={speaking[userId] ?? false}
          />
          <span className="truncate text-xs text-ink-400">
            {users[userId]?.username ?? "…"}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Two clicks, because getting back in needs someone to invite you. */
function LeaveGuild({ guildId }: { guildId: string }) {
  const removeGuild = useGuildStore((state) => state.removeGuild);
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const leave = async () => {
    setBusy(true);
    setError("");
    try {
      await deleteLeaveGuild(guildId);
      navigate("/guild");
      removeGuild(guildId);
    } catch (err) {
      setError(errorText(err, "Could not leave this guild."));
      setBusy(false);
    }
  };

  return (
    <>
      <button
        className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors hover:bg-white/[0.05] ${
          confirming ? "text-red-300" : "text-ink-300 hover:text-white"
        }`}
        disabled={busy}
        onClick={() => (confirming ? void leave() : setConfirming(true))}
        onBlur={() => setConfirming(false)}
      >
        <FiLogOut size={14} /> {confirming ? "Click again to leave" : "Leave guild"}
      </button>
      {error && <p className="px-2.5 text-xs text-red-300">{error}</p>}
    </>
  );
}

function SectionLabel({
  children,
  action,
}: {
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-2.5 pb-1 pt-3">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-ink-400">
        {children}
      </span>
      {action}
    </div>
  );
}

export default function GuildChannelsBar() {
  const { guildId } = useParams<{ guildId: string }>();
  // channelId belongs to a child route, so it is read from the URL directly
  const channelId = useMatch("/guild/:guildId/channel/:channelId")?.params
    .channelId;
  const {
    getGuild,
    setChannelModalGuildId,
    setInviteModalGuildId,
    setSettingsModalGuildId,
  } = useGuildStore();
  const { getGuildChannels } = useChannelStore();

  const guild = getGuild(guildId ?? "");
  const guildChannels = getGuildChannels(guildId ?? "");
  const textChannels = guildChannels.filter(
    (channel) => channel.type === ChannelType.GUILD_TEXT
  );
  const voiceChannels = guildChannels.filter(
    (channel) => channel.type === ChannelType.GUILD_VOICE
  );
  const standing = useGuildStanding(guildId);
  const canManageGuild = allows(standing, GuildPermission.MANAGE_GUILD);
  const canManageChannels = allows(standing, GuildPermission.MANAGE_CHANNELS);
  const replaceGuild = useGuildStore((state) => state.replaceGuild);
  const [iconError, setIconError] = useState("");

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
    // With no channel picked, the channel list is the whole point of the page,
    // so on a phone it is the page rather than a drawer behind an empty state.
    <SidePanel label="Channels" tourId="guild-channels" inline={!channelId}>
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-white/[0.06] px-4">
        {canManageGuild && guild ? (
          <ImageEditButton
            label="Change the guild icon"
            badgeSize="sm"
            onUpload={async (file) => replaceGuild(await putGuildIcon(guild.id, file))}
            onError={setIconError}
          >
            <Avatar
              name={guild.name}
              seed={guild.id}
              src={guild.icon_url ?? null}
              size="sm"
            />
          </ImageEditButton>
        ) : (
          <Avatar
            name={guild?.name}
            seed={guild?.id ?? ""}
            src={guild?.icon_url ?? null}
            size="sm"
          />
        )}
        <h2 className="min-w-0 flex-1 truncate text-[15px] font-semibold text-white">
          {guild?.name ?? "Guild"}
        </h2>
        {(canManageGuild || canManageChannels) && (
          <button
            onClick={() => setSettingsModalGuildId(guildId ?? null)}
            aria-label="Guild settings"
            className="-mr-1 shrink-0 rounded-lg p-2 text-ink-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <FiSettings size={15} />
          </button>
        )}
      </div>
      {iconError && (
        <p className="border-b border-white/[0.06] px-4 py-2 text-xs text-red-300">
          {iconError}
        </p>
      )}

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        <SectionLabel>Text channels</SectionLabel>
        <div className="space-y-0.5">
          {textChannels.map((channel) => (
            <ChannelLink
              key={channel.id}
              channel={channel}
              guildId={guildId!}
              active={channelId === channel.id}
            />
          ))}
        </div>

        <SectionLabel>Voice channels</SectionLabel>
        <div className="space-y-0.5">
          {voiceChannels.map((channel) => (
            <div key={channel.id}>
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

      <div className="shrink-0 space-y-1 border-t border-white/[0.06] p-2">
        {/* In the channel bar rather than the members panel so it is reachable
            with no channel selected — otherwise a fresh guild has no way in. */}
        <button
          className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-ink-300 transition-colors hover:bg-white/[0.05] hover:text-white"
          onClick={() => setInviteModalGuildId(guildId ?? null)}
        >
          <FiUserPlus size={14} /> Invite people
        </button>

        {canManageChannels && (
          <button
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-ink-300 transition-colors hover:bg-white/[0.05] hover:text-white"
            onClick={() => setChannelModalGuildId(guildId ?? null)}
          >
            <FiPlus size={14} /> Create channel
          </button>
        )}

        {/* The role loads with the member list. Until it has, this cannot tell a
            member from someone it should not be offered to. */}
        {guildId && standing.role && !standing.isOwner && (
          <LeaveGuild guildId={guildId} />
        )}
      </div>
    </SidePanel>
  );
}
