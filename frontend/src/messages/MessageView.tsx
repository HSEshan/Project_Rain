import { useEffect, useMemo, useRef, useState } from "react";
import { FiSend } from "react-icons/fi";
import { type Message } from "../shared/types";
import { useWebSocket } from "../utils/WebsocketProvider";
import { useMessageStore } from "../shared/messageStore";
import { EventType } from "../utils/eventType";
import { useAuth } from "../auth/AuthContext";
import { useUserStore } from "../shared/userStore";
import Avatar from "../shared/Avatar";
import ViewHeader from "../shared/ViewHeader";

/** Messages from the same person within this window share one header. */
const GROUP_WINDOW_MS = 5 * 60 * 1000;

function dayLabel(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (sameDay(date, today)) return "Today";
  if (sameDay(date, yesterday)) return "Yesterday";
  return date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}

const timeLabel = (iso: string) =>
  new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

type Row =
  | { kind: "day"; key: string; label: string }
  | { kind: "message"; key: string; message: Message; grouped: boolean };

/**
 * Flatten the message list into render rows: date separators, plus a flag for
 * whether each message continues the previous author's run. Doing this once
 * here keeps the row component free of neighbour lookups.
 */
function buildRows(messages: Message[]): Row[] {
  const rows: Row[] = [];
  let lastDay = "";
  let previous: Message | undefined;

  for (const message of messages) {
    const day = new Date(message.created_at).toDateString();
    if (day !== lastDay) {
      rows.push({
        kind: "day",
        key: "day-" + day,
        label: dayLabel(message.created_at),
      });
      lastDay = day;
      previous = undefined;
    }
    const grouped =
      !!previous &&
      previous.sender_id === message.sender_id &&
      new Date(message.created_at).getTime() -
        new Date(previous.created_at).getTime() <
        GROUP_WINDOW_MS;

    rows.push({ kind: "message", key: message.id, message, grouped });
    previous = message;
  }
  return rows;
}

function MessageRow({
  message,
  grouped,
  isMine,
  selfName,
}: {
  message: Message;
  grouped: boolean;
  isMine: boolean;
  selfName?: string;
}) {
  const author = useUserStore((state) => state.users[message.sender_id]);
  // The label says "You", but the avatar still needs a real name to derive an
  // initial from — the user store does not necessarily hold the current user.
  const authorName = isMine ? selfName : author?.username;
  const label = isMine ? "You" : authorName ?? "…";

  return (
    <div
      className={`group flex gap-3 px-4 transition-colors hover:bg-white/[0.02] sm:px-6 ${
        grouped ? "py-0.5" : "pb-0.5 pt-4"
      }`}
    >
      {grouped ? (
        // Keeps the text aligned and shows the timestamp only on hover, which
        // is what stops a long run of messages becoming a wall of metadata.
        <span className="w-8 shrink-0 pt-0.5 text-right font-mono text-[10px] leading-6 text-ink-500 opacity-0 transition-opacity group-hover:opacity-100">
          {timeLabel(message.created_at)}
        </span>
      ) : (
        <Avatar
          name={authorName}
          seed={message.sender_id}
          size="sm"
          className="mt-0.5"
        />
      )}

      <div className="min-w-0 flex-1">
        {!grouped && (
          <p className="mb-0.5 flex items-baseline gap-2">
            <span className="text-sm font-semibold text-white">{label}</span>
            <span className="font-mono text-[10px] text-ink-500">
              {timeLabel(message.created_at)}
            </span>
          </p>
        )}
        <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed text-ink-200">
          {message.content}
        </p>
      </div>
    </div>
  );
}

export interface MessageViewProps {
  channelId: string;
  /** Rendered as the header: DM participants, or the channel name in a guild. */
  title: string;
  icon?: React.ReactNode;
  subtitle?: string;
  actions?: React.ReactNode;
}

/**
 * Chat surface for one channel. Channel-agnostic on purpose — DMs and guild
 * text channels are the same thing to the message store and the WS protocol.
 */
