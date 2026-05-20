/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f1117",
          raised: "#1a1d27",
          overlay: "#22263a",
        },
        accent: {
          DEFAULT: "#6366f1",
          hover: "#4f52d9",
        },
        token: {
          visible: "#10b981",    // green — decrypted, user has access
          redacted: "#6b7280",   // grey — placeholder, no access
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
