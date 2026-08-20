import { FiArrowRight } from "react-icons/fi";
import { Button } from "../shared/Button";
import Logo from "./Logo";
import Reveal from "./Reveal";

export default function LandingFooter() {
  return (
    <>
      <section className="relative overflow-hidden px-5 py-24 sm:px-8">
        {/* Soft accent wash behind the closing call to action */}
        <div
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[820px] max-w-[95vw] -translate-x-1/2 -translate-y-1/2 rounded-full bg-rain-500/10 blur-[120px]"
        />
        <Reveal className="relative mx-auto max-w-2xl text-center">
          <h2 className="text-balance text-3xl font-bold text-white sm:text-5xl">
            Make a room. <span className="gradient-text">Say something.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-lg text-pretty text-ink-300">
            Free, self-hosted, and running right now. Create an account and
            bring someone with you, since voice is better with company.
          </p>
          <div className="mt-9 flex justify-center">
            <Button to="/login" variant="primary" size="lg" icon={<FiArrowRight />}>
              Create your account
            </Button>
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-white/[0.06] px-5 py-10 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-5 sm:flex-row">
          <Logo size={22} />
          <p className="text-center text-xs text-ink-400">
            A portfolio project: chat, guilds and a self-hosted SFU.
          </p>
          <div className="flex gap-5 text-xs text-ink-400">
            <a href="#features" className="transition-colors hover:text-white">
              Features
            </a>
            <a href="#architecture" className="transition-colors hover:text-white">
              Architecture
            </a>
            <a href="#voice" className="transition-colors hover:text-white">
              Voice
            </a>
          </div>
        </div>
      </footer>
    </>
  );
}
