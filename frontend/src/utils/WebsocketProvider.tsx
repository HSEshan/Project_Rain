/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  useCallback,
} from "react";
import { useAuth } from "../auth/AuthContext";
import { eventBus } from "./EventBus";
import type { EventPayload } from "./eventType";

interface WebSocketContextType {
  getWs: () => WebSocket | null;
  isConnected: boolean;
  isConnecting: boolean;
  reconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

const MAX_RETRIES = 5;
const INITIAL_RETRY_DELAY = 1000; // 1 second
const MAX_RETRY_DELAY = 30000; // 30 seconds

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const retryTimeoutRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const { getToken } = useAuth();

  const connect = useCallback(() => {
    if (isConnecting || wsRef.current) return;

    setIsConnecting(true);
    console.log("Creating new WebSocket connection...");
    const token = getToken();
    if (!token) {
      console.error("No token found");
      return;
    }

    const wsHost = import.meta.env.VITE_HOST;

    const newWs = new WebSocket(`ws://${wsHost}:8000/ws?token=${token}`);

    newWs.onopen = () => {
      console.log("✅ WebSocket connected");
      setIsConnected(true);
      setIsConnecting(false);
      retryCountRef.current = 0; // Reset retry count on successful connection
    };

    newWs.onmessage = (msg) => {
      try {
        const data: EventPayload = JSON.parse(msg.data);
        eventBus.emit(data);
        console.log("🔔 Message received:", data);
      } catch (err) {
        console.error("❌ Invalid WS event", err);
      }
    };

    newWs.onerror = (error) => {
      console.error("⚠️ WebSocket error:", error);
      setIsConnecting(false);
    };

    newWs.onclose = (event) => {
      console.log("❌ WebSocket closed:", event.code, event.reason);
      setIsConnected(false);
      setIsConnecting(false);
      wsRef.current = null;

      // Only attempt to reconnect if we should and haven't exceeded max retries
      if (shouldReconnectRef.current && retryCountRef.current < MAX_RETRIES) {
        scheduleReconnect();
      } else if (retryCountRef.current >= MAX_RETRIES) {
        console.error(
          "🚫 Max retry attempts reached. Manual reconnection required."
        );
      }
    };

    wsRef.current = newWs;
  }, [isConnecting]);

  const scheduleReconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
    }

    retryCountRef.current++;
    const delay = Math.min(
      INITIAL_RETRY_DELAY * Math.pow(2, retryCountRef.current - 1),
      MAX_RETRY_DELAY
    );

    console.log(
      `🔄 Scheduling reconnection attempt ${retryCountRef.current}/${MAX_RETRIES} in ${delay}ms`
    );

    retryTimeoutRef.current = setTimeout(() => {
      if (shouldReconnectRef.current) {
        connect();
      }
    }, delay);
  }, [connect]);

  const reconnect = useCallback(() => {
    console.log("🔄 Manual reconnection requested");
    retryCountRef.current = 0;
    shouldReconnectRef.current = true;

    if (wsRef.current) {
      wsRef.current.close();
    } else {
      connect();
    }
  }, [connect]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();

    return () => {
      console.log("Cleaning up WebSocket connection");
      shouldReconnectRef.current = false;

      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }

      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []); // Only run on mount

  const contextValue: WebSocketContextType = {
    getWs: () => wsRef.current,
    isConnected,
    isConnecting,
    reconnect,
  };

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
};
