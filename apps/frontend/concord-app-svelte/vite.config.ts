import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 4200,
    proxy: {
      '/v2': {
        target: 'http://localhost:9001',
        changeOrigin: true
      },
      '/auth': {
        target: 'http://localhost:9001',
        changeOrigin: true
      },
      '/socket.io': {
        target: 'http://localhost:9001',
        changeOrigin: true,
        ws: true
      }
    }
  }
});
