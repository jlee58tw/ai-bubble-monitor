import type { Config } from "tailwindcss";
export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        term: { bg: "#0a0c10", panel: "#11151c", border: "#232a35", amber: "#ffb000", muted: "#7d8590",
                up: "#3fb950", down: "#f85149", info: "#58a6ff" },
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"] },
    },
  },
  plugins: [],
} satisfies Config;
