import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // FastAPI serves the built board from here.
  build: { outDir: "../foreman/static/app", emptyOutDir: true },
  // In development the board runs on Vite and everything else goes to FastAPI.
  server: {
    proxy: {
      "/api": backend,
      "/login": backend,
      "/logout": backend,
      "/docs": backend,
      "/openapi.json": backend,
    },
  },
});
