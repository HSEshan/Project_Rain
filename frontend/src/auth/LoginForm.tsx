import { useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../utils/apiClient";
import { useAuth } from "../auth/AuthContext";

export default function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({ username: "", password: "" });
  const [error, setError] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiClient.post("/auth/login", formData);
      login(res.data.access_token); // Save token in cookie
      navigate("/home");
    } catch (err: any) {
      setError("Invalid credentials: " + err.response.data.detail);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-2xl font-semibold text-center mb-4">Log in</h2>
      <input
        type="text"
        name="username"
        placeholder="Username or Email"
        value={formData.username}
        onChange={handleChange}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      <input
        type="password"
        name="password"
        placeholder="Password"
        value={formData.password}
        onChange={handleChange}
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
