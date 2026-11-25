import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Tailwind config - defines the NexaFlow brand design tokens
 * (color palette + type scale) referenced throughout the app.
 */
export default {
  darkMode: "class",
  content: [
    path.join(__dirname, "index.html"),
    path.join(__dirname, "src/**/*.{js,jsx,ts,tsx}"),
  ],
  theme: {
    extend: {
      colors: {
        // Deep teal-navy - primary brand color, used for headings/buttons
        ink: {
          50: "#EEF3F5",
          100: "#D6E1E6",
          200: "#AEC3CC",
          300: "#7C9DA9",
          400: "#4C7280",
          500: "#2C5566",
          600: "#1B3A4B", // primary
          700: "#152E3C",
          800: "#10202B", // deep panel background
          900: "#0A151C",
        },
        // Warm amber/marigold - signature accent for CTAs & highlights
        amber: {
          50: "#FDF6E9",
          100: "#FAE8C3",
          200: "#F3D08A",
          300: "#EDBB5D",
          400: "#E8A33D", // accent
          500: "#D6892A",
          600: "#B36F20",
        },
        slate: {
          25: "#F7F8FA",
          650: "#425466",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      backgroundImage: {
        "flow-grid":
          "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.08) 1px, transparent 0)",
      },
      boxShadow: {
        card: "0 10px 40px -10px rgba(16, 32, 43, 0.25)",
      },
    },
  },
  plugins: [],
};