export function MessageView({
  channelId,
  title,
  icon,
  subtitle,
  actions,
}: MessageViewProps) {
  const { getChannelMessages, fetchChannelMessages } = useMessageStore();
  const { fetchUsers } = useUserStore();
  const { getWs } = useWebSocket();
  const { getCurrentUser } = useAuth();

  const messages = getChannelMessages(channelId);
  const ws = getWs();
  const currentUser = getCurrentUser();
  const currentUserId = currentUser?.id;

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState("");

  const rows = useMemo(() => buildRows(messages), [messages]);

  const scrollToBottom = (smooth = false) => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: smooth ? "smooth" : undefined,
    });
  };

  useEffect(() => {
    if (!channelId) return;
    setIsInitialLoad(true);
    setDraft("");
    setSendError("");
    fetchChannelMessages(channelId);
  }, [channelId, fetchChannelMessages]);

  // Guild channels can carry messages from members we have never loaded.
  // Keyed on length, not the array: the store returns a fresh array each render.
  useEffect(() => {
    const senderIds = [...new Set(messages.map((m) => m.sender_id))];
    if (senderIds.length > 0) fetchUsers(senderIds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, fetchUsers]);

  useEffect(() => {
    if (messages.length === 0) return;
    if (isInitialLoad) {
      setIsInitialLoad(false);
      scrollToBottom(false);
    } else {
      scrollToBottom(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelId, messages.length]);

  // Grow the composer with its content, up to a cap, then scroll internally.
  const resizeInput = () => {
    const node = inputRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = Math.min(node.scrollHeight, 160) + "px";
  };

  const sendMessage = () => {
    const text = draft.trim();
    if (!text) return;
    if (!ws) {
      setSendError("Not connected. Reconnecting, your message was not sent.");
      return;
    }
    ws.send(
      JSON.stringify({
        event_type: EventType.MESSAGE,
        receiver_id: channelId,
        text,
      })
    );
    setDraft("");
    setSendError("");
    requestAnimationFrame(resizeInput);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex min-w-0 flex-1 flex-col bg-ink-950">
      <ViewHeader
        icon={icon}
        title={title}
        subtitle={subtitle}
        actions={actions}
      />

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overscroll-contain py-2"
      >
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <p className="text-base font-medium text-ink-200">
              This is the beginning of {title}
            </p>
            <p className="max-w-sm text-sm text-ink-400">
              No messages yet. Say something to get it started.
            </p>
          </div>
        ) : (
          rows.map((row) =>
            row.kind === "day" ? (
              <div
                key={row.key}
                className="flex items-center gap-3 px-4 py-4 sm:px-6"
              >
                <span className="h-px flex-1 bg-white/[0.07]" />
                <span className="rounded-full border border-white/[0.07] px-2.5 py-0.5 text-[11px] font-medium text-ink-400">
                  {row.label}
                </span>
                <span className="h-px flex-1 bg-white/[0.07]" />
              </div>
            ) : (
              <MessageRow
                key={row.key}
                message={row.message}
                grouped={row.grouped}
                isMine={row.message.sender_id === currentUserId}
                selfName={currentUser?.username}
              />
            )
          )
        )}
      </div>

      <div className="shrink-0 px-3 pb-4 pt-2 sm:px-6">
        {sendError && <p className="mb-2 text-xs text-amber-300">{sendError}</p>}
        <div className="flex items-end gap-2 rounded-2xl border border-white/[0.08] bg-ink-850/80 p-2 transition-colors focus-within:border-rain-400/40 focus-within:ring-2 focus-within:ring-rain-400/20">
          <textarea
            ref={inputRef}
            rows={1}
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              resizeInput();
            }}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${title}`}
            className="max-h-40 flex-1 resize-none bg-transparent px-2.5 py-2 text-[15px] text-white placeholder-ink-500 focus:outline-none"
          />
          <button
            onClick={sendMessage}
            disabled={!draft.trim()}
            aria-label="Send message"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rain-400 to-iris-400 text-ink-950 transition-all hover:brightness-110 disabled:from-ink-700 disabled:to-ink-700 disabled:text-ink-500"
          >
            <FiSend size={15} />
          </button>
        </div>
        <p className="mt-1.5 hidden px-1 text-[11px] text-ink-500 sm:block">
          <kbd className="font-sans">Enter</kbd> to send ·{" "}
          <kbd className="font-sans">Shift + Enter</kbd> for a new line
        </p>
      </div>
    </div>
  );
}
