import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(),tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Core REST API (spaces, notes, search)
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },

      // Chat service (or any second microservice)
      "/chat-api": {
        target: "http://localhost:8001",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/chat-api/, ""),
      },
    },
  },
});
