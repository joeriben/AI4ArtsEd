import { fileURLToPath, URL } from 'node:url'

import { defineConfig, type ProxyOptions } from 'vite'
import vue from '@vitejs/plugin-vue'

// The backend takes CF-Connecting-IP from a loopback peer as the client's
// address: the Cloudflare tunnel writes it there
// (devserver/my_app/lab/login_attempts.py). This server is a loopback peer
// as well and listens on every interface, so a request that reaches it from
// another machine carries its own address there in place of whatever it
// sent. `bypass` runs before the request's headers are copied, for every
// request. The backend's check for this machine (settings_routes.py
// `is_localhost_request`) reads the same header, so a browser on another
// machine no longer passes through this server as this machine. A request
// whose peer is already gone is not passed on.
const passClientAddress: NonNullable<ProxyOptions['bypass']> = (req) => {
  const peer = req.socket.remoteAddress
  if (!peer) return false
  if (!/^(127\.|::1$|::ffff:127\.)/.test(peer)) req.headers['cf-connecting-ip'] = peer
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // No PWA plugin: service-worker caching made behaviour inconsistent across
    // iOS and Firefox, so it stayed disabled, and the unused dependency was
    // dropped on 2026-10-10.
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
  },
  server: {
    host: '0.0.0.0',   // Listen on all network interfaces (WLAN + Cloudflare)
    port: 5173,
    strictPort: true,  // Fail if port is already in use (required for Cloudflared)
    allowedHosts: [
      'lab.ai4artsed.org',  // Allow Cloudflare tunnel subdomain
      '.ai4artsed.org',     // Allow all subdomains
    ],
    hmr: true,  // Enable HMR for instant browser updates
    proxy: {
      // Dev frontend proxies to dev backend (17802)
      // Production uses 17801
      '/api': {
        target: 'http://localhost:17802',
        changeOrigin: true,
        bypass: passClientAddress,
      },
      '/exports/json': {
        target: 'http://localhost:17802',
        changeOrigin: true,
        bypass: passClientAddress,
      },
      '/pipeline_configs_with_properties': {
        target: 'http://localhost:17802',
        changeOrigin: true,
        bypass: passClientAddress,
      }
    }
  }
})
