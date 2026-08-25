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
import { emitResync } from "../shared/resync";
import type { EventPayload } from "./eventType";

interface WebSocketContextType {
  getWs: () => WebSocket | null;
  isConnected: boolean;
  isConnecting: boolean;
  reconnect: () => void;
  disconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

const INITIAL_RETRY_DELAY = 1000; // 1 second
const MAX_RETRY_DELAY = 30000; // 30 seconds
/**
 * Beyond this the delay is capped, so retries continue for as long as the tab
 * is open. There is deliberately no attempt limit: this used to give up after
 * five tries, about 31 seconds of backoff, leaving a `console.error` and a
 * permanently dead socket. A one minute outage disconnected a client until they
 * reloaded the page, which is not something a user would ever think to do.
 */
const MAX_BACKOFF_EXPONENT = 5;

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const retryTimeoutRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  // Distinguishes a reconnect from the first connect: AppInitializer has
  // already fetched everything for the latter, so resyncing then is wasted work
  const hasConnectedRef = useRef(false);
  const { getToken } = useAuth();

  const connect = useCallback(() => {
    if (isConnecting || wsRef.current) return;

    const token = getToken();
    if (!token) {
      console.error("No token found");
      return;
    }

    setIsConnecting(true);
    console.log("Creating new WebSocket connection...");

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.host;
    const newWs = new WebSocket(`${protocol}://${host}/ws?token=${token}`);

    newWs.onopen = () => {
      console.log("✅ WebSocket connected");
      setIsConnected(true);
      setIsConnecting(false);
      retryCountRef.current = 0; // Reset retry count on successful connection

      // Anything published while the socket was down was delivered to nobody
      // and is not retried anywhere, so the client has to assume it is behind.
      if (hasConnectedRef.current) {
        console.log("🔁 Reconnected, resyncing stores");
        emitResync();
      }
      hasConnectedRef.current = true;
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

      // Keep trying for as long as the tab is open. The delay is capped, so
      // this settles into a poll rather than growing without bound.
      if (shouldReconnectRef.current) {
        scheduleReconnect();
      }
    };

    wsRef.current = newWs;
  }, [isConnecting]);

  const scheduleReconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
    }

    retryCountRef.current++;
    const exponent = Math.min(retryCountRef.current - 1, MAX_BACKOFF_EXPONENT);
    const base = Math.min(
      INITIAL_RETRY_DELAY * Math.pow(2, exponent),
      MAX_RETRY_DELAY
    );
    // Full jitter. Without it every client of a restarted gateway waits the
    // same 1s, 2s, 4s and reconnects in lockstep, so the instance coming back
    // takes the entire herd at once — and each of them then fires a resync.
    // Spreading the retries over the window is what stops a restart turning
    // into a self-inflicted load spike.
    const delay = Math.round(base / 2 + Math.random() * (base / 2));

    console.log(
      `🔄 Scheduling reconnection attempt ${retryCountRef.current} in ${delay}ms`
    );

    retryTimeoutRef.current = setTimeout(() => {
      if (shouldReconnectRef.current) {
        connect();
      }
    }, delay);
  }, [connect]);

  const disconnect = useCallback(() => {
    console.log("🔌 Closing WebSocket connection");
    shouldReconnectRef.current = false;
    retryCountRef.current = 0;

    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
  }, []);

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
        // Detach first: a socket closed mid-handshake (React's dev-mode double
        // mount does exactly this) would otherwise report an error and queue a
        // reconnect for a provider that no longer exists.
        const socket = wsRef.current;
        wsRef.current = null;
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
      }
    };
  }, []); // Only run on mount

  const contextValue: WebSocketContextType = {
    getWs: () => wsRef.current,
    isConnected,
    isConnecting,
    reconnect,
    disconnect,
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
