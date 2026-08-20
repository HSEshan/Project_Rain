import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FiMenu, FiX } from "react-icons/fi";
import { Button } from "../shared/Button";
import Logo from "./Logo";

const LINKS = [
  { href: "#features", label: "Features" },
  { href: "#architecture", label: "Architecture" },
  { href: "#voice", label: "Voice" },
];

export default function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  // The bar is transparent over the hero and solidifies once you leave it,
  // so the aurora is never fighting a panel for the same pixels.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
        scrolled
          ? "border-b border-white/[0.06] bg-ink-950/80 backdrop-blur-xl"
          : "border-b border-transparent"
      }`}
    >
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link to="/" aria-label="Rain home">
          <Logo />
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-lg px-3.5 py-2 text-sm text-ink-300 transition-colors hover:text-white"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <Button to="/login" variant="ghost" size="sm">
            Sign in
          </Button>
          <Button to="/login" variant="primary" size="sm">
            Get started
          </Button>
        </div>

        <button
          className="rounded-lg p-2 text-ink-200 transition-colors hover:bg-white/5 md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          {open ? <FiX size={20} /> : <FiMenu size={20} />}
        </button>
      </nav>

      {open && (
        <div className="border-t border-white/[0.06] bg-ink-950/95 px-5 pb-5 pt-2 backdrop-blur-xl md:hidden">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="block rounded-lg px-2 py-3 text-sm text-ink-200 hover:bg-white/5"
            >
              {link.label}
            </a>
          ))}
          <Button to="/login" variant="primary" full className="mt-3">
            Get started
          </Button>
        </div>
      )}
    </header>
  );
}
