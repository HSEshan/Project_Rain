import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { FiPhone, FiX } from "react-icons/fi";
import Avatar from "../shared/Avatar";
import { useChannelStore } from "../shared/channelStore";
import { ChannelType } from "../shared/types";
import { useUserStore } from "../shared/userStore";
import { useIncomingCallStore, type IncomingCall } from "./incomingCall";
import { useVoiceStore } from "./voiceStore";

/**
 * "X is calling you", from any page, until it is answered, dismissed or over.
 *
 * Fixed to the top of the screen, unlike `CallDock`, because it has to be seen
 * rather than merely be reachable, and it is short lived. On a phone it spans
 * the width; on a desktop it sits top centre.
 */
export default function IncomingCallBanner() {
  const calls = useIncomingCallStore((state) => state.calls);
  const channels = useChannelStore((state) => state.channels);

  // Only DMs and group DMs ring. An unloaded channel waits rather than guessing.
  const ringing = Object.values(calls)
    .filter((call) => {
      const type = channels[call.channelId]?.type;
      return type === ChannelType.DM || type === ChannelType.GROUP_DM;
    })
    .sort((a, b) => a.startedAt - b.startedAt);

  useRingingTitle(ringing.length > 0);

  if (ringing.length === 0) return null;

  return (
    <div
      className="pointer-events-none fixed inset-x-0 top-0 z-[60] flex flex-col items-center gap-2 px-2 pt-2 sm:pt-4"
      role="region"
      aria-label="Incoming calls"
    >
      {ringing.map((call) => (
        <Ring key={call.channelId} call={call} />
      ))}
    </div>
  );
}

function Ring({ call }: { call: IncomingCall }) {
  const navigate = useNavigate();
  const dismiss = useIncomingCallStore((state) => state.dismiss);
  const join = useVoiceStore((state) => state.join);
  const inOtherCall = useVoiceStore((state) => state.activeChannelId !== null);
  const channel = useChannelStore((state) => state.channels[call.channelId]);
  const { getUser, fetchUsers } = useUserStore();

  useEffect(() => {
    fetchUsers([call.callerId]);
  }, [call.callerId, fetchUsers]);

  const caller = getUser(call.callerId)?.username ?? "Someone";
  const isGroup = channel?.type === ChannelType.GROUP_DM;
  const where = isGroup ? channel?.name || "a group" : null;

  const answer = () => {
    navigate(`/dm/${call.channelId}`);
    void join(call.channelId);
  };

  return (
    <div
      role="alertdialog"
      aria-label={`${caller} is calling`}
      className="pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-2xl border border-emerald-400/30 bg-ink-900/95 px-3 py-2.5 shadow-lift backdrop-blur-xl animate-fade-up"
    >
      <span className="relative shrink-0">
        <span className="absolute -inset-1 animate-ping rounded-full bg-emerald-400/30 motion-reduce:hidden" />
        <Avatar name={caller} seed={call.callerId} size="sm" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="block text-[11px] font-semibold uppercase tracking-wider text-emerald-300">
          Incoming call
        </span>
        <span className="block truncate text-sm text-ink-100">
          {caller}
          {where && <span className="text-ink-400"> in {where}</span>}
        </span>
        {inOtherCall && (
          <span className="block text-[11px] text-ink-400">
            Joining ends your current call
          </span>
        )}
      </span>

      <button
        onClick={() => dismiss(call.channelId)}
        title="Dismiss"
        aria-label="Dismiss call"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/[0.08] text-ink-100 transition-colors hover:bg-white/[0.14]"
      >
        <FiX size={16} />
      </button>
      <button
        onClick={answer}
        title="Join call"
        aria-label="Join call"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white transition-colors hover:bg-emerald-400"
      >
        <FiPhone size={16} />
      </button>
    </div>
  );
}

/**
 * Alternate the tab title while something rings, so a call reaches someone
 * whose tab is in the background. Restores whatever the title was.
 */
function useRingingTitle(ringing: boolean) {
  useEffect(() => {
    if (!ringing) return;
    const original = document.title;
    let flip = false;
    const timer = setInterval(() => {
      flip = !flip;
      document.title = flip ? "Incoming call" : original;
    }, 1000);
    return () => {
      clearInterval(timer);
      document.title = original;
    };
  }, [ringing]);
}
