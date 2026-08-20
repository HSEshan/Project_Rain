import { useState } from "react";
import { Link } from "react-router-dom";
import { FiArrowLeft, FiCheck } from "react-icons/fi";
import Logo from "../landing_page/Logo";
import LoginForm from "./LoginForm";
import SignupForm from "./SignupForm";

const SELLING_POINTS = [
  "Direct messages and friends, live without a refresh",
  "Guilds with text and voice channels",
  "Group voice on a self-hosted SFU",
];

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);

  return (
    <div className="flex min-h-screen bg-ink-950">
      {/* Brand rail. Hidden below lg — on a phone the form is the whole job. */}
      <aside className="relative hidden w-[46%] flex-col justify-between overflow-hidden border-r border-white/[0.06] p-12 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-40 top-0 h-[560px] w-[560px] rounded-full bg-rain-500/15 blur-[130px]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 -right-20 h-[420px] w-[420px] rounded-full bg-iris-500/10 blur-[120px]"
        />

        <Link to="/" className="relative w-fit">
          <Logo size={30} />
        </Link>

        <div className="relative max-w-md">
          <h1 className="text-balance text-4xl font-bold leading-tight text-white">
            Real-time chat and voice,{" "}
            <span className="gradient-text">built to scale.</span>
          </h1>
          <ul className="mt-8 space-y-3.5">
            {SELLING_POINTS.map((point) => (
              <li key={point} className="flex items-start gap-3 text-ink-300">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-rain-400/15 text-rain-300">
                  <FiCheck size={12} />
                </span>
                <span className="text-[15px] text-pretty">{point}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative font-mono text-xs text-ink-500">
          9 services · WebRTC/UDP media · self-hosted
        </p>
      </aside>

      <main className="flex flex-1 flex-col px-5 py-8 sm:px-8">
        <div className="flex items-center justify-between lg:justify-end">
          <Link to="/" className="lg:hidden">
            <Logo size={26} />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-ink-400 transition-colors hover:text-white"
          >
            <FiArrowLeft size={15} /> Back
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm py-10">
            <div key={isLogin ? "login" : "signup"} className="animate-fade-up">
              {isLogin ? (
                <LoginForm />
              ) : (
                <SignupForm onDone={() => setIsLogin(true)} />
              )}
            </div>

            <p className="mt-8 text-center text-sm text-ink-400">
              {isLogin ? "New to Rain?" : "Already have an account?"}{" "}
              <button
                className="font-medium text-rain-300 transition-colors hover:text-rain-200"
                onClick={() => setIsLogin((prev) => !prev)}
              >
                {isLogin ? "Create an account" : "Sign in"}
              </button>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
