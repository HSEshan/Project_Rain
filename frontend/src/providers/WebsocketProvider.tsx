import { createContext, useEffect } from "react";
import { eventBus } from "../shared/events/EventBus";

const WebSocketContext = createContext<WebSocket | null>(null);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8001");

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        eventBus.emit(data);
      } catch (err) {
        console.error("Invalid WS event", err);
      }
    };

    return () => ws.close();
  }, []);

  return (
    <WebSocketContext.Provider value={null}>
      {children}
    </WebSocketContext.Provider>
  );
};
