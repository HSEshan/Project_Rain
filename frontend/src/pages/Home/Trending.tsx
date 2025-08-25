import { useEffect, useRef, useState } from "react";
import { useWebSocket } from "../../providers/WebsocketProvider";
import { useAuth } from "../../auth/AuthContext";
import { eventBus } from "../../shared/events/EventBus";

export default function Trending() {
  const [connected, setConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    sender_id: "",
    receiver_id: "",
    text: "",
  });
  const [messages, setMessages] = useState<any[]>([]);
  const ws = useWebSocket();
  const { getToken } = useAuth();
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setError("No auth token found.");
      return;
    }
  }, [getToken]);

  useEffect(() => {
    eventBus.subscribe("notification", (event: any) => {
      setMessages((prev) => [event, ...prev]);
    });
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setError("WebSocket not connected.");
      return;
    }

    const payload = {
      event_type: "notification",
      sender_id: formData.sender_id,
      receiver_id: formData.receiver_id,
      text: formData.text,
      metadata: null,
    };

    ws.send(JSON.stringify(payload));
    setFormData((prev) => ({ ...prev, text: "" }));
  };

  return (
    <div className="bg-zinc-800 text-white p-6 rounded-lg max-w-2xl mx-auto mt-8 shadow-lg">
      <h3 className="text-xl font-semibold flex items-center gap-2 mb-4">
        💬 WebSocket Messenger
        <span
          className={`w-3 h-3 rounded-full ${
            connected ? "bg-green-500" : "bg-red-500"
          }`}
          title={connected ? "Connected" : "Disconnected"}
        />
      </h3>

      {error && <p className="text-red-400 mb-4">{error}</p>}

      <form
        onSubmit={handleSend}
        className="flex flex-wrap gap-2 items-center mb-6"
      >
        <input
          type="text"
          name="sender_id"
          placeholder="Sender ID"
          value={formData.sender_id}
          onChange={handleChange}
          required
          className="px-3 py-2 rounded bg-zinc-700 border border-zinc-600 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <input
          type="text"
          name="receiver_id"
          placeholder="Receiver ID"
          value={formData.receiver_id}
          onChange={handleChange}
          required
          className="px-3 py-2 rounded bg-zinc-700 border border-zinc-600 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <input
          type="text"
          name="text"
          placeholder="Notification"
          value={formData.text}
          onChange={handleChange}
          required
          className="px-3 py-2 w-60 rounded bg-zinc-700 border border-zinc-600 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="submit"
          className="px-4 py-2 rounded bg-indigo-600 hover:bg-indigo-700 text-white font-semibold transition"
        >
          Send
        </button>
      </form>

      <div>
        <h4 className="text-lg font-semibold mb-2">📥 Received Messages</h4>
        <div className="max-h-80 overflow-y-auto bg-zinc-700 p-3 rounded space-y-2">
          {messages.map((msg, index) => (
            <pre
              key={index}
              className="bg-zinc-800 p-2 rounded text-sm text-zinc-100"
            >
              {JSON.stringify(msg, null, 2)}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
}
