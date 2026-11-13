import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
// Fonts are bundled, not loaded from Google: a privacy tool should not send each visitor's IP
// address to a font CDN, and the demo must work on a network that blocks it.
import "@fontsource-variable/public-sans";
import "@fontsource/courier-prime/400.css";
import "@fontsource/courier-prime/700.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
