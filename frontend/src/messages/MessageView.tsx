import { type Message } from "./types";
import { useWebSocket } from "../utils/WebsocketProvider";
import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { useMessageStore } from "./messageStore";
import { EventType } from "../utils/eventType";
import { useAuth } from "../auth/AuthContext";
import { useUserStore } from "../shared/userStore";

function MessageItem({ message }: { message: Message }) {
  const { getUser } = useAuth();
  const { getUser: getUserFromStore } = useUserStore();
  const user = getUser();
  return (
    <div
      className={`bg-gray-600 text-white p-3 rounded-lg shadow-sm border border-none mb-3 w-2/3 ${
        message.sender_id === user?.id ? "self-end" : "self-start"
      }`}
    >
      {" "}
      <div className="break-words whitespace-pre-wrap text-sm leading-relaxed">
        {message.sender_id === user?.id
          ? "You"
          : getUserFromStore(message.sender_id)?.username}
      </div>
      <div className="break-words whitespace-pre-wrap text-sm leading-relaxed">
        {message.content}
      </div>
      <div className="text-xs text-gray-300 mt-2 text-right">
        {new Date(message.created_at).toLocaleTimeString()}
      </div>
    </div>
  );
}

export function MessageView() {
  const { getMessages, removeUnRead, channels } = useMessageStore();
  const { dmId } = useParams<{ dmId: string }>();
  const messages = getMessages(dmId);
  const { getWs } = useWebSocket();
  const ws = getWs();
  const messageRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    removeUnRead(dmId ?? "");
  }, [dmId]);

  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const sendMessage = () => {
    if (!ws) {
      alert("No websocket connection");
      return;
    }

    if (messageRef.current?.value?.trim()) {
      ws.send(
        JSON.stringify({
          event_type: EventType.MESSAGE,
          receiver_id: dmId,
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
    <div className="w-3/5 bg-gray-800 p-4 overflow-y-auto flex flex-col h-full">
      <h1 className="text-lg text-white font-bold mb-4 flex-shrink-0">
        {channels
          .find((channel) => channel.channel_id === dmId)
          ?.participants.map((participant) => participant.username)
          .join(", ")}
      </h1>

      {messages === undefined ? (
        <div className="text-gray-500 text-center py-8">Loading...</div>
      ) : (
        <>
          {/* Messages container auto scroll to bottom */}
          <div
            className="flex-1 overflow-y-auto mb-5 flex flex-col space-y-2"
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
              className="bg-black hover:bg-gray-800 text-white px-6 py-3 rounded-lg shadow-sm transition-colors duration-200 focus:outline-none"
              onClick={sendMessage}
            >
              Send
            </button>
          </div>
        </>
      )}
    </div>
  );
}
