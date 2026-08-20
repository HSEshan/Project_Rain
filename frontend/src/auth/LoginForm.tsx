import { useState, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FiEye, FiEyeOff, FiLock, FiMail } from "react-icons/fi";
import type { AxiosResponse } from "axios";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../shared/Button";
import { Input } from "../shared/Input";
import { errorText } from "../shared/errors";
import { postLogin } from "./apiClient";

export default function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [loggingIn, setLoggingIn] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [searchParams] = useSearchParams();
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoggingIn(true);
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
      .catch((err: unknown) => {
        setError(errorText(err, "Could not sign you in."));
      })
      .finally(() => setLoggingIn(false));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-white">Welcome back</h2>
        <p className="mt-1.5 text-sm text-ink-400">
          Sign in to pick up where you left off.
        </p>
      </div>

      {searchParams.get("signup") && (
        <p className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3.5 py-2.5 text-sm text-emerald-300">
          Account created. Sign in to continue.
        </p>
      )}

      <Input
        label="Email or username"
        name="username"
        type="text"
        autoComplete="username"
        placeholder="you@example.com"
        icon={<FiMail size={15} />}
        ref={usernameRef}
      />

      <div className="relative">
        <Input
          label="Password"
          name="password"
          type={showPassword ? "text" : "password"}
          autoComplete="current-password"
          placeholder="••••••••"
          icon={<FiLock size={15} />}
          ref={passwordRef}
        />
        <button
          type="button"
          onClick={() => setShowPassword((v) => !v)}
          className="absolute right-3 top-[30px] rounded-md p-1.5 text-ink-400 transition-colors hover:text-white"
          aria-label={showPassword ? "Hide password" : "Show password"}
        >
          {showPassword ? <FiEyeOff size={15} /> : <FiEye size={15} />}
        </button>
      </div>

      {error && (
        <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
          {error}
        </p>
      )}

      <Button type="submit" variant="primary" size="lg" full loading={loggingIn}>
        {loggingIn ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
