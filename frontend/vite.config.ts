import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import { defineConfig } from 'vite';

// When the project is served through a Windows junction (e.g. C:\claude →
// C:\Users\<user>\claude), Vite's ESM module graph can resolve `/src/main.tsx`
// through the real target while the browser requested it through the junction,
// producing a blank page. Always resolve to the real path so both sides agree.
function realDirname(): string {
  try {
    return fs.realpathSync(__dirname);
  } catch {
    return __dirname;
  }
}

const projectRoot = realDirname();

export default defineConfig({
  root: projectRoot,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(projectRoot, "./src"),
    },
  },
  server: {
    port: 3000,
    host: true,
    // Allow Vite to serve files from the real project root even when the CWD
    // is reached through a junction.
    fs: {
      allow: [projectRoot],
    },
    proxy: {
      '/api': {
        target: `http://localhost:${process.env.API_PORT ?? 8000}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
  },
});
