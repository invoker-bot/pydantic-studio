import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Vite builds output INTO the Python package's static/ tree so the
// existing StudioServer._mount_static at "/static" serves it without
// any new route. Setting base="/static/dist/" on production builds
// (only) makes the built index.html reference assets at
// /static/dist/assets/<hash>.js so they resolve via the same mount.
// Dev mode keeps base="/" so `pnpm dev` and its proxy work normally.
const PYTHON_DIST = path.resolve(
  __dirname,
  "../src/pydantic_studio/renderers/html/static/dist",
);

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/dist/" : "/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: PYTHON_DIST,
    emptyOutDir: true,
  },
  server: {
    proxy: {
      // pnpm dev proxies /api/* to the local FastAPI process so the
      // dev SPA can hit the real backend during development.
      "/api": "http://127.0.0.1:8000",
    },
  },
}));
