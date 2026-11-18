import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Movilidad Av. Pradilla',
        short_name: 'Pradilla',
        description: 'Horas pico, rutas alternativas y a qué hora salir por la Avenida Pradilla (Chía).',
        lang: 'es-CO',
        theme_color: '#0f3d3e',
        background_color: '#f6f1e7',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Los datos de la API se piden primero a la red; si no hay conexión se usa la última respuesta
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/') && !url.pathname.startsWith('/api/reportes'),
            handler: 'NetworkFirst',
            options: { cacheName: 'api', networkTimeoutSeconds: 4, expiration: { maxEntries: 60, maxAgeSeconds: 86400 } },
          },
          {
            urlPattern: ({ url }) => url.hostname.endsWith('maptiler.com') || url.hostname.endsWith('openstreetmap.org'),
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'tiles', expiration: { maxEntries: 200, maxAgeSeconds: 604800 } },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', ws: true } },
  },
  test: { environment: 'node' },
})
