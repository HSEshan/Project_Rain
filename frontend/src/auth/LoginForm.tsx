import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../utils/apiClientBase";
import { useAuth } from "../auth/AuthContext";

export default function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiClient.post(
        "/auth/login",
        new URLSearchParams({
          username: usernameRef.current?.value || "",
          password: passwordRef.current?.value || "",
        }),
        {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        }
      );
      login(res.data.access_token); // Save token in cookie
      navigate("/home");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError("Invalid credentials: " + err.message);
      } else {
        setError("An unknown error occurred");
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-2xl font-semibold text-center mb-4">Log in</h2>
      <input
        type="text"
        name="username"
        placeholder="Username or Email"
        ref={usernameRef}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      <input
        type="password"
        name="password"
        placeholder="Password"
        ref={passwordRef}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      {error && <p className="text-red-400 text-sm">{error}</p>}
      <button
        type="submit"
        className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
      >
        Log in
      </button>
    </form>
  );
}
