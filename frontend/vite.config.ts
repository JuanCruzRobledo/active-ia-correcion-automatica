import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // Update controlado por el usuario via toast, no autoUpdate silencioso.
      registerType: 'prompt',
      injectRegister: 'auto',
      manifest: {
        name: 'Active-IA',
        short_name: 'Active-IA',
        description: 'Correccion automatica de practicos con IA',
        id: '/',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        display_override: ['standalone', 'minimal-ui'],
        orientation: 'portrait',
        lang: 'es',
        // Homologado al fondo de la app (tokens OKLCH --background).
        theme_color: '#fbfbfb',
        background_color: '#fbfbfb',
        icons: [
          { src: '/icons/pwa-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        shortcuts: [
          { name: 'Entregas', url: '/entregas' },
          { name: 'Pendientes', url: '/pendientes' },
          { name: 'Dashboard gestor', url: '/dashboard-gestor' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        navigateFallback: '/index.html',
        // Las rutas de API nunca caen al index.html (son del backend).
        navigateFallbackDenylist: [/^\/api/],
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // SOLO GET de /api. NUNCA POST/PUT/PATCH/DELETE: las mutaciones
            // (corregir, eliminar, archivar, subir entrega) deben fallar limpio
            // offline, no servirse de cache stale.
            urlPattern: ({ url, request }) =>
              url.pathname.startsWith('/api/') && request.method === 'GET',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-get',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 100, maxAgeSeconds: 86400 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      // SW solo en build, no en dev (evita confusion con el HMR de Vite).
      devOptions: { enabled: false },
    }),
  ],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    // host:true → el dev server escucha en 0.0.0.0 (accesible desde la red local).
    host: true,
    // En dev la app pega a /api (relativo); Vite lo proxea al backend (puerto 5000
    // del host, segun docker-compose). Asi dev y prod usan la misma URL relativa.
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
