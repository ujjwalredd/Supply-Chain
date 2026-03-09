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
        // Matches modern-landing design system exactly
        background:      "#FAFAFA",    // surface
        surface:         "#FFFFFF",    // paper
        surfaceRaised:   "#F4F4F5",    // subtle
        foreground:      "#09090B",    // ink
        accent:          "#0070F3",    // Vercel/Linear blue
        accentForeground:"#FFFFFF",
        card:            "#FFFFFF",
        cardForeground:  "#09090B",
        muted:           "#F4F4F5",
        mutedForeground: "#71717A",    // steel
        border:          "rgba(0,0,0,0.06)",
        borderStrong:    "rgba(0,0,0,0.10)",
        destructive:     "#EF4444",
        success:         "#10B981",
        warning:         "#F59E0B",
        info:            "#3B82F6",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "JetBrains Mono", "monospace"],
      },
      backgroundImage: {
        "subtle-grid":
          "linear-gradient(to right, rgba(0,0,0,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,0,0,0.03) 1px, transparent 1px)",
        "hero-glow":
          "radial-gradient(circle at 50% 0%, rgba(0,112,243,0.06), transparent 50%)",
      },
      boxShadow: {
        sm:    "0 1px 2px rgba(0,0,0,0.05)",
        card:  "0 1px 3px rgba(0,0,0,0.04), 0 10px 20px -5px rgba(0,0,0,0.02)",
        glass: "0 4px 32px -4px rgba(0,0,0,0.04)",
        glow:  "0 0 40px -10px rgba(0,112,243,0.15)",
        md:    "0 4px 12px rgba(0,0,0,0.06)",
        lg:    "0 8px 24px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
