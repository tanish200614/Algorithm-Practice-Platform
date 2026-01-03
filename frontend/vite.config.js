import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Dev talks to uvicorn on :8000 directly via VITE_API_URL. In the
    // container build VITE_API_URL is empty, so requests go to the same
    // origin and nginx proxies them to the backend.
    proxy: {},
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
