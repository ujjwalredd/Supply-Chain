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
        background:       "#f8fafc",
        surface:          "#ffffff",
        surfaceRaised:    "#f1f5f9",
        foreground:       "#0f172a",
        accent:           "#6366f1",
        accentForeground: "#ffffff",
        card:             "#ffffff",
        cardForeground:   "#0f172a",
        muted:            "#f1f5f9",
        mutedForeground:  "#64748b",
        border:           "#e2e8f0",
        borderStrong:     "#cbd5e1",
        destructive:      "#ef4444",
        success:          "#10b981",
        warning:          "#f59e0b",
        info:             "#3b82f6",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
      boxShadow: {
        sm:   "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
        md:   "0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",
        lg:   "0 8px 24px rgba(0,0,0,0.08), 0 4px 8px rgba(0,0,0,0.04)",
        glow: "0 0 20px rgba(99,102,241,0.15)",
        card: "0 1px 3px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
