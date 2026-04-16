import { defineConfig, Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// Serve trajectory .traj.json files from LocalManus logs
function trajectoriesPlugin(): Plugin {
  const TRAJ_DIRS = [
    process.env.JUSTAI_TRAJ_DIR || '/home/justinleopard/projects/LocalManus/logs',
  ]

  return {
    name: 'justai-trajectories',
    configureServer(server) {
      server.middlewares.use('/api/trajectories', (req, res, next) => {
        // List all trajectory files
        if (req.url === '/' || req.url === '') {
          const files: { name: string; size: number; mtime: string }[] = []
          for (const dir of TRAJ_DIRS) {
            try {
              // Top-level .traj.json
              for (const f of fs.readdirSync(dir)) {
                if (f.endsWith('.traj.json')) {
                  const st = fs.statSync(path.join(dir, f))
                  files.push({ name: f, size: st.size, mtime: st.mtime.toISOString() })
                }
              }
              // relay_dispatch subdirectory
              const sub = path.join(dir, 'relay_dispatch')
              if (fs.existsSync(sub)) {
                for (const f of fs.readdirSync(sub)) {
                  if (f.endsWith('.traj.json')) {
                    const st = fs.statSync(path.join(sub, f))
                    files.push({ name: `relay_dispatch/${f}`, size: st.size, mtime: st.mtime.toISOString() })
                  }
                }
              }
            } catch { /* dir not found, skip */ }
          }
          files.sort((a, b) => b.mtime.localeCompare(a.mtime))
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify(files))
          return
        }

        // Serve a specific trajectory file
        const filename = decodeURIComponent(req.url!.slice(1)) // strip leading /
        for (const dir of TRAJ_DIRS) {
          const fp = path.join(dir, filename)
          if (fs.existsSync(fp) && fp.endsWith('.traj.json')) {
            res.setHeader('Content-Type', 'application/json')
            fs.createReadStream(fp).pipe(res)
            return
          }
        }
        res.statusCode = 404
        res.end('Not found')
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), trajectoriesPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        demo: path.resolve(__dirname, 'demo.html'),
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
    host: true,
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
