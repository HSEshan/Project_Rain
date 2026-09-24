import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  FiMic,
  FiMicOff,
  FiPhoneOff,
  FiVolume2,
  FiVolumeX,
} from "react-icons/fi";
import Avatar from "../shared/Avatar";
import { useChannelStore } from "../shared/channelStore";
import { useUserStore } from "../shared/userStore";
import { ChannelType } from "../shared/types";
import { useGuildStore } from "../guild/guildStore";
import VolumeControl from "./VolumeControl";
import { useVoiceStore } from "./voiceStore";

/**
 * The call you are in, from anywhere in the app.
 *
 * The session already outlives navigation (it lives in `voiceStore`, not in a
 * view), but its controls did not: muting meant going back to the DM or the
 * voice channel first. This is those controls, plus a link back.
 *
 * **Hidden on the call's own page**, where `CallBar` or `VoiceChannelView`
 * already carries the same buttons; two hang-up buttons on one screen is one
 * too many.
 *
 * **In the layout flow rather than `position: fixed`.** Floating over the page
 * would sit on top of whichever composer and send button happen to be in that
 * corner, and on a phone there is no free corner. As a strip under the content
 * it only ever takes room, never covers anything.
 */
export default function CallDock() {
  const {
    activeChannelId,
    muted,
    deafened,
    speaking,
    error,
    toggleMute,
    toggleDeafen,
    leave,
    getRoster,
  } = useVoiceStore();
  const channel = useChannelStore((state) =>
    activeChannelId ? state.channels[activeChannelId] : undefined
  );
  const participants = useChannelStore((state) =>
    activeChannelId ? state.participants[activeChannelId] : undefined
  );
  const guild = useGuildStore((state) =>
    channel?.guild_id
      ? state.guilds.find((item) => item.id === channel.guild_id)
      : undefined
  );
  const { getUser, fetchUsers } = useUserStore();
  const { pathname } = useLocation();

  const roster = activeChannelId ? getRoster(activeChannelId) : [];

  useEffect(() => {
    if (roster.length > 0) fetchUsers(roster);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roster.length, fetchUsers]);

  if (!activeChannelId) return null;

  const isGuildVoice = channel?.type === ChannelType.GUILD_VOICE;
  const href = isGuildVoice
    ? `/guild/${channel?.guild_id}/channel/${activeChannelId}`
    : `/dm/${activeChannelId}`;

  if (pathname === href) return null;

  // Titled the way the call's own page titles it, so the dock and the page it
  // links to read as the same place.
  const names = (participants ?? [])
    .map((id) => getUser(id)?.username)
    .filter(Boolean)
    .join(", ");
  const title = isGuildVoice
    ? channel?.name
    : (channel?.type === ChannelType.GROUP_DM && channel.name) || names;
  const subtitle = isGuildVoice ? guild?.name : "Call";

  const circle =
    "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-200";
  const toggle = (on: boolean) =>
    on
      ? "bg-red-500/90 text-white hover:bg-red-500"
      : "bg-white/[0.08] text-ink-100 hover:bg-white/[0.14]";

  return (
    <div className="shrink-0 px-2 pb-2 pt-1 sm:px-4 sm:pb-3 animate-fade-up">
      <div
        role="region"
        aria-label="Current call"
        className="mx-auto flex max-w-3xl items-center gap-3 rounded-2xl border border-emerald-400/25 bg-ink-900/95 px-3 py-2 shadow-lift backdrop-blur-xl"
      >
        <Link
          to={href}
          title="Go to call"
          className="group flex min-w-0 flex-1 items-center gap-3 rounded-lg"
        >
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/60 motion-reduce:hidden" />
            <span className="relative h-2.5 w-2.5 rounded-full bg-emerald-400" />
          </span>

          <span className="min-w-0">
            <span className="block text-[11px] font-semibold uppercase tracking-wider text-emerald-300">
              Voice connected
            </span>
            <span className="block truncate text-sm text-ink-100 group-hover:text-white group-hover:underline">
              {title || "Call"}
              {subtitle && (
                <span className="text-ink-400"> · {subtitle}</span>
              )}
            </span>
          </span>

          {/* Who is here and who is talking. Hidden on a phone, where the
              buttons need the width more than the faces do. */}
          <span className="ml-auto hidden -space-x-2 sm:flex">
            {roster.slice(0, 5).map((userId) => (
              <Avatar
                key={userId}
                name={getUser(userId)?.username}
                seed={userId}
                size="xs"
                speaking={speaking[userId] ?? false}
                className="ring-2 ring-ink-900"
              />
            ))}
          </span>
        </Link>

        <span className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={() => void toggleMute()}
            title={muted ? "Unmute" : "Mute"}
            aria-label={muted ? "Unmute" : "Mute"}
            className={`${circle} ${toggle(muted)}`}
          >
            {muted ? <FiMicOff size={15} /> : <FiMic size={15} />}
          </button>
          <button
            onClick={() => void toggleDeafen()}
            title={deafened ? "Undeafen" : "Deafen"}
            aria-label={deafened ? "Undeafen" : "Deafen"}
            className={`${circle} ${toggle(deafened)}`}
          >
            {deafened ? <FiVolumeX size={15} /> : <FiVolume2 size={15} />}
          </button>
          <VolumeControl compact />
          <button
            onClick={() => void leave()}
            title="Hang up"
            aria-label="Hang up"
            className={`${circle} bg-red-500/90 text-white hover:bg-red-500`}
          >
            <FiPhoneOff size={15} />
          </button>
        </span>
      </div>

      {error && (
        <p className="mx-auto mt-1 max-w-3xl px-2 text-[11px] text-amber-300">
          {error}
        </p>
      )}
    </div>
  );
}
