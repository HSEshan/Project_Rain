import { createContext, useContext, useEffect, useState } from "react";
import { eventBus } from "../shared/events/EventBus";
import { useAuth } from "../auth/AuthContext";

const WebSocketContext = createContext<WebSocket | null>(null);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { isAuthenticated, getToken } = useAuth();
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      if (ws) {
        console.log("User not authenticated, closing WebSocket");
        ws.close();
        setWs(null);
      }
      return;
    }

    const token = getToken();
    if (!token) {
      console.log("No token available");
      return;
    }

    console.log("Creating new WebSocket connection...");
    const wsUrl = new URL("ws://localhost:8001/ws");
    wsUrl.searchParams.set("token", token);
    const newWs = new WebSocket(wsUrl.toString());

    // Set up event handlers BEFORE setting state
    newWs.onopen = () => {
      console.log("WebSocket connected successfully");
    };

    newWs.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        eventBus.emit(data);
      } catch (err) {
        console.error("Invalid WS event", err);
      }
    };

    newWs.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    newWs.onclose = (event) => {
      console.log("WebSocket closed:", event.code, event.reason);
      setWs(null);
    };

    // Now set the state after handlers are configured
    setWs(newWs);
    console.log("WebSocket created and configured");

    return () => {
      console.log("Cleaning up WebSocket connection");
      if (newWs && newWs.readyState === WebSocket.OPEN) {
        newWs.close();
      }
    };
  }, [isAuthenticated, getToken]);

  return (
    <WebSocketContext.Provider value={ws}>{children}</WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const ws = useContext(WebSocketContext);
  if (!ws) {
    throw new Error("WebSocket not found");
  }
  return ws;
};
