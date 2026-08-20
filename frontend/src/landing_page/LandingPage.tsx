import Architecture from "./Architecture";
import Features from "./Features";
import Hero from "./Hero";
import LandingFooter from "./LandingFooter";
import LandingNav from "./LandingNav";
import VoiceShowcase from "./VoiceShowcase";

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-ink-950">
      <LandingNav />
      <main>
        <Hero />
        <Features />
        <Architecture />
        <VoiceShowcase />
        <LandingFooter />
      </main>
    </div>
  );
}
