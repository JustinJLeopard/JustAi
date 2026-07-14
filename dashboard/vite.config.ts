import { defineConfig, Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { createTrajectoryMiddleware } from './trajectory-middleware'

// Serve trajectory .traj.json files when JUSTAI_TRAJ_DIR is configured.
function trajectoriesPlugin(): Plugin {
  const TRAJ_DIRS: string[] = process.env.JUSTAI_TRAJ_DIR
    ? [process.env.JUSTAI_TRAJ_DIR]
    : []

  return {
    name: 'justai-trajectories',
    configureServer(server) {
      server.middlewares.use('/api/trajectories', createTrajectoryMiddleware(TRAJ_DIRS))
    },
  }
}

export default defineConfig({
  plugins: [react(), trajectoriesPlugin()],
  base: './',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      input: {
        // index.html is the DEMO (the default URL visitors land on at justai-demo.vercel.app/)
        // — rollup uses these keys to name output chunks, so calling this 'demo' makes
        // dist/assets/demo-*.js the file that actually contains demo code.
        demo: path.resolve(__dirname, 'index.html'),
        // app.html is the original production dashboard (LoginPage + SpacetimeDB client).
        // Reachable at justai-demo.vercel.app/app.html for local-dev verification.
        app: path.resolve(__dirname, 'app.html'),
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/__tests__/setup.ts',
  },
  server: {
    port: 3001,
    // The dev-only trajectory route has no authentication surface. Keep the
    // Vite server loopback-only even though file reads are descriptor-contained.
    host: '127.0.0.1',
    proxy: {
      // Proxy memory RPC to claude-flow MCP HTTP server
      '/api/memory': {
        target: 'http://127.0.0.1:3100',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api\/memory/, ''),
      },
      // Proxy orchestrator API endpoints
      '/api/health': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
      '/api/runs': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
      '/api/config': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
      '/api/run': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
      '/api/observability': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
      '/api/trajectory': {
        target: 'http://127.0.0.1:3002',
        changeOrigin: true,
      },
    },
  },
})
