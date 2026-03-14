/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          d3: ["d3", "d3-sankey"],
          deckgl: ["@deck.gl/core", "@deck.gl/layers", "@deck.gl/react"],
          maplibre: ["maplibre-gl"],
          framer: ["framer-motion"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
