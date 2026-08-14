import { type Message } from "../shared/types";
import { useWebSocket } from "../utils/WebsocketProvider";
import { useEffect, useRef, useState } from "react";
import { useMessageStore } from "../shared/messageStore";
import { EventType } from "../utils/eventType";
import { useAuth } from "../auth/AuthContext";
import { useUserStore } from "../shared/userStore";

function MessageItem({ message }: { message: Message }) {
  const { getCurrentUser } = useAuth();
  const { getUser: getUserFromStore } = useUserStore();
  const currentUser = getCurrentUser();

  const getSenderName = () => {
    if (message.sender_id === currentUser?.id) return "You";
    const sender = getUserFromStore(message.sender_id);
    return sender?.username || "Loading...";
  };

  return (
    <div
      className={`bg-gray-600 text-white p-3 rounded-lg shadow-sm border border-none mb-3 w-2/3 ${
        message.sender_id === currentUser?.id ? "self-end" : "self-start"
      }`}
    >
      <div className="break-words whitespace-pre-wrap text-sm leading-relaxed">
        {getSenderName()}
      </div>
      <div className="break-words whitespace-pre-wrap text-sm leading-relaxed">
        {message.content}
      </div>
      <div className="text-xs text-gray-300 mt-2 text-right">
        {new Date(message.created_at).toLocaleString()}
      </div>
    </div>
  );
}

export interface MessageViewProps {
  channelId: string;
  /** Rendered as the header: DM participants, or "# channel-name" in a guild. */
  title: string;
}

/**
 * Chat surface for one channel. Channel-agnostic on purpose — DMs and guild
 * text channels are the same thing to the message store and the WS protocol.
 */
export function MessageView({ channelId, title }: MessageViewProps) {
  const { getChannelMessages, fetchChannelMessages } = useMessageStore();
  const { fetchUsers } = useUserStore();
  const { getWs } = useWebSocket();

  const messages = getChannelMessages(channelId);
  const ws = getWs();
  const messageRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  const scrollToBottom = (smooth: boolean = false) => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: smooth ? "smooth" : undefined,
      });
    }
  };

  useEffect(() => {
    if (!channelId) return;
    setIsInitialLoad(true);
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

  const sendMessage = () => {
    if (!ws) {
      alert("No websocket connection");
      return;
    }

    if (messageRef.current?.value?.trim()) {
      ws.send(
        JSON.stringify({
          event_type: EventType.MESSAGE,
          receiver_id: channelId,
          text: messageRef.current.value,
        })
      );
      messageRef.current.value = "";
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }

    if (e.key === "Enter" && e.shiftKey) {
      e.preventDefault();
      messageRef.current!.value += "\n";
      messageRef.current!.scrollTop = messageRef.current!.scrollHeight;
    }
  };

  return (
    <div className="flex-1 bg-gray-800 p-4 flex flex-col h-full">
      <h1 className="text-lg text-white font-bold mb-4 flex-shrink-0">
        {title}
      </h1>

      <div
        className="flex-1 overflow-y-auto mb-5 flex flex-col space-y-2 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-gray-800"
        ref={messagesContainerRef}
      >
        {messages.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            No messages yet. Start the conversation!
          </div>
        ) : (
          messages.map((message: Message) => (
            <MessageItem key={message.id} message={message} />
          ))
        )}
      </div>

      <div className="flex gap-2 relative bottom-0 left-0 right-0 p-4 bg-gray-800 border-t">
        <textarea
          className="flex-1 p-3 rounded-lg bg-gray-600 text-white shadow-sm border border-none focus:outline-none focus:ring-2 focus:ring-white focus:border-transparent"
          ref={messageRef}
          rows={1}
          placeholder="Type your message here..."
          onKeyDown={handleKeyPress}
        />
        <button
          className="bg-black text-white px-6 py-3 rounded-lg shadow-sm transition-colors duration-200 focus:outline-none"
          onClick={sendMessage}
        >
          Send
        </button>
      </div>
    </div>
  );
}
