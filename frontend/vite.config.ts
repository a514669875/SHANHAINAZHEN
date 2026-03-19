import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  css: {
    preprocessorOptions: {
      scss: { api: 'modern-compiler' as const },
      sass: { api: 'modern-compiler' as const },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            if (req.url?.includes('/ws')) {
              // 后端未启动或重启时 ws 代理会 ECONNRESET，可忽略
              return
            }
            console.error('[Vite] 代理错误:', err.message)
          })
        },
      },
    },
  },
})
