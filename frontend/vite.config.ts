import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend so the frontend can be
// developed with `npm run dev` while the backend runs on :8000. The
// production build (npm run build -> dist/) is served directly by FastAPI
// from the same origin, per spec section 7 ("Serve the production
// frontend and API from the same local origin").
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
