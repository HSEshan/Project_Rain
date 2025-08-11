import { eventBus } from "../shared/events/EventBus";
import { Cookies } from "react-cookie";

const cookies = new Cookies();
const WS_BASE_URL = "ws://localhost:8001/ws"; // adjust to your endpoint

let socket: WebSocket | null = null;
let listeners: ((data: any) => void)[] = [];

const connect = () => {
  const token = cookies.get("token");
  if (!token) {
    console.warn("No token found, skipping WebSocket connection.");
    return;
  }

  const url = `${WS_BASE_URL}?token=${token}`;
  socket = new WebSocket(url);

  socket.onopen = () => {
    console.log("[WS] Connected");
  };

  socket.onclose = (event) => {
    console.warn("[WS] Disconnected", event.reason);
    // Optional: Retry connection with exponential backoff
  };

  socket.onerror = (error) => {
    console.error("[WS] Error", error);
  };

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    eventBus.emit(message);
  };
};

const send = (data: any) => {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(data));
  } else {
    console.warn("Socket not open. Cannot send.");
  }
};

const onMessage = (cb: (data: any) => void) => {
  listeners.push(cb);
  return () => {
    listeners = listeners.filter((listener) => listener !== cb);
  };
};

const close = () => {
  socket?.close();
};

const wsClient = {
  connect,
  send,
  onMessage,
  close,
};

export default wsClient;
