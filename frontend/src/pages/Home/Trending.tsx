import { useEffect, useState } from "react";
import apiClient from "../../utils/apiClient";

export default function Trending() {
  const [data, setData] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get("trending")
      .then((res) => setData(res.data.message))
      .catch((err) => setError("Error fetching data"))
      .finally(() => setLoading(false));
  });

  return (
    <div style={{ background: "#444", padding: "1rem", borderRadius: "8px" }}>
      <h3>🔥 Trending</h3>
      {loading && <p>Loading...</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {data && <p>{data}</p>}
    </div>
  );
}
