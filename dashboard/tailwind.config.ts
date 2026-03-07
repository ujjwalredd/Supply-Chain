import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background:     "#09090b",
        surface:        "#111117",
        surfaceRaised:  "#16161e",
        foreground:     "#e4e4f0",
        accent:         "#7c6af7",
        accentForeground: "#ffffff",
        card:           "#111117",
        cardForeground: "#e4e4f0",
        muted:          "#16161e",
        mutedForeground:"#52526a",
        border:         "rgba(255,255,255,0.07)",
        borderStrong:   "rgba(255,255,255,0.12)",
        destructive:    "#f87171",
        success:        "#34d399",
        warning:        "#fbbf24",
        info:           "#60a5fa",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      boxShadow: {
        sm:  "0 1px 2px rgba(0,0,0,0.4)",
        md:  "0 4px 12px rgba(0,0,0,0.5)",
        glow:"0 0 20px rgba(124,106,247,0.2)",
      },
    },
  },
  plugins: [],
};

export default config;
