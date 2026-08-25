import { defineConfig, type ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'
import type { IncomingMessage } from 'node:http'

// M14 (T-140) added client-side routes at `/cameras` and `/recordings` —
// both collide with backend path prefixes of the same name (M17 (T-208)'s
// `/demo` route is the same case). A plain
// string/target proxy entry intercepts *every* request under that prefix,
// including the browser's top-level HTML navigation to e.g. `/cameras`,
// which used to only ever be an XHR/fetch path before routing existed. This
// `bypass` lets an actual page navigation (`Accept: text/html`) fall
// through to Vite's own SPA-fallback middleware instead of being proxied to
// the backend as an API call; `fetch()` calls from `services/camerasApi.ts`
// et al. don't send that header and still proxy through unchanged.
function bypassNavigationRequests(req: IncomingMessage): string | undefined {
  return req.headers.accept?.includes('text/html') ? '/index.html' : undefined
}

const apiProxy = (bypass = false): ProxyOptions => ({
  target: 'http://localhost:8000',
  ...(bypass ? { bypass: bypassNavigationRequests } : {}),
})

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': apiProxy(),
      '/cameras': apiProxy(true),
      '/streams': apiProxy(),
      '/recordings': apiProxy(true),
      '/demo': apiProxy(true),
      '/rtmp-demo': apiProxy(true),
      '/analytics': apiProxy(),
      '/zones': apiProxy(),
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
