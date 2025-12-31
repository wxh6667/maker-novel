import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [
    vue(),
    // 仅开发时启用，避免生产构建的额外开销
    ...(command === 'serve' ? [vueJsx(), vueDevTools()] : []),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    host: true,  // 监听所有网络接口，WSL 环境下可从 Windows 访问
    port: 3456,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9527',
        changeOrigin: true,
      }
    },
    watch: {
      // WSL 环境下访问 /mnt/ 需要轮询模式
      usePolling: true,
      interval: 1000,
    }
  },
  build: {
    target: 'es2020',
    minify: 'esbuild',
    // 分块策略，避免单文件过大
    rollupOptions: {
      output: {
        manualChunks: {
          'naive-ui': ['naive-ui'],
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
        }
      }
    }
  }
}))
