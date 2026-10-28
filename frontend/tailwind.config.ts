import type { Config } from "tailwindcss";
const v = (n: string) => `rgb(var(--c-${n}) / <alpha-value>)`;
export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        term: { bg: v("bg"), panel: v("panel"), border: v("border"), amber: v("amber"), muted: v("muted"),
                up: v("up"), down: v("down"), info: v("info"), fg: v("fg"), strong: v("strong") },
        risk: { low: "#22c55e", mid: "#eab308", high: "#f97316", hot: "#ef4444" },
      },
      fontFamily: {
        sans: ["\"Noto Sans TC\"", "\"PingFang TC\"", "\"Microsoft JhengHei\"", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "\"Noto Sans TC\"", "\"Microsoft JhengHei\"", "monospace"],
      },
      keyframes: {
        fadeUp: { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "none" } },
        pulseGlow: { "0%,100%": { opacity: "0.55" }, "50%": { opacity: "1" } },
      },
      animation: { "fade-up": "fadeUp .5s ease-out both", glow: "pulseGlow 2.4s ease-in-out infinite" },
    },
  },
  plugins: [],
} satisfies Config;
