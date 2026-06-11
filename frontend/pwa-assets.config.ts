import { defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config'

export default defineConfig({
  // Logo de marca como fuente de los iconos/splash.
  preset: minimal2023Preset,
  images: ['public/active-ia-logo.svg'],
})
