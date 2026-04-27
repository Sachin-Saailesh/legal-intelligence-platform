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
        background: "#0F2340",
        surface: "#0F2340",
        "surface-container-lowest": "#0A192F",
        "surface-container-low": "#1A1A2E",
        "surface-container": "#1E3A5F",
        "surface-container-high": "#1E3A5F",
        "surface-container-highest": "#334155",
        "on-surface": "#e1e3e4",
        "on-surface-variant": "#94a3b8",
        secondary: "#38bdf8",
        "secondary-container": "#1e3a5f",
        primary: "#adc8f5",
        "primary-container": "#1e3a5f",
        error: "#fb7185",
        "outline-variant": "#334155",
        outline: "#64748b",
      },
      fontFamily: {
        headline: ["Inter", "sans-serif"],
        body: ["Inter", "sans-serif"],
        label: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
        serif: ["Georgia", "serif"],
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        sm: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
