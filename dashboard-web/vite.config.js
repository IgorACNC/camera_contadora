import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento (npm run dev), repassa API, fotos e WebSocket para o backend Python.
const BACKEND = process.env.BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": BACKEND,
      "/fotos": BACKEND,
      "/ws": { target: BACKEND.replace(/^http/, "ws"), ws: true },
    },
  },
});
