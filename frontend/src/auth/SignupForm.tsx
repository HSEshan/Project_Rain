import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { postSignup } from "./apiClient";
import type { AxiosResponse } from "axios";

export default function SignupForm({
  setIsLogin,
}: {
  setIsLogin: (isLogin: boolean) => void;
}) {
  const navigate = useNavigate();

  const usernameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const [errors, setErrors] = useState<{ [key: string]: string }>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    await postSignup(
      usernameRef.current?.value || "",
      emailRef.current?.value || "",
      passwordRef.current?.value || ""
    )
      .then((res: AxiosResponse) => {
        if (res.status === 201) {
          navigate("/login?signup=true");
          setIsLogin(true);
        }
      })
      .catch((err: Error) => {
        setErrors({ "Signup failed": err.message });
      });
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

      {errors["Signup failed"] && (
        <p className="text-red-400 text-sm">{errors["Signup failed"]}</p>
      )}

      <button
        type="submit"
        className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
      >
        Sign Up
      </button>
    </form>
  );
}
