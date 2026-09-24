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
import { refreshSession } from "../auth/refresh";
import { eventBus } from "./EventBus";
import { emitResync } from "../shared/resync";
import { emitSessionExpired } from "../shared/session";
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

/**
 * The gateway's answer to a token it will not accept
 * (`WS_1008_POLICY_VIOLATION`, `ws_gateway/src/auth/service.py`).
 *
 * Retrying it *unchanged* is pointless: the token that was refused is the only
 * token this tab has, so every attempt gets the same answer, and the socket
 * used to settle into a 30 second poll against a server that would reject it
 * forever. Since Phase 15 there is a third possibility between "outage" and
 * "signed out" — the access token simply reached the end of its hour while the
 * socket was open, which the gateway only notices on the next connect. So a
 * 1008 is answered by renewing once and reconnecting with the new token, and
 * only a renewal that is itself refused ends the session.
 */
const WS_POLICY_VIOLATION = 1008;

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
  // Whether this run of disconnections has already spent a forced renewal. A
  // gateway that refuses a freshly minted token is not refusing it for being
  // stale, so trying again would burn a refresh token per reconnect.
  const renewedForOutageRef = useRef(false);
  const { getToken } = useAuth();

  const connect = useCallback((tokenOverride?: string) => {
    if (isConnecting || wsRef.current) return;

    // The override is the token a renewal just returned. Going through
    // `getToken` instead would read React state that has not re-rendered yet,
    // and reconnect with the token the gateway just refused.
    const token = tokenOverride ?? getToken();
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
      // The outage is over, so the next one may renew again.
      renewedForOutageRef.current = false;

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

      // A refused token is not an outage, and no amount of waiting fixes it —
      // but a *renewed* token might be accepted.
      //
      // `force`, because the gateway has just contradicted the only evidence
      // the client had. `tokenNeedsRefresh` reads the token's own `exp`, and a
      // token can be refused while that still looks fine — clock skew between
      // the two services, a rotated `SECRET_KEY`, or env files that drifted
      // apart. Without forcing, the renewal returned the same refused token
      // and the socket reconnected with it forever.
      //
      // Once per outage, because forcing is a real rotation. If the *renewed*
      // token is refused too, renewing is not the answer and this is an outage
      // like any other: fall through to backoff rather than spending a refresh
      // token per attempt.
      if (event.code === WS_POLICY_VIOLATION && !renewedForOutageRef.current) {
        renewedForOutageRef.current = true;
        shouldReconnectRef.current = false;
        void refreshSession({ force: true }).then((renewed) => {
          if (!renewed) {
            emitSessionExpired();
            return;
          }
          shouldReconnectRef.current = true;
          retryCountRef.current = 0;
          connect(renewed);
        });
        return;
      }

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
