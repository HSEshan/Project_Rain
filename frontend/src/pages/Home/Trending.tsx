import { useEffect, useRef, useState } from "react";

export default function Trending() {
  const [data, setData] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Utility: get token from cookie
  function getTokenFromCookie(): string | null {
    const match = document.cookie.match(/(?:^|;\s*)token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
  }

  useEffect(() => {
    // First, load trending data
    fetch("http://localhost:8000/trending", {
      credentials: "include",
    })
      .then((res) => res.json())
      .then((data) => setData(data.message))
      .catch(() => setError("Error fetching data"))
      .finally(() => setLoading(false));

    // Then, connect to WebSocket
    const token = getTokenFromCookie();
    if (!token) {
      setError("No auth token found.");
      return;
    }

    const ws = new WebSocket(`ws://localhost:8001/ws?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("✅ WebSocket connected");
      setConnected(true);
    };

    ws.onmessage = (event) => {
      console.log("📨 Received:", event.data);
      // Optionally parse and use incoming event
    };

    ws.onclose = () => {
      console.log("❌ WebSocket disconnected");
      setConnected(false);
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
      setError("WebSocket error occurred.");
    };

    return () => {
      ws.close();
    };
  }, []);

  return (
    <div style={{ background: "#444", padding: "1rem", borderRadius: "8px" }}>
      <h3>
        🔥 Trending{" "}
        <span
          style={{
            marginLeft: "0.5rem",
            display: "inline-block",
            width: "10px",
            height: "10px",
            borderRadius: "50%",
            backgroundColor: connected ? "limegreen" : "crimson",
          }}
          title={connected ? "Connected" : "Disconnected"}
        ></span>
      </h3>
      {loading && <p>Loading...</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {data && <p>{data}</p>}
    </div>
  );
}
