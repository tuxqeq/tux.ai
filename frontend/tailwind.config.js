/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#000000",
          raised: "#0d0d0d",
          overlay: "#1a1a1a",
        },
        accent: {
          DEFAULT: "#f9a8c9",
          hover: "#f472b6",
        },
        token: {
          visible: "#10b981",
          redacted: "#6b7280",
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
