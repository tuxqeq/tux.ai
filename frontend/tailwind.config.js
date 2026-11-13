/** @type {import('tailwindcss').Config} */
//
// Design notes (thesis UI rework, Nov 2026)
// The interface is a redacted case file: cool photocopy paper, ink text, and black toner bars for
// every value the model and the reader are not allowed to see. The bars are the only loud element,
// so the palette has no brand hue. Red is kept for errors and destructive actions only.
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        desk: "#DCDFDA", // sidebar, behind the sheet
        paper: "#E9EBE6", // app background
        sheet: "#F6F7F4", // the page the transcript is written on
        ink: {
          DEFAULT: "#1D2026", // body text, primary buttons
          2: "#555B64", // secondary text (6.4:1 on sheet)
          3: "#7A808A", // hints, timestamps (3.9:1, large/aux text only)
        },
        rule: {
          DEFAULT: "#C5CAC3", // hairlines and input borders
          strong: "#9EA49C",
        },
        toner: "#000000", // redaction bars
        alert: {
          DEFAULT: "#B3261E",
          soft: "#F6E3E1",
        },
      },
      fontFamily: {
        sans: ['"Public Sans Variable"', '"Public Sans"', "system-ui", "sans-serif"],
        type: ['"Courier Prime"', '"Courier New"', "monospace"],
      },
      fontSize: {
        // 1.2 ratio scale around a 15px body
        "2xs": ["11px", { lineHeight: "14px" }],
        xs: ["12.5px", { lineHeight: "18px" }],
        sm: ["13.5px", { lineHeight: "20px" }],
        base: ["15px", { lineHeight: "24px" }],
        lg: ["18px", { lineHeight: "26px" }],
        xl: ["22px", { lineHeight: "30px" }],
        "2xl": ["32px", { lineHeight: "42px" }],
        "3xl": ["40px", { lineHeight: "54px" }],
      },
      transitionTimingFunction: {
        // fast start, soft landing: things that answer a click
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
        // pen stroke: used for bars that are drawn on
        stroke: "cubic-bezier(0.65, 0, 0.35, 1)",
      },
    },
  },
  plugins: [],
};
