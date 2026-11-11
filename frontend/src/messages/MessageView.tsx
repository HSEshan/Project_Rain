import { useEffect, useMemo, useRef, useState } from "react";
import { FiEdit2, FiImage, FiSend, FiTrash2, FiX } from "react-icons/fi";
import { type Attachment, type Message } from "../shared/types";
import { useWebSocket } from "../utils/WebsocketProvider";
import { useMessageStore } from "../shared/messageStore";
import { useChannelStore } from "../shared/channelStore";
import { deleteMessage, patchMessage } from "../shared/messageApiClient";
import { errorText } from "../shared/errors";
import { useGuildStore } from "../guild/guildStore";
import {
  GuildPermission,
  allows,
  outranks,
  standingOf,
  useGuildStanding,
} from "../guild/permissions";
import { eventBus } from "../utils/EventBus";
import {
  EventAction,
  EventType,
  TargetType,
  type EventPayload,
} from "../utils/eventType";
import { useAuth } from "../auth/AuthContext";
import { useUserStore } from "../shared/userStore";
import Avatar from "../shared/Avatar";
import ViewHeader from "../shared/ViewHeader";
import ProfileTrigger from "../profile/ProfileTrigger";
import AttachmentGallery from "../media/AttachmentGallery";
import EmojiPicker from "./EmojiPicker";
import { isJumboEmoji } from "./emoji";
import { useAttachmentDrafts } from "../media/useAttachmentDrafts";
import {
  ACCEPTED_IMAGE_TYPES,
  MAX_ATTACHMENTS_PER_MESSAGE,
} from "../media/apiClient";

/** The gateway's MAX_MESSAGE_LENGTH; it drops anything longer. */
const MAX_DRAFT_LENGTH = 4000;

/**
 * Put `insert` at the textarea's caret, replacing any selection, and move the
 * caret after it. Null when the result would exceed the length limit. The
 * textarea keeps its selection while the emoji picker has focus, so it is still
 * there to read when a pick arrives.
 */
function insertAtCaret(
  node: HTMLTextAreaElement | null,
  value: string,
  insert: string
): { next: string; place: () => void } | null {
  const start = node?.selectionStart ?? value.length;
  const end = node?.selectionEnd ?? value.length;
  const next = value.slice(0, start) + insert + value.slice(end);
  if (next.length > MAX_DRAFT_LENGTH) return null;
  const caret = start + insert.length;
  return { next, place: () => node?.setSelectionRange(caret, caret) };
}

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

/**
 * The time without its AM/PM, for the gutter beside a grouped message. The
 * gutter is only as wide as an avatar, and "10:42 AM" is not; the full time is
 * one line up in the group's header and in the title.
 */
const shortTimeLabel = (iso: string) =>
  new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" })
    .formatToParts(new Date(iso))
    .filter((part) => part.type !== "dayPeriod")
    .map((part) => part.value)
    .join("")
    .trim();

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

/** Edit in place. Enter saves and Escape cancels, as in the composer. */
function MessageEditor({
  message,
  onDone,
}: {
  message: Message;
  onDone: () => void;
}) {
  const updateMessage = useMessageStore((state) => state.updateMessage);
  const [text, setText] = useState(message.content);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    if (text === message.content) return onDone();
    setBusy(true);
    setError("");
    try {
      const saved = await patchMessage(message.id, text);
      // Yours is the one client that must not wait for the event to catch up
      updateMessage(message.id, {
        content: saved.content,
        edited_at: saved.edited_at,
      });
      onDone();
    } catch (err) {
      setError(errorText(err, "Could not save that edit."));
      setBusy(false);
    }
  };

  return (
    // `relative` so the picker's popover anchors to the editor
    <div className="relative mt-0.5">
      <textarea
        ref={editorRef}
        autoFocus
        aria-label="Edit message"
        value={text}
        rows={Math.min(text.split("\n").length, 8)}
        maxLength={MAX_DRAFT_LENGTH}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onDone();
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void save();
          }
        }}
        className="w-full resize-none rounded-lg border border-white/10 bg-ink-850/80 px-3 py-2 text-[15px] text-white focus:outline-none focus:ring-2 focus:ring-rain-400/60"
      />
      <div className="flex items-center gap-2">
        <EmojiPicker
          disabled={busy}
          onPick={(emoji) => {
            const result = insertAtCaret(editorRef.current, text, emoji);
            if (!result) return;
            setText(result.next);
            requestAnimationFrame(result.place);
          }}
        />
        {error ? (
          <p className="text-xs text-red-300">{error}</p>
        ) : (
          <p className="text-[11px] text-ink-400">
            Enter to save, Escape to cancel
          </p>
        )}
      </div>
    </div>
  );
}

