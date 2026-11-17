import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/shendu/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    proxy: {
      "/shendu/api": {
        target: "http://127.0.0.1:8010",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/shendu\/api/, ""),
      },
    },
  },
});
