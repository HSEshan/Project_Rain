import { useState, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { postLogin } from "./apiClient";
import type { AxiosResponse } from "axios";

export default function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [searchParams] = useSearchParams();
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await postLogin(
      usernameRef.current?.value || "",
      passwordRef.current?.value || ""
    )
      .then((res: AxiosResponse) => {
        if (res.status === 200) {
          login(res.data.access_token);
          navigate("/home");
        }
      })
      .catch((err: Error) => {
        setError(err.message);
      });
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
      {error && <p className="text-red-400 text-sm text-center">{error}</p>}
      {searchParams.get("signup") && (
        <p className="text-green-400 text-sm text-center">Signup successful</p>
      )}
      <button
        type="submit"
        className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
      >
        Log in
      </button>
    </form>
  );
}
