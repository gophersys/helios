import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// Use staging backend when VITE_BACKEND_URL is set, otherwise localhost
const backendUrl = process.env.VITE_BACKEND_URL || 'http://localhost:9001';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 4200,
    proxy: {
      '/v2': {
        target: backendUrl,
        changeOrigin: true,
        secure: false // Allow self-signed certs for staging
      },
      '/auth': {
        target: backendUrl,
        changeOrigin: true,
        secure: false
      },
      '/socket.io': {
        target: backendUrl,
        changeOrigin: true,
        ws: true,
        secure: false
      }
    }
  }
});