function MessageRow({
  message,
  grouped,
  isMine,
  canDelete,
  selfName,
}: {
  message: Message;
  grouped: boolean;
  isMine: boolean;
  canDelete: boolean;
  selfName?: string;
}) {
  const removeMessage = useMessageStore((state) => state.removeMessage);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");

  const remove = async () => {
    setError("");
    try {
      await deleteMessage(message.id);
      removeMessage(message.id);
    } catch (err) {
      setError(errorText(err, "Could not delete that message."));
      setConfirming(false);
    }
  };

  const author = useUserStore((state) => state.users[message.sender_id]);
  // The label says "You", but the avatar still needs a real name to derive an
  // initial from — the user store does not necessarily hold the current user.
  const authorName = isMine ? selfName : author?.username;
  const label = isMine ? "You" : authorName ?? "…";

  return (
    <div
      className={`group relative flex gap-3 px-4 transition-colors hover:bg-white/[0.02] sm:px-6 ${
        grouped ? "py-0.5" : "pb-0.5 pt-4"
      }`}
    >
      {(isMine || canDelete) && !editing && (
        // A tap on a phone sets :hover, so this needs nothing of its own there.
        // No pointer events until then, or an invisible delete button would sit
        // over the end of the first line of text.
        <div className="pointer-events-none absolute right-4 top-0 z-10 flex items-center gap-0.5 rounded-lg border border-white/[0.07] bg-ink-900 p-0.5 opacity-0 transition-opacity focus-within:pointer-events-auto focus-within:opacity-100 group-hover:pointer-events-auto group-hover:opacity-100 sm:right-6">
          {confirming ? (
            <>
              <button
                onClick={() => void remove()}
                className="rounded-md px-2 py-0.5 text-xs font-medium text-red-300 hover:bg-red-500/15"
              >
                Delete
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="rounded-md px-2 py-0.5 text-xs text-ink-300 hover:bg-white/5"
              >
                Keep
              </button>
            </>
          ) : (
            <>
              {isMine && (
                <button
                  onClick={() => setEditing(true)}
                  aria-label="Edit message"
                  className="rounded-md p-1.5 text-ink-400 hover:bg-white/5 hover:text-white"
                >
                  <FiEdit2 size={13} />
                </button>
              )}
              <button
                onClick={() => setConfirming(true)}
                aria-label="Delete message"
                className="rounded-md p-1.5 text-ink-400 hover:bg-white/5 hover:text-red-300"
              >
                <FiTrash2 size={13} />
              </button>
            </>
          )}
        </div>
      )}
      {grouped ? (
        // Keeps the text aligned and shows the timestamp only on hover, which
        // is what stops a long run of messages becoming a wall of metadata.
        <span
          title={timeLabel(message.created_at)}
          className="w-8 shrink-0 whitespace-nowrap pt-0.5 text-right font-mono text-[10px] leading-6 text-ink-500 opacity-0 transition-opacity group-hover:opacity-100"
        >
          {shortTimeLabel(message.created_at)}
        </span>
      ) : (
        <ProfileTrigger
          userId={message.sender_id}
          label={authorName ? `View ${authorName}` : "View profile"}
          className="mt-0.5 self-start"
        >
          <Avatar name={authorName} seed={message.sender_id} size="sm" />
        </ProfileTrigger>
      )}

      <div className="min-w-0 flex-1">
        {!grouped && (
          <p className="mb-0.5 flex min-w-0 items-baseline gap-2">
            {/* The name gives way to the time, never the other way round: a
                shrinking time breaks at its space and drops "AM" a line. */}
            <ProfileTrigger userId={message.sender_id} className="min-w-0">
              <span className="block truncate text-sm font-semibold text-white">
                {label}
              </span>
            </ProfileTrigger>
            <span className="shrink-0 whitespace-nowrap font-mono text-[10px] text-ink-500">
              {timeLabel(message.created_at)}
            </span>
          </p>
        )}
        {/* A message can be images alone, and an empty paragraph would still
            take a line of height above them. */}
        {editing ? (
          <MessageEditor message={message} onDone={() => setEditing(false)} />
        ) : (
          message.content && (
            <p
              className={`whitespace-pre-wrap break-words text-ink-200 ${
                isJumboEmoji(message.content)
                  ? "py-0.5 text-4xl leading-tight"
                  : "text-[15px] leading-relaxed"
              }`}
            >
              {message.content}
              {message.edited_at && (
                <span
                  title={new Date(message.edited_at).toLocaleString()}
                  className="ml-1.5 text-[10px] text-ink-500"
                >
                  (edited)
                </span>
              )}
            </p>
          )
        )}
        {error && <p className="text-xs text-red-300">{error}</p>}
        <AttachmentGallery attachments={message.attachments ?? []} />
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
  /**
   * Slot directly above the composer. The DM views put the call bar here so it
   * sits with the controls rather than in the scrolling message list, where it
   * would drift out of view mid-call.
   */
  aboveComposer?: React.ReactNode;
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
  aboveComposer,
}: MessageViewProps) {
  const { getChannelMessages, fetchChannelMessages } = useMessageStore();
  const { fetchUsers } = useUserStore();
  const { getWs } = useWebSocket();
  const { getCurrentUser } = useAuth();

  const messages = getChannelMessages(channelId);
  const ws = getWs();
  const currentUser = getCurrentUser();

  // Moderation only exists in a guild. A DM has no guild, so no standing, so
  // `allows` is false and only your own messages get a delete button.
  const guildId = useChannelStore(
    (state) => state.channels[channelId]?.guild_id ?? undefined
  );
  const standing = useGuildStanding(guildId);
  const guild = useGuildStore((state) =>
    state.guilds.find((g) => g.id === guildId)
  );
  const guildMembers = useGuildStore((state) =>
    guildId ? state.members[guildId] : undefined
  );
  const canModerate = (authorId: string) => {
    if (!allows(standing, GuildPermission.MANAGE_MESSAGES)) return false;
    const author = guildMembers?.find((m) => m.user_id === authorId);
    // Someone who has left has no standing to be outranked by
    return !author || outranks(standing, standingOf(guild, author));
  };
  const currentUserId = currentUser?.id;

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState("");
  // What went out last, and where, so a refusal can put it back. The channel is
  // part of it because this view outlives a channel switch: a refusal for a
  // message sent elsewhere must not land in this composer, least of all its
  // images.
  const lastSentRef = useRef<{
    channelId: string;
    text: string;
    attachments: Attachment[];
  } | null>(null);
  const attachments = useAttachmentDrafts(channelId);
  const restoreAttachments = attachments.restore;
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const canSend =
    (!!draft.trim() || attachments.readyIds.length > 0) && !attachments.uploading;

  // Sending clears the composer before the server has answered, so a refusal has
  // to put the words back or they are simply gone.
  useEffect(() => {
    const onNotification = (event: EventPayload) => {
      if (event.metadata?.action !== EventAction.RATE_LIMITED) return;
      const last = lastSentRef.current;
      // A refusal for a message sent from another channel is not about this
      // composer, and an error here would point at the wrong conversation.
      if (!last || last.channelId !== channelId) return;
      setSendError(event.text);
      lastSentRef.current = null;
      setDraft((current) => current || last.text);
      restoreAttachments(last.attachments);
      requestAnimationFrame(resizeInput);
    };
    eventBus.on(EventType.NOTIFICATION, onNotification);
    return () => eventBus.off(EventType.NOTIFICATION, onNotification);
  }, [channelId, restoreAttachments]);

  const sendMessage = () => {
    const text = draft.trim();
    if (!canSend) return;
    if (!ws) {
      setSendError("Not connected. Reconnecting, your message was not sent.");
      return;
    }
    ws.send(
      JSON.stringify({
        event_type: EventType.MESSAGE,
        // The gateway only accepts messages to a channel and rebuilds the frame
        // from `target_id`; `receiver_id` is the deprecated name it still takes.
        target_type: TargetType.CHANNEL,
        target_id: channelId,
        text,
        // Only a request: the gateway links each id that is ours and unsent,
        // and tells every recipient (us included) what it actually attached.
        ...(attachments.readyIds.length > 0 && {
          metadata: { attachment_ids: attachments.readyIds },
        }),
      })
    );
    lastSentRef.current = { channelId, text, attachments: attachments.ready };
    setDraft("");
    setSendError("");
    attachments.clear();
    requestAnimationFrame(resizeInput);
  };

  // At the caret, not the end: someone fixing a sentence midway wants the emoji
  // where they were typing.
  const insertEmoji = (emoji: string) => {
    const result = insertAtCaret(inputRef.current, draft, emoji);
    if (!result) return;
    setDraft(result.next);
    requestAnimationFrame(() => {
      result.place();
      resizeInput();
    });
  };

  // A pasted screenshot is the most common way an image enters a chat, so the
  // textarea accepts one directly. Text pastes are left to the browser.
  const handlePaste = (e: React.ClipboardEvent) => {
    const images = Array.from(e.clipboardData.files).filter((file) =>
      file.type.startsWith("image/")
    );
    if (images.length === 0) return;
    e.preventDefault();
    attachments.add(images);
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
                canDelete={
                  row.message.sender_id === currentUserId ||
                  canModerate(row.message.sender_id)
                }
                selfName={currentUser?.username}
              />
            )
          )
        )}
      </div>

      {aboveComposer}

      <div className="shrink-0 px-3 pb-4 pt-2 sm:px-6">
        {sendError && <p className="mb-2 text-xs text-amber-300">{sendError}</p>}
        {attachments.notice && (
          <p className="mb-2 text-xs text-amber-300">{attachments.notice}</p>
        )}
        {/* `relative`: the emoji popover anchors to this box, not its button */}
        <div className="relative rounded-2xl border border-white/[0.08] bg-ink-850/80 p-2 transition-colors focus-within:border-rain-400/40 focus-within:ring-2 focus-within:ring-rain-400/20">
          {attachments.drafts.length > 0 && (
            <ul className="flex flex-wrap gap-2 px-1 pb-2 pt-1">
              {attachments.drafts.map((item) => (
                <li key={item.localId} className="relative">
                  <img
                    src={item.previewUrl}
                    alt=""
                    className={`h-16 w-16 rounded-xl border object-cover ${
                      item.error ? "border-red-400/60 opacity-50" : "border-white/10"
                    }`}
                  />
                  {!item.attachment && !item.error && (
                    // Upload progress as a bar along the bottom of the thumbnail
                    <span className="absolute inset-x-1 bottom-1 h-1 overflow-hidden rounded-full bg-ink-950/70">
                      <span
                        className="block h-full bg-rain-400 transition-[width]"
                        style={{ width: `${Math.round(item.progress * 100)}%` }}
                      />
                    </span>
                  )}
                  {item.error && (
                    <span
                      title={item.error}
                      className="absolute inset-0 flex items-center justify-center rounded-xl text-center text-[10px] font-medium leading-tight text-red-200"
                    >
                      Failed
                    </span>
                  )}
                  <button
                    onClick={() => attachments.remove(item.localId)}
                    aria-label="Remove image"
                    className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-white/10 bg-ink-800 text-ink-200 hover:bg-red-500 hover:text-white"
                  >
                    <FiX size={11} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex items-end gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={attachments.drafts.length >= MAX_ATTACHMENTS_PER_MESSAGE}
              aria-label="Attach images"
              title="Attach images"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-ink-300 transition-colors hover:bg-white/5 hover:text-white disabled:opacity-40"
            >
              <FiImage size={17} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_IMAGE_TYPES}
              multiple
              className="hidden"
              onChange={(e) => {
                attachments.add(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
            />
            <EmojiPicker onPick={insertEmoji} />
            <textarea
              ref={inputRef}
              rows={1}
              maxLength={MAX_DRAFT_LENGTH}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                resizeInput();
              }}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={`Message ${title}`}
              className="max-h-40 min-w-0 flex-1 resize-none bg-transparent px-1 py-2 text-[15px] text-white placeholder-ink-500 focus:outline-none"
            />
            <button
              onClick={sendMessage}
              disabled={!canSend}
              aria-label="Send message"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rain-400 to-iris-400 text-ink-950 transition-all hover:brightness-110 disabled:from-ink-700 disabled:to-ink-700 disabled:text-ink-500"
            >
              <FiSend size={15} />
            </button>
          </div>
        </div>
        <p className="mt-1.5 hidden px-1 text-[11px] text-ink-500 sm:block">
          <kbd className="font-sans">Enter</kbd> to send ·{" "}
          <kbd className="font-sans">Shift + Enter</kbd> for a new line
        </p>
      </div>
    </div>
  );
}
