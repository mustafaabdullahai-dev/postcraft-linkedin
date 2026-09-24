import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: [".ngrok-free.dev", ".trycloudflare.com", ".ngrok-free.app"],
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});