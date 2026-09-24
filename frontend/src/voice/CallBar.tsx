import { useEffect } from "react";
import {
  FiMic,
  FiMicOff,
  FiPhone,
  FiPhoneOff,
  FiVolume2,
  FiVolumeX,
} from "react-icons/fi";
import { useAuth } from "../auth/AuthContext";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import { useUserStore } from "../shared/userStore";
import VolumeControl from "./VolumeControl";
import { useVoiceStore } from "./voiceStore";

/**
 * Calling inside a DM or a group DM, in two pieces.
 *
 * `CallButton` is the way in and lives in the view header, top right, where
 * every other chat app puts it. `CallBar` is the strip above the composer and
 * appears **only while a call exists**: who is in it, and the controls if you
 * are one of them.
 *
 * Splitting them keeps one action in one place. The strip deliberately does not
 * repeat the join button, because the header already owns starting and joining.
 *
 * A guild voice channel is a room you walk into and stand in, so it gets a
 * whole view. A DM call is an event: it starts, the other side has to find out,
 * and it ends. It needs no new plumbing for that — the roster comes from the
 * same webhook-driven VOICE_STATE events that fill a guild channel's roster,
 * and those reach every member of the channel whether or not they are in the
 * room, which is what lets the other side ring.
 */

/**
 * Shared state for both pieces.
 *
 * `fetchOnMount` belongs to the header button alone, because that is the one
 * that is always rendered. A call may have started before this view was opened
 * and nothing else would ask; letting both components fetch would just be the
 * same request twice.
 */
function useCallState(channelId: string, fetchOnMount = false) {
  const { getRoster, fetchRoster, activeChannelId } = useVoiceStore();
  const { getCurrentUser } = useAuth();
  const { getUser, fetchUsers } = useUserStore();

  const roster = getRoster(channelId);
  const selfId = getCurrentUser()?.id;

  useEffect(() => {
    if (fetchOnMount) void fetchRoster(channelId);
  }, [channelId, fetchOnMount, fetchRoster]);

  useEffect(() => {
    if (roster.length > 0) fetchUsers(roster);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roster.length, fetchUsers]);

  const others = roster.filter((id) => id !== selfId);

  return {
    roster,
    others,
    inThisCall: activeChannelId === channelId,
    names: others
      .map((id) => getUser(id)?.username)
      .filter(Boolean)
      .join(", "),
    getUser,
  };
}

/** Header action: start a call, or join the one already running. */
export function CallButton({ channelId }: { channelId: string }) {
  const { roster, inThisCall } = useCallState(channelId, true);
  const { join, connecting } = useVoiceStore();

  // While you are in the call the strip below carries the controls, including
  // hanging up, so a second control here would be one too many.
  if (inThisCall) return null;

  if (roster.length > 0) {
    return (
      <Button
        size="sm"
        variant="primary"
        icon={<FiPhone size={14} />}
        loading={connecting}
        onClick={() => void join(channelId)}
      >
        Join call
      </Button>
    );
  }

  return (
    <button
      onClick={() => void join(channelId)}
      disabled={connecting}
      aria-label="Start a call"
      title="Start a call"
      className="rounded-lg p-2 text-ink-300 transition-colors hover:bg-white/5 hover:text-white disabled:opacity-50"
    >
      <FiPhone size={17} />
    </button>
  );
}

/** The strip above the composer. Nothing at all when there is no call. */
export default function CallBar({ channelId }: { channelId: string }) {
  const { roster, others, inThisCall, names, getUser } = useCallState(channelId);
  const { leave, toggleMute, toggleDeafen, muted, deafened, error, speaking } =
    useVoiceStore();

  if (!inThisCall && roster.length === 0) return null;

  const circle =
    "flex h-9 w-9 items-center justify-center rounded-full transition-all duration-200";

  return (
    <div className="shrink-0 px-3 pt-2 sm:px-6">
      <div
        className={`flex flex-wrap items-center gap-3 rounded-2xl border px-3 py-2.5 ${
          inThisCall
            ? "border-emerald-400/25 bg-emerald-400/[0.06]"
            : "border-rain-400/30 bg-rain-400/[0.07]"
        }`}
      >
        <span className="flex -space-x-2">
          {roster.slice(0, 4).map((userId) => (
            <Avatar
              key={userId}
              name={getUser(userId)?.username}
              seed={userId}
              size="xs"
              speaking={speaking[userId] ?? false}
              className="ring-2 ring-ink-950"
            />
          ))}
        </span>

        <span className="min-w-0 flex-1 text-sm">
          {inThisCall ? (
            <span className="text-emerald-200">
              In a call{names ? ` with ${names}` : ", waiting for someone"}
            </span>
          ) : (
            <span className="text-rain-100">
              {names || "Someone"} {others.length > 1 ? "are" : "is"} in a call
            </span>
          )}
        </span>

        {inThisCall && (
          <span className="flex items-center gap-1.5">
            <button
              onClick={() => void toggleMute()}
              title={muted ? "Unmute" : "Mute"}
              aria-label={muted ? "Unmute" : "Mute"}
              className={`${circle} ${
                muted
                  ? "bg-red-500/90 text-white hover:bg-red-500"
                  : "bg-white/[0.08] text-ink-100 hover:bg-white/[0.14]"
              }`}
            >
              {muted ? <FiMicOff size={15} /> : <FiMic size={15} />}
            </button>
            <button
              onClick={() => void toggleDeafen()}
              title={deafened ? "Undeafen" : "Deafen"}
              aria-label={deafened ? "Undeafen" : "Deafen"}
              className={`${circle} ${
                deafened
                  ? "bg-red-500/90 text-white hover:bg-red-500"
                  : "bg-white/[0.08] text-ink-100 hover:bg-white/[0.14]"
              }`}
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
        )}
      </div>

      {inThisCall && error && (
        <p className="mt-1.5 px-1 text-[11px] text-amber-300">{error}</p>
      )}
    </div>
  );
}
