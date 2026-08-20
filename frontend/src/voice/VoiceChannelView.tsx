import { useEffect } from "react";
import {
  FiMic,
  FiMicOff,
  FiPhoneOff,
  FiVolume2,
  FiVolumeX,
} from "react-icons/fi";
import { useAuth } from "../auth/AuthContext";
import { useUserStore } from "../shared/userStore";
import type { Channel } from "../shared/types";
import Avatar from "../shared/Avatar";
import { Button } from "../shared/Button";
import ViewHeader from "../shared/ViewHeader";
import { useVoiceStore } from "./voiceStore";

function ParticipantTile({
  userId,
  isSelf,
  muted,
}: {
  userId: string;
  isSelf: boolean;
  muted: boolean;
}) {
  const user = useUserStore((state) => state.users[userId]);
  const name = user?.username ?? "…";

  return (
    <div className="flex w-32 flex-col items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.02] px-3 py-5 transition-colors hover:border-white/[0.12] sm:w-36">
      <Avatar name={name} seed={userId} size="xl" />
      <div className="flex w-full items-center justify-center gap-1.5">
        <span className="truncate text-sm text-ink-200">{name}</span>
        {isSelf && muted && (
          <FiMicOff size={13} className="shrink-0 text-red-400" />
        )}
      </div>
      {isSelf && (
        <span className="-mt-1.5 text-[10px] uppercase tracking-wide text-ink-500">
          You
        </span>
      )}
    </div>
  );
}

/**
 * Control bar for a live session. Fixed to the bottom of the view so the
 * disconnect button is always reachable, however long the roster gets.
 */
function ControlBar({
  muted,
  deafened,
  onMute,
  onDeafen,
  onLeave,
}: {
  muted: boolean;
  deafened: boolean;
  onMute: () => void;
  onDeafen: () => void;
  onLeave: () => void;
}) {
  const circle =
    "flex h-12 w-12 items-center justify-center rounded-full transition-all duration-200";

  return (
    <div className="glass flex items-center gap-2.5 rounded-full p-2 shadow-lift">
      <button
        onClick={onMute}
        title={muted ? "Unmute" : "Mute"}
        aria-label={muted ? "Unmute" : "Mute"}
        className={`${circle} ${
          muted
            ? "bg-red-500/90 text-white hover:bg-red-500"
            : "bg-white/[0.08] text-ink-100 hover:bg-white/[0.14]"
        }`}
      >
        {muted ? <FiMicOff size={17} /> : <FiMic size={17} />}
      </button>
      <button
        onClick={onDeafen}
        title={deafened ? "Undeafen" : "Deafen"}
        aria-label={deafened ? "Undeafen" : "Deafen"}
        className={`${circle} ${
          deafened
            ? "bg-red-500/90 text-white hover:bg-red-500"
            : "bg-white/[0.08] text-ink-100 hover:bg-white/[0.14]"
        }`}
      >
        {deafened ? <FiVolumeX size={17} /> : <FiVolume2 size={17} />}
      </button>
      <button
        onClick={onLeave}
        title="Disconnect"
        aria-label="Disconnect"
        className={`${circle} bg-red-500 text-white hover:bg-red-400`}
      >
        <FiPhoneOff size={17} />
      </button>
    </div>
  );
}

export default function VoiceChannelView({
  channel,
  actions,
}: {
  channel: Channel;
  actions?: React.ReactNode;
}) {
  const {
    activeChannelId,
    connecting,
    error,
    muted,
    deafened,
    join,
    leave,
    toggleMute,
    toggleDeafen,
    fetchRoster,
    getRoster,
  } = useVoiceStore();
  const { getCurrentUser } = useAuth();
  const fetchUsers = useUserStore((state) => state.fetchUsers);

  const connected = activeChannelId === channel.id;
  const participants = getRoster(channel.id);
  const currentUserId = getCurrentUser()?.id;

  // The roster is server state; anyone can be in here before we arrive
  useEffect(() => {
    void fetchRoster(channel.id);
  }, [channel.id, fetchRoster]);

  useEffect(() => {
    if (participants.length) void fetchUsers(participants);
  }, [participants, fetchUsers]);

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-ink-950">
      <ViewHeader
        icon={<FiVolume2 size={16} />}
        title={channel.name ?? "voice"}
        subtitle={
          participants.length > 0
            ? `${participants.length} in voice`
            : "Voice channel"
        }
        actions={actions}
      />

      <div className="relative flex flex-1 flex-col items-center justify-center gap-10 overflow-y-auto p-6">
        {/* Soft stage light behind the roster while a call is live */}
        {connected && (
          <div
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-1/3 h-96 w-96 max-w-[90vw] -translate-x-1/2 -translate-y-1/2 rounded-full bg-rain-500/10 blur-[100px]"
          />
        )}

        {participants.length > 0 ? (
          <div className="relative flex flex-wrap justify-center gap-3">
            {participants.map((userId) => (
              <ParticipantTile
                key={userId}
                userId={userId}
                isSelf={userId === currentUserId}
                muted={muted}
              />
            ))}
          </div>
        ) : (
          <div className="relative flex flex-col items-center gap-3 text-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-ink-400">
              <FiVolume2 size={24} />
            </span>
            <p className="text-lg font-medium text-ink-100">
              Nobody is in here yet
            </p>
            <p className="max-w-xs text-sm text-ink-400">
              Join the channel and anyone else in the guild can drop in.
            </p>
          </div>
        )}

        {error && (
          <p className="relative max-w-md rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-2.5 text-center text-sm text-amber-300">
            {error}
          </p>
        )}

        <div className="relative">
          {connected ? (
            <ControlBar
              muted={muted}
              deafened={deafened}
              onMute={() => void toggleMute()}
              onDeafen={() => void toggleDeafen()}
              onLeave={() => void leave()}
            />
          ) : (
            <Button
              variant="primary"
              size="lg"
              loading={connecting}
              onClick={() => void join(channel.id)}
              icon={!connecting ? <FiMic size={16} /> : undefined}
            >
              {connecting ? "Connecting…" : "Join voice"}
            </Button>
          )}
        </div>

        {connected && currentUserId && !participants.includes(currentUserId) && (
          <p className="relative text-xs text-ink-500">
            Connected. Waiting for the roster to catch up…
          </p>
        )}
      </div>
    </div>
  );
}
