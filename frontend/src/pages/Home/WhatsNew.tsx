import { useEffect, useState } from "react";
import apiClient from "../../utils/apiClientBase";

export default function WhatsNew() {
  const [data, setData] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get("/whatsnew")
      .then((res) => setData(res.data.message))
      .catch((err) => setError("Error fetching data"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ background: "#444", padding: "1rem", borderRadius: "8px" }}>
      <h3>📰 What's New</h3>
      {loading && <p>Loading...</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {data && <p>{data}</p>}
    </div>
  );
}
