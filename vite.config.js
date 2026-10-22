import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      ignored: [
        "**/artifacts/**",
        "**/data/**",
        "**/.venv/**",
        "**/venv/**",
        "**/backend/**",
        "**/__pycache__/**",
        "**/*.{docx,pptx,pdf}",
        "**/~$*"
      ]
    },
    proxy: {
      "/api": "http://127.0.0.1:8000"
    }
  }
});
