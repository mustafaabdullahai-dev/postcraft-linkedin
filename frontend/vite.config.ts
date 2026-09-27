import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // 5173 is often taken by other local dev servers; override with VITE_DEV_PORT.
    port: Number(process.env.VITE_DEV_PORT ?? 5174),
    strictPort: true,
    host: process.env.VITE_DEV_HOST ?? "0.0.0.0",
    allowedHosts: [".ngrok-free.dev", ".trycloudflare.com", ".ngrok-free.app"],
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8001",
        changeOrigin: true,
      },
      // User-uploaded post images are served by the backend.
      "/uploads": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});