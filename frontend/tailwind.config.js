/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Deep blue-black base. Named `ink` so it never reads as Tailwind gray,
        // which is what the old UI used everywhere.
        ink: {
          950: "#04060C",
          900: "#070A12",
          850: "#0B0F1A",
          800: "#101725",
          750: "#151D2E",
          700: "#1C2639",
          600: "#26334B",
          500: "#374764",
          400: "#56688A",
          300: "#8496B6",
          200: "#B6C2D8",
          100: "#DDE4F0",
        },
        // Primary accent. The project is called Rain; cyan is the whole identity.
        rain: {
          50: "#ECFEFF",
          100: "#CFFAFE",
          200: "#A5F3FC",
          300: "#67E8F9",
          400: "#22D3EE",
          500: "#06B6D4",
          600: "#0891B2",
          700: "#0E7490",
          800: "#155E75",
          900: "#164E63",
        },
        // Secondary accent, used only as the far end of gradients.
        iris: {
          300: "#A5B4FC",
          400: "#818CF8",
          500: "#6366F1",
          600: "#4F46E5",
        },
      },
      fontFamily: {
        sans: [
          "Inter var", "Inter", "ui-sans-serif", "system-ui", "-apple-system",
          "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif",
        ],
        mono: [
          "ui-monospace", "SFMono-Regular", "Menlo", "Consolas",
          "Liberation Mono", "monospace",
        ],
      },
      letterSpacing: { tightest: "-0.045em" },
      borderRadius: { "4xl": "2rem" },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,211,238,0.18), 0 8px 40px -12px rgba(34,211,238,0.45)",
        lift: "0 24px 60px -24px rgba(0,0,0,0.85)",
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(18px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "scale-in": {
          from: { opacity: "0", transform: "translateY(8px) scale(0.97)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        // Travelling sheen on the primary CTA. One animation, not five.
        sheen: {
          "0%": { transform: "translateX(-120%)" },
          "60%, 100%": { transform: "translateX(220%)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.95)", opacity: "0.7" },
          "70%": { transform: "scale(1.25)", opacity: "0" },
          "100%": { transform: "scale(1.25)", opacity: "0" },
        },
        equalize: {
          "0%, 100%": { transform: "scaleY(0.35)" },
          "50%": { transform: "scaleY(1)" },
        },
        marquee: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-50%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.7s cubic-bezier(0.16,1,0.3,1) both",
        "fade-in": "fade-in 0.5s ease-out both",
        "scale-in": "scale-in 0.18s cubic-bezier(0.16,1,0.3,1) both",
        float: "float 6s ease-in-out infinite",
        sheen: "sheen 3.2s ease-in-out infinite",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.24,0,0.38,1) infinite",
        equalize: "equalize 1s ease-in-out infinite",
        marquee: "marquee 32s linear infinite",
      },
    },
  },
  plugins: [require("tailwind-scrollbar")],
};
