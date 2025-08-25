import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../utils/apiClientBase";
import { useAuth } from "../auth/AuthContext";

export default function SignupForm() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const usernameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [generalError, setGeneralError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setGeneralError("");

    try {
      const formData = new URLSearchParams();
      formData.append("username", usernameRef.current?.value || "");
      formData.append("email", emailRef.current?.value || "");
      formData.append("password", passwordRef.current?.value || "");
      await apiClient
        .post("/auth/register", formData, {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        })
        .then((res) => {
          login(res.data.access_token);
          navigate("/home");
        })
        .catch((err) => {
          setErrors({ username: "Invalid credentials: " + err.response.data });
        });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrors({ username: "Invalid credentials: " + err.message });
      } else {
        setErrors({ username: "An unknown error occurred" });
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-2xl font-semibold text-center mb-4">Sign Up</h2>

      <input
        type="text"
        name="username"
        placeholder="Username"
        ref={usernameRef}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      {errors.username && (
        <p className="text-red-400 text-sm">{errors.username}</p>
      )}

      <input
        type="email"
        name="email"
        placeholder="Email"
        ref={emailRef}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      {errors.email && <p className="text-red-400 text-sm">{errors.email}</p>}

      <input
        type="password"
        name="password"
        placeholder="Password"
        ref={passwordRef}
        className="w-full p-2 bg-gray-700 text-white rounded"
      />
      {errors.password && (
        <p className="text-red-400 text-sm">{errors.password}</p>
      )}

      {generalError && <p className="text-red-400 text-sm">{generalError}</p>}

      <button
        type="submit"
        className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
      >
        Sign Up
      </button>
    </form>
  );
}
