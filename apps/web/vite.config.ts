import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiPort = Number(
  process.env.AGENTLABYRINTH_E2E_PROXY_API_PORT ??
    process.env.AGENTLABYRINTH_E2E_API_PORT ??
    '8000',
);
if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535) {
  throw new Error('The E2E API proxy port must be an integer between 1 and 65535');
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
});
