import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  const allowedHosts = (env.VITE_ALLOWED_HOSTS || '.trycloudflare.com')
    .split(',')
    .map((host) => host.trim())
    .filter(Boolean)

  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_DEV_PORT) || 5002,
      proxy: {
        '/api': {
          target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:5001',
          changeOrigin: true,
        },
      },
      allowedHosts,
    },
  }
})
