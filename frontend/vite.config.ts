import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    // 127.0.0.1, not localhost: Node 18+ resolves localhost to ::1 first, and uvicorn/Envoy
    // listen on IPv4 only (ECONNREFUSED ::1:8000 on the pod, D-27)
    proxy: {
      // REST API
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      // gRPC-Web via Envoy
      "/chat.ChatService": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
  // `vite preview` serves the built app on the pod (scripts/pod.sh). Vite refuses unknown Host
  // headers, so allow the Runpod HTTP proxy (https://<podId>-3000.proxy.runpod.net).
  preview: {
    allowedHosts: [".proxy.runpod.net"],
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
