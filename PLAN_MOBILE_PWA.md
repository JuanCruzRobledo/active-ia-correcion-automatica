# Plan de Implementación — Adaptación Mobile + PWA Profesional de Active-IA

> Frontend: React 19 + Vite + Tailwind v4 + React Router 7. Objetivo: mismo estilo visual que desktop, totalmente responsivo, touch-first, instalable como PWA con sensación de app nativa (AppStore/PlayStore). Base: 143 hallazgos reales sobre 9 áreas auditadas.

---

## 1. Resumen ejecutivo y principios de diseño mobile

El frontend de Active-IA está construido sólidamente para desktop (Tailwind v4 con `@theme`, tokens OKLCH light/dark vía `data-theme`, fuentes Geist, componentes UI con portales correctos), pero **no tiene ninguna capa mobile ni PWA**. Los tres bloqueadores transversales que aparecen en cada área son:

1. **Tablas anchas (5–8 columnas) que solo hacen `overflow-x-auto`** (o ni eso): obligan a scroll horizontal doloroso y dejan la columna de acciones fuera del viewport. Afecta Usuarios, Materias, Comisiones, Rubricas, Entregas, PorEntregar, DetalleModal, TutoresNexo, Notificaciones, ExamenesEditor.
2. **`Modal` base sin variante mobile**: siempre centrado con `p-6`, sin bottom-sheet, sin safe-area, sin full-screen. Tapa contenido con el teclado virtual.
3. **Touch targets por debajo de 44px en todos lados** (`Button` h-8/h-9, iconos `p-1`/`p-1.5`, checkbox 16px, X de cierre `p-1`) e **inputs `text-sm` (14px) que disparan auto-zoom en iOS**.

A nivel infraestructura: no hay `vite-plugin-pwa`, manifest, service worker, iconos PNG, ni meta tags. El viewport no tiene `viewport-fit=cover`, así que `env(safe-area-inset-*)` devuelve 0 (imposible respetar el notch). Sobrevive `App.css` basura del scaffold de Vite (`#root { max-width:1280px; padding:2rem; text-align:center }`) que rompería el layout mobile si está importado, y el `index.html` declara `lang="en"` sobre una app 100% en español.

### Principios rectores

| Principio | Significado operativo |
|-----------|----------------------|
| **Mobile-first incremental** | Las clases base de Tailwind = mobile; `sm:`/`md:`/`lg:` = pantallas mayores. Pero NO reescribimos: agregamos capa mobile y migramos `lg:`-aislado a base mobile donde haga falta. |
| **Paridad visual** | Misma paleta, mismos tokens OKLCH, mismas fuentes. NUNCA se cambia el look. Se cambian layout, densidad y ergonomía táctil. El usuario debe reconocer la misma app. |
| **Touch-first** | Todo elemento interactivo en mobile ≥ 44×44px (Apple HIG). `touch-manipulation` para matar el delay de 300ms. Hover → tap (tooltips, info en `title=`). |
| **App-like, no web-like** | Bottom tab bar fija, bottom-sheets deslizables con drag handle, FAB para acción primaria, `ScrollRestoration`, transiciones con easing iOS, sin `window.confirm/alert/prompt` nativos. |
| **Una sola fuente de verdad** | No duplicar pantallas. Desktop y mobile conviven en el mismo componente vía breakpoints y, donde sea estructural (tabla↔cards), vía un wrapper compartido `ResponsiveTable`. `navConfig` es la única fuente de navegación. |
| **PWA real** | Instalable (Lighthouse Installability OK), offline-shell, update controlado, safe-areas, theme-color sincronizado con el tema. |

---

## 2. Estrategia general y arquitectura responsive

### Breakpoints (contrato, Tailwind v4 default)

| Token | Ancho | Uso |
|-------|-------|-----|
| base | `< 640px` | **Mobile** (360–430px target). Bottom-nav, cards, bottom-sheets, FAB. |
| `sm:` | `≥ 640px` | Phablet / landscape phone. Densificación, grids 2-col. |
| `md:` | `≥ 768px` | Tablet vertical. Tablas empiezan a aparecer en algunos casos. |
| `lg:` | `≥ 1024px` | **Desktop**. Sidebar visible, tablas completas, layout actual intacto. |
| `xl:` | `≥ 1280px` | Desktop ancho. |

Convención por defecto de aparición de tabla: **`hidden lg:block` para la `<table>` + `lg:hidden` para card-list** en ABM admin (6–8 columnas). Para tablas más livianas (DetalleModal, Notificaciones, PorEntregar de 5 col) el breakpoint puede ser `md:`/`sm:` según densidad — se indica por pantalla en §7.

### Cómo conviven desktop y mobile SIN duplicar pantallas

1. **Mismo componente de página.** Cada `*Page.tsx` mantiene su lógica (hooks React Query, filtros, estado). Solo cambia el render presentacional según breakpoint.
2. **Tabla↔Cards** se resuelve con un componente compartido nuevo `ResponsiveTable` (ver §6) que recibe `columns` + un `renderCard(row)` opcional. Internamente renderiza `<table className="hidden lg:table">` y `<div className="lg:hidden ...">`. Así no se duplica la fuente de datos ni la lógica de columnas.
3. **Modal↔Bottom-sheet** se resuelve dentro del propio `Modal` compartido (variante por breakpoint), no por pantalla. Arreglar el primitivo arregla ~12 modales de golpe.
4. **Layout shell**: `AppLayout` renderiza el `Sidebar` (`hidden lg:flex`, ya correcto) y agrega `BottomNav` (`lg:hidden`) como hermano del `<main>`. El `MobileHeader` se mantiene pero se simplifica (deja de ser navegación principal).
5. **Densidad responsive como convención de clases**: `p-4 sm:p-6`, `text-2xl sm:text-3xl`, `space-y-4 sm:space-y-6`, headers `flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`. Estas reglas se aplican consistentemente y se documentan en el design system.

### Orden de ejecución macro (detalle en §8)

```
FUNDACIÓN (design system + PWA + componentes compartidos)
   └─ desbloquea casi todas las pantallas
        └─ PANTALLAS por prioridad de uso real (tutor > admin > config)
             └─ QA + Lighthouse + matriz de dispositivos
```

---

## 3. FUNDACIÓN PWA (paso a paso)

> Hoy NO existe nada de PWA. Esta sección entrega toda la infraestructura de cero. Esfuerzo: alto.

### 3.1 Paquetes a instalar

```bash
cd frontend
npm i -D vite-plugin-pwa            # incluye workbox-window / workbox-build transitivos
npm i -D @vite-pwa/assets-generator # genera iconos 192/512/maskable/apple desde un SVG/PNG fuente
# react-hot-toast: verificar si ya está; si no:
npm i react-hot-toast              # toasts de update / offline-ready (alternativa: componente propio con tokens)
```

### 3.2 Archivos a crear / modificar

| Archivo | Acción |
|---------|--------|
| `frontend/vite.config.ts` | Registrar `VitePWA({...})` (ver 3.4). |
| `frontend/index.html` | Meta tags PWA + viewport-fit + apple-touch + theme-color (ver 3.5). |
| `frontend/public/icons/` | Iconos generados: `pwa-192.png`, `pwa-512.png`, `maskable-512.png`, `apple-touch-icon.png` (180, fondo sólido), `favicon.ico`, `favicon.svg`, `safari-pinned-tab.svg`. |
| `frontend/public/offline.html` | Fallback de navegación offline (minimal, con tokens de marca). |
| `frontend/src/pwa/registerSW.ts` (o en `main.tsx`) | Registro vía `virtual:pwa-register` con `onNeedRefresh`/`onOfflineReady`. |
| `frontend/src/pwa/useInstallPrompt.ts` | Hook que captura `beforeinstallprompt`. |
| `frontend/src/pwa/InstallButton.tsx` | Botón "Instalar app" (oculto si standalone). |
| `frontend/src/pwa/OfflineBanner.tsx` | Barra fija "Sin conexión" basada en `navigator.onLine`. |
| `frontend/src/pwa/pwa-types.d.ts` | `/// <reference types="vite-plugin-pwa/client" />`. |
| `frontend/nginx.conf` | Locations no-cache para `/sw.js` y `/manifest.webmanifest` (ver 3.7). |
| `@vite-pwa/assets-generator` config | `pwa-assets.config.ts` con preset `minimal-2023` + logo fuente 512px. |

### 3.3 Generación de iconos y splash

- Logo fuente: rasterizar `public/active-ia-logo.svg` a un PNG de ≥512px (o usar el SVG directamente si el generador lo acepta).
- `@vite-pwa/assets-generator` preset `minimal-2023` produce: `pwa-192`, `pwa-512`, `maskable-512` (con safe-zone ~10% de padding para que no se recorte el logo en el círculo de Android), `apple-touch-icon` (180×180, **fondo sólido sin transparencia** — iOS no soporta alpha en el touch icon).
- **Apple splash screens**: iOS NO usa el manifest para el splash. Generar `apple-touch-startup-image` por resolución de iPhone target (390/393/430px width) con `pwa-asset-generator` o el generador, y agregar `<link rel="apple-touch-startup-image" media="...">` en `index.html`. Sin esto, al abrir la PWA instalada en iPhone se ve pantalla en blanco. En Android el splash lo arma el navegador desde `background_color` + icon 512.
- Mantener la **paleta de marca idéntica** a desktop.

### 3.4 `vite.config.ts` — VitePWA + Workbox

```ts
import { VitePWA } from 'vite-plugin-pwa'

VitePWA({
  registerType: 'prompt',          // toast de update controlado, no autoUpdate silencioso
  injectRegister: 'auto',
  manifest: {
    name: 'Active-IA',
    short_name: 'Active-IA',
    description: 'Corrección automática de prácticos con IA',
    id: '/',
    start_url: '/?source=pwa',
    scope: '/',
    display: 'standalone',
    display_override: ['standalone', 'minimal-ui'],
    orientation: 'portrait',
    lang: 'es',
    theme_color: '#0f172a',        // homologar al header dark (convertir OKLCH --background a hex)
    background_color: '#ffffff',
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
    navigateFallbackDenylist: [/^\/api/],
    cleanupOutdatedCaches: true,
    runtimeCaching: [
      {
        // SOLO GET de /api — NUNCA POST/PUT/DELETE (no cachear mutaciones de correcciones/entregas)
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
  devOptions: { enabled: false },   // SW solo en build, no en dev (evita confusión de HMR)
})
```

**Crítico**: el `runtimeCaching` filtra `request.method === 'GET'`. Las mutaciones (corregir, eliminar, archivar, subir entrega) NUNCA se cachean — deben fallar limpio offline, no servirse de caché stale.

### 3.5 `index.html` — meta tags

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<!-- NO maximum-scale / user-scalable=no: rompe accesibilidad. El anti-zoom se logra con font-size>=16px -->
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#0f172a" media="(prefers-color-scheme: dark)" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="Active-IA" />
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
<link rel="mask-icon" href="/icons/safari-pinned-tab.svg" color="#0f172a" />
<!-- <link rel="manifest"> lo inyecta VitePWA; confirmar que aparece -->
<!-- apple-touch-startup-image links por resolución (ver 3.3) -->
```

Y cambiar `<html lang="en">` → `<html lang="es">` (afecta lectores de pantalla, autocorrección del teclado y SEO).

### 3.6 Registro del SW + update + offline (en `main.tsx` / `registerSW.ts`)

```ts
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  onNeedRefresh() {
    // toast persistente "Nueva versión disponible — Actualizar" → onClick: updateSW(true)
  },
  onOfflineReady() {
    // toast "Listo para usar sin conexión"
  },
})
```

- Mantener el listener `vite:preloadError` existente como **fallback complementario** (no lo reemplaza).
- **theme-color dinámico**: en el mismo punto donde el `ThemeToggle` setea `data-theme`, actualizar:
  ```ts
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', themeColor)
  ```
  para que la status bar de la PWA siga al tema light/dark.
- **`useInstallPrompt`**: escuchar `beforeinstallprompt`, `e.preventDefault()`, guardar el evento, exponer `install()`. Renderizar `<InstallButton>` (min-h-11) en el bottom-sheet "Más"/perfil. Ocultar si `matchMedia('(display-mode: standalone)').matches` o si no hay evento. Para **iOS** (sin `beforeinstallprompt`): detectar Safari iOS y mostrar instrucciones "Compartir → Agregar a inicio".
- **`OfflineBanner`**: `fixed bottom-0 inset-x-0 z-50 pb-[env(safe-area-inset-bottom)]`, escucha `online`/`offline`, muestra "Sin conexión".

### 3.7 `nginx.conf`

Agregar locations explícitas **ANTES** de la regla genérica `expires 1y immutable`:

```nginx
location = /sw.js {
  add_header Cache-Control "no-cache";
}
location = /manifest.webmanifest {
  add_header Cache-Control "no-cache";
  default_type application/manifest+json;
}
# sumar application/manifest+json a gzip_types
```

Los assets con hash de Vite (JS/CSS) sí pueden quedar `immutable 1y`. `sw.js` y `manifest` deben ser `no-cache` o se rompe el ciclo de update. Confirmar que nginx sirve el SPA en `/` y proxy-pasa `/api` al **mismo dominio** (mismo origin) para que el scope del SW y el `runtimeCaching` cubran las llamadas. Si `VITE_API_URL` apunta a otro host, ajustar el `urlPattern` a ese origin.

---

## 4. NAVEGACIÓN mobile

### Objetivo
Reemplazar el patrón actual (dropdown inline dentro del `MobileHeader`, que se siente web) por una **bottom tab bar fija nativa** + **drawer/bottom-sheet "Más"** para el overflow, conviviendo con el `Sidebar` desktop.

### 4.1 Partición de `navConfig.ts`

ADMIN tiene 11–13 items; una tab bar nativa muestra **4–5 máximo**. Extender `NavItem`:

```ts
interface NavItem {
  // ...campos actuales
  primary?: boolean   // o un campo 'order' numérico
}
```

Derivar dos selectores:
- `primaryNavForRole(role)` → **máx 4 items** para la tab bar.
- `overflowNavForRole(role)` → el resto, al bottom-sheet "Más".

Reparto sugerido por rol (el 4º slot siempre es "Más"):
- **ADMIN** → Dashboard · Materias · Comisiones · **Más**
- **COORDINADOR** → Dashboard · Materias · Comisiones · **Más**
- **TUTOR** → Entregas · Pendientes · Comisiones · **Más**
- **GESTOR** → Dashboard gestor · Gestión · (3º según uso) · **Más**

Las **acciones de cuenta** (perfil, theme toggle, logout) van al bottom-sheet "Más", **nunca** a la tab bar.

### 4.2 Componente `BottomNav.tsx` (nuevo)

```tsx
// fixed bottom-0 inset-x-0 z-50, oculto en desktop
<nav className="lg:hidden fixed bottom-0 inset-x-0 z-50 grid grid-cols-4
                bg-background/95 backdrop-blur-md border-t border-border
                pb-[env(safe-area-inset-bottom)]">
  {primaryItems.map(item => (
    <NavLink className="flex flex-col items-center justify-center min-h-14 gap-0.5
                        text-muted-foreground [&.active]:text-foreground">
      <Icon className="h-6 w-6" />
      <span className="text-[10px] truncate max-w-full">{item.label}</span>
      {/* indicador de activo: barra superior o color */}
    </NavLink>
  ))}
  <button className="..." onClick={openMoreSheet}>  {/* tab "Más" */}
    <Menu className="h-6 w-6" /><span className="text-[10px]">Más</span>
  </button>
</nav>
```

### 4.3 Bottom-sheet "Más" + Drawer accesible reusable

Crear `MoreSheet.tsx` (bottom-sheet) que liste `overflowNavForRole` + acciones de cuenta. Patrón base reusable `<Sheet>`:
- Backdrop `fixed inset-0 bg-black/50 z-40` (cierra al tap).
- Panel `fixed bottom-0 inset-x-0 rounded-t-2xl bg-card z-50 max-h-[85dvh] overflow-y-auto pb-[env(safe-area-inset-bottom)]`.
- **Drag handle**: `mx-auto h-1.5 w-12 rounded-full bg-border my-2`.
- Animación `translate-y` + `transition-transform duration-300` (easing iOS `cubic-bezier(0.32,0.72,0,1)`).
- **Accesibilidad**: `role="dialog" aria-modal="true"`, focus-trap, `useLockBodyScroll` (body `overflow-hidden` mientras abierto), cierre por `Escape` y por **swipe-down** sobre el handle.
- Items de navegación `min-h-12` (48px).

### 4.4 `AppLayout.tsx`

```tsx
<div className="h-[100dvh] flex">            {/* era h-screen → 100dvh */}
  <Sidebar className="hidden lg:flex" />
  <div className="flex-1 flex flex-col">
    <MobileHeader />                          {/* simplificado: logo + perfil, ya no es nav principal */}
    <main className="flex-1 overflow-y-auto overscroll-contain
                     px-4 py-4 sm:p-6 lg:p-8
                     pb-[calc(4rem+env(safe-area-inset-bottom))] lg:pb-8">
      <ScrollRestoration />                   {/* reset de scroll por ruta */}
      <Outlet />
    </main>
    <BottomNav className="lg:hidden" />
  </div>
</div>
```

Cambios clave del layout shell:
- `h-screen` → `h-[100dvh]` (la barra de URL móvil rompe `h-screen`).
- `<main>` padding `p-6` → `px-4 py-4 sm:p-6 lg:p-8` (en 360px, `p-6` come el 13% del ancho).
- `pb-[calc(4rem+env(safe-area-inset-bottom))]` para que el contenido no quede tapado por la bottom-nav ni el home indicator.
- `<ScrollRestoration />` de react-router (sensación nativa al navegar).

### 4.5 `MobileHeader.tsx` (simplificado)

Deja de ser navegación principal. Mantiene: logo + (opcional) título de pantalla + perfil/theme. Correcciones:
- `pt-[env(safe-area-inset-top)]` + `min-h-16` (no `h-16`) para el notch/dynamic island.
- `bg-background/80 backdrop-blur-md` (header translúcido nativo al scrollear).
- Touch targets: hamburguesa y perfil a `min-h-11 min-w-11`.
- Si se conserva un menú: que sea Drawer real con backdrop, no dropdown inline.

### 4.6 FAB (slot reservado)

Para acciones primarias (Subir Entrega, Nuevo tutor nexo, Crear): `fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom))] right-4 z-40 h-14 w-14 rounded-full shadow-lg` (por encima de la bottom-nav).

### 4.7 Deduplicar lógica
`navItemsForRole` está duplicado entre `Sidebar` y `MobileHeader`. Centralizar todo en `navConfig.ts` (única fuente) y que `Sidebar`, `BottomNav` y `MoreSheet` consuman los selectores. Evitar triplicar.

---

## 5. DESIGN SYSTEM responsive (`index.css`)

> Trabajo **aditivo**: se agregan tokens/utilidades sin tocar la paleta OKLCH ni el look. Esfuerzo: medio.

### 5.1 Limpieza previa (crítica)
- **Eliminar `App.css`** (basura del scaffold: `#root { max-width:1280px; padding:2rem; text-align:center }`) y quitar su import. El `#root` debe ser `min-h-dvh w-full` sin padding ni `text-align`. El gobierno de ancho/padding va a containers Tailwind (`mx-auto max-w-screen-xl px-4 sm:px-6 lg:px-8`).
- Verificar que ningún componente use `.logo`/`.card`/`.read-the-docs`.

### 5.2 Utilidades a agregar (Tailwind v4 `@utility`)

| Utilidad | Definición | Uso |
|----------|-----------|-----|
| Safe-area | `@utility pt-safe { padding-top: env(safe-area-inset-top) }` (+ `pb/pl/pr-safe`) y variantes con `max()`: `pb-safe-4 { padding-bottom: max(1rem, env(safe-area-inset-bottom)) }` | Header sticky (top), bottom-nav/FAB/sheets (bottom). |
| Viewport dinámico | `.min-h-dvh { min-height: 100vh; min-height: 100dvh }`, `.h-dvh` análogo | Shell de layout, overlays full-height (en vez de `h-screen`/`100vh`). |
| Touch target | `.touch-target { min-height: 2.75rem; min-width: 2.75rem }` (= `min-h-11 min-w-11`) | Todo interactivo en mobile. |
| Anti-zoom iOS | `@media (max-width: 640px) { input, select, textarea { font-size: 16px } }` | Regla base global: ningún campo < 16px en mobile. |
| Scroll nativo | `.scroll-momentum { -webkit-overflow-scrolling: touch }` + usar `overscroll-contain` | Modales, listas largas, drawer, sheets. |
| Tap feedback | `html { -webkit-tap-highlight-color: transparent }` + `.no-select { user-select: none }` | Botones/FAB/nav (matar el flash gris web). |
| Animaciones mobile | `@keyframes slide-up (translateY(100%)→0)` + `fade-in`, expuestos `.animate-slide-up`/`.animate-fade-in` con `cubic-bezier(0.32,0.72,0,1)`, respetando `prefers-reduced-motion` | Bottom-sheets, drawers, backdrops. |
| Tipografía fluida | tokens `--text-h1: clamp(1.5rem, 5vw, 2.25rem)` como `@utility .text-h1` | Headings que no deben desbordar en 360px. |

### 5.3 Ajustes en `body` / base
- `body { min-height: 100vh; min-height: 100dvh }` (era `100vh` fijo — rompe con teclado virtual).
- Mantener `focus-visible` (correcto: solo teclado). Opcional: ocultar scrollbar custom de 8px en touch: `@media (pointer: coarse) { ::-webkit-scrollbar { width: 0 } }`.

### 5.4 Reglas documentadas (contrato del DS)
- Mobile-first (base = mobile). Headings de pantalla ≤ `text-xl`/`text-2xl` en mobile, escalan con `sm:`/`lg:`.
- Todo interactivo en mobile usa `touch-target` (≥44px).
- Campos de formulario nunca < 16px en mobile.
- Padding de página: `p-4 sm:p-6 lg:p-8`. Spacing vertical: `space-y-4 sm:space-y-6`.

---

## 6. PATRONES DE COMPONENTES COMPARTIDOS

> Esto es lo que **más desbloquea**: arreglar `Table`, `Modal`, `Button`, `Input`/`Select` y `Dropdown`/`MultiSelect` resuelve la mayoría de las pantallas porque se consumen en toda la app. Esfuerzo: alto.

### 6.1 `Table` → card-list responsive (`ResponsiveTable`)

**Approach técnico**: extender `Table.tsx` (o crear wrapper `ResponsiveTable`) que reciba la API actual (`columns`, `data`) + props nuevas:
- `mobileLabel?` por columna (o usar el `header` como label).
- `cardTitle?: (row) => ReactNode` o `primaryColumn`.
- `renderCard?: (row) => ReactNode` (escape hatch para cards custom).

Render:
```tsx
<>
  <table className="hidden lg:table">...</table>   {/* desktop intacto, px-6→px-4 */}
  <div className="lg:hidden flex flex-col gap-3">   {/* card-list mobile */}
    {data.map(row => (
      <div className="rounded-lg border border-border bg-card p-4 min-h-[44px]"
           onClick={onRowClick}>
        {/* título destacado + pares label/valor:
            flex justify-between gap-3 py-1.5 border-b border-border/50 last:border-0 */}
      </div>
    ))}
  </div>
</>
```
- Fila tappable `min-h-[44px]` cuando hay `onRowClick`.
- Quitar `whitespace-nowrap` problemático; `truncate`/`break-all` para emails.
- Reutilizar `EmptyState` (componente dedicado) en lugar del empty inline de texto plano.
- En mobile la columna sticky `right-0` deja de tener sentido (se omite en card).

### 6.2 `Modal` → bottom-sheet / full-screen

**Approach**: variante por breakpoint dentro del propio `Modal.tsx`. Una sola corrección arregla DetalleModal, MateriaForm, modales de Perfil, TutoresNexo, etc.

```tsx
// Backdrop
<div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center
                p-0 sm:p-4 bg-black/50">
  {/* Panel */}
  <div className="w-full sm:max-w-... bg-card
                  rounded-t-2xl sm:rounded-lg
                  max-h-[92dvh] sm:max-h-[90vh] overflow-y-auto overscroll-contain
                  animate-slide-up sm:animate-fade-in
                  pb-[env(safe-area-inset-bottom)]">
    {/* drag handle solo mobile */}
    <div className="mx-auto h-1.5 w-12 rounded-full bg-border my-2 sm:hidden" />
    {/* header/content/footer con p-4 sm:p-6 (no p-6 fijo) */}
    {/* footer sticky bottom-0 bg-card para que el teclado no lo tape */}
  </div>
</div>
```
- Variante `fullScreen` opcional para forms largos: `h-[100dvh] sm:h-auto rounded-none sm:rounded-lg`.
- `100dvh`/`max-h-[92dvh]` en vez de `90vh` (barras móviles).
- **Cierre por tap en backdrop** habilitado en mobile (hoy `disableBackdropClose=true` por defecto deja solo la X). Swipe-down sobre el handle.
- X de cierre a `p-2 min-h-11 min-w-11`.
- Safe-area en footer: `pb-[max(1rem,env(safe-area-inset-bottom))]`; en full-screen `pt-[env(safe-area-inset-top)]` en header.

### 6.3 `Button`

Elevar touch target en mobile sin cambiar el look desktop:
- `default`: `h-11 sm:h-9`
- `lg`: `h-12 sm:h-10`
- `icon`: `h-11 w-11 sm:h-9 sm:w-9`
- `sm` que deba seguir chico visualmente: `min-h-[44px] sm:min-h-0`
- Clase base: agregar `touch-manipulation` (mata delay 300ms + doble-tap-zoom).

Esto beneficia a TODA la app (submits, acciones de card, iconos de cierre/menú).

### 6.4 `Input` / `Select` (anti-zoom + teclado correcto)

- `text-base sm:text-sm` (16px en mobile evita auto-zoom iOS) + altura `h-11 sm:h-10` (o `py-3 sm:py-2`).
- Verificar que **propaguen** `...props` al `<input>`/`<select>` nativo: `inputMode`, `enterKeyHint`, `autoComplete`, `autoCapitalize`, `autoCorrect`, `spellCheck`, `pattern`.
- `touch-manipulation`.
- Convención de uso por caso (a aplicar en pantallas §7):
  - Números (notas, puntajes, año, cmid): `inputMode="numeric"` / `"decimal"`.
  - Email: `inputMode="email" autoCapitalize="none" autoComplete="email"`.
  - Username: `autoCapitalize="none" autoComplete="username"`.
  - Password: `autoComplete="current-password"` / `"new-password"`.
  - Búsqueda: `inputMode="search" enterKeyHint="search"`.
  - Código (mayúsculas): `autoCapitalize="characters" autoCorrect="off" spellCheck={false}`.

### 6.5 `Dropdown` / `MultiSelect` → action-sheet en mobile

- **Dropdown**: en mobile convertir el menú flotante por coordenadas en **bottom-sheet de acciones** full-width (o como mínimo clamp `w-[calc(100vw-2rem)] max-w-[14rem]` para no desbordar). Items `py-3 min-h-[44px] text-base sm:text-sm`. Reemplazar el **cierre-en-scroll** por reposicionamiento (los gestos táctiles scrollean y cierran accidentalmente). Trigger como `<button>` real con `min-h-11 min-w-11`, `aria-haspopup="menu"`, `aria-expanded`.
- **MultiSelect**: en mobile abrir como bottom-sheet full-width (`left:0; width:100vw; rounded-t-2xl`). Opciones `py-3 min-h-[44px]`. X de cada badge a `p-1.5 min-h-9 min-w-9`. Reposicionar con **`visualViewport`** (resize/scroll) para que el teclado virtual no tape el listado.
- **Tooltips de ayuda** (Input/Select/MultiSelect): hoy `group-hover` → inaccesible en touch (no hay hover). Convertir en Popover/bottom-sheet activado por **tap** (`onClick`/`onFocus`), `min-h-11 min-w-11`, o degradar a `helperText` visible. Como mínimo agregar `focus-within:block` además de `group-hover:block`.

### 6.6 `Checkbox` / `Accordion`
- **Checkbox**: `h-5 w-5 sm:h-4 sm:w-4`, envolver input+label en `<label className="flex items-center gap-2 min-h-[44px] py-2 cursor-pointer">`. `items-start` cuando el label puede envolver (Notificaciones). `touch-manipulation`.
- **Accordion**: `min-w-0` al contenedor flex, `truncate`/`line-clamp-2` al texto, `shrink-0` al chevron (evita deformación en 360px). `py-3` ya da ~44px.

### 6.7 `EmptyState` / `Badge`
- `EmptyState`: `text-5xl sm:text-6xl`, `py-8 sm:py-12`, action `w-full sm:w-auto`.
- `Badge`: documentar que es no-interactivo. Para chips tappables (filtros) crear variante `Chip` con `min-h-[32px] px-3 py-1.5`, agrupados con `flex flex-wrap gap-2`.

### 6.8 ConfirmDialog (reemplazo de nativos)
Crear `ConfirmDialog` / action-sheet propio con tokens (respeta dark mode) para reemplazar `window.confirm/alert/prompt` en EntregasPage, RubricasPage, TutoresNexoPage. Botones `min-h-11`, destructivo con `variant="destructive"`, en mobile como bottom-sheet `rounded-t-2xl`.

---

## 7. PLAN POR PANTALLA (agrupado por cluster)

Prioridad: **P0** = bloqueante / uso intenso mobile · **P1** = importante · **P2** = pulido.

### Cluster A — Auth + Dashboard (esfuerzo: medio)

| Pantalla | Cambios clave | Prio |
|----------|--------------|------|
| `LoginPage` | `min-h-screen`→`min-h-dvh` + safe-area wrapper; card `p-6 sm:p-8`, opción edge-to-edge mobile (`rounded-none sm:rounded-lg`); username `inputMode="text" autoCapitalize="none" autoCorrect="off" spellCheck={false}`; quitar `autoFocus` en mobile (abre teclado y empuja layout). | P1 |
| `ChangePasswordPage` | `min-h-dvh` + safe-area; `overflow-y-auto` para alcanzar el submit con teclado abierto; `p-6 sm:p-8`; passwords `autoCapitalize="none" autoCorrect="off" spellCheck={false}`; helper como checklist compacto `text-xs leading-snug`. | P1 |
| `DashboardTutor` | Banner Moodle apilable: `flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between`, botón `w-full sm:w-auto min-h-[44px]` (idealmente `<Button>`); header `text-xl sm:text-2xl`; `gap-4 sm:gap-6`. | P1 |
| `StatCard` | `p-4 sm:p-6`, value `text-2xl sm:text-3xl` (densificar, menos scroll). | P1 |
| `QuickActions` | Botones `min-h-[44px]`; con 10 acciones en mobile considerar acordeón o "Ver más"; `order` para que Actividad Reciente no quede muy abajo. | P2 |
| `DashboardPage` / `DashboardAdmin` / `DashboardCoordinador` | Alert API Key: botón `w-full sm:w-auto min-h-[44px]`; headers con HelpButton `flex items-center gap-2 flex-wrap` + `text-xl sm:text-2xl`. | P2 |
| `RecentActivity` | `line-clamp-2/3`, `p-4 sm:p-6`. | P2 |

> Base sólida: los grids de StatCards ya usan `sm:`/`lg:` y apilan bien.

### Cluster B — ABM admin (esfuerzo: alto) — **P0**

| Pantalla | Cambios clave | Prio |
|----------|--------------|------|
| `UsuariosPage` | `Table`→cards (`ResponsiveTable`) 6 col; trigger acciones `•••`→`MoreVertical` con `min-h-11 min-w-11`; header `flex-col gap-3 sm:flex-row`; filtros: Buscar visible + resto en bottom-sheet; paginación táctil `flex-1 min-h-11`; **eliminar `console.log` por render**. | P0 |
| `ComisionesPage` | `Table`→cards 7 col (la más ancha); filtros 4-col → bottom-sheet "Filtros (N)"; trigger acciones `MoreVertical` 44px; filtro Año `inputMode="numeric"`; `min-w-0`+`truncate` en nombre de materia. | P0 |
| `RubricasPage` | `Table`→cards 8 col; menú de 6 acciones → **action-sheet** (no dropdown anclado que desborda); filtros 5-col → bottom-sheet; reemplazar `window.prompt`/`alert` (duplicar/errores) por modal con `Input inputMode="numeric"` + toasts. | P0 |
| `MateriasPage` | `Table`→cards 6 col; chips "N coordinadores · M comisiones"; trigger 44px; header responsive; `space-y-4 sm:space-y-6`. | P0 |
| `MateriaForm` | Modal→bottom-sheet (resuelto por §6.2); footer `flex flex-col-reverse gap-2 sm:flex-row sm:justify-end`, botones `w-full sm:w-auto min-h-11`; `moodle_course_id` `inputMode="numeric"`; Código `autoCapitalize="characters" autoCorrect="off"`; Descripción → Textarea. | P1 |
| `CohortesPage` | Ya usa grid de cards (buena base); botones Editar/Eliminar `min-h-11 min-w-11`; X de chip `h-6 w-6` + hit-area; `p-4 sm:p-6`; `truncate` en nombre; considerar Dropdown único en vez de 2 iconos chicos. | P1 |
| FAB de creación | Patrón común: `fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] right-4 h-14 w-14 rounded-full shadow-lg z-40` como alternativa al botón de header en mobile (todas las páginas con "Crear"). | P1 |

### Cluster C — Flujos de tutor (esfuerzo: alto) — **P0** (lo más usado desde el celular)

| Pantalla | Cambios clave | Prio |
|----------|--------------|------|
| `EntregasPage` | `Table`→cards 7 col (`hidden md:table` + `md:hidden`), `px-6`→`px-4` desktop; barra de acciones masivas → **action-bar fija inferior** (`fixed bottom-0 inset-x-0 z-40 pb-[env(safe-area-inset-bottom)]`, visible solo si `selectedIds>0`, botones `min-h-11 flex-1`); filtros (search+estado+fechas) → bottom-sheet "Filtros"; "Subir Entrega" → **FAB**; paginación `flex-1 min-h-11` o "Cargar más"; reemplazar `window.confirm/alert` por ConfirmDialog; search `inputMode="search"`; date inputs `min-h-11 w-full`; pull-to-refresh (ya hay polling 10s). | P0 |
| `PorEntregarTable` | Tabla 5 col **sin overflow wrapper** → cards en mobile (`hidden md:block`); sacar el modal de `<tr><td colSpan>` y montarlo a nivel card; chips error/comentario visibles (no en `title=`, que no funciona en touch); botón Subir `w-full min-h-11`. | P0 |
| `ComisionRow` (Pendientes) | `flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`; stats en fila propia `flex flex-wrap gap-2`; acciones `flex flex-wrap gap-2` botones `min-h-11 flex-1 sm:flex-none`; enlaces "Ver en Moodle"/"Ver entregas" `py-1.5`→`min-h-11`. | P0 |
| `MateriaBlock` (Pendientes) | Header `flex flex-col gap-2`: fila toggle `min-h-11`; pills `flex flex-wrap gap-2`; ImportarButton `w-full sm:w-auto`; opción de mostrar solo pill "pendientes" en mobile. | P1 |
| `UnidadBlock` (Pendientes) | Título+subtítulo apilados (`flex flex-col`, no inline `ml-2`); pills `flex flex-wrap gap-1 shrink-0`; toggle `min-h-11`; `truncate`+`min-w-0`. | P1 |
| `PendientesPage` | Header `flex-col gap-3 sm:flex-row`; botón Actualizar icon-only en mobile (`hidden sm:inline` para el label); ImportarButton `w-full sm:w-auto`; toggles filtro → **segmented control** táctil (`inline-flex rounded-full bg-muted p-1`, `min-h-11`). | P1 |
| `PorEntregarPage` | Header `flex-col gap-3 sm:flex-row sm:items-start sm:justify-between`; acciones `flex-1 sm:flex-none min-h-11`; Actualizar icon-only mobile; `p-4 sm:p-6`. | P1 |

### Cluster D — Gestión / Avance / Config de materia (esfuerzo: alto) — el área más dura

| Pantalla | Cambios clave | Prio |
|----------|--------------|------|
| `DetalleModal` (dashboard-gestor) | Tabla 6 col (alumno×examen) → cards (`hidden sm:table` + `sm:hidden space-y-3`); email `break-all`; pares label/valor; aprovecha Modal→bottom-sheet de §6.2; `max-h-[70vh] sm:max-h-[60vh]`. | P0 |
| `ExamenesEditor` | (1) Tabla 5 col → cards. (2) **Quitar anchos fijos px** (`w-44/w-40/w-64/w-32/min-w-[16rem]`) → `grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4`, cada control `w-full`, recupera `sm:col-span-2`. (3) Iconos acción `min-h-11 min-w-11`. (4) cmid `inputMode="numeric"`, nota mínima `inputMode="decimal"`. | P0 |
| `UnidadComponentesEditor` | Filas con `w-36/w-48/min-w-[16rem]` → `grid grid-cols-1 gap-2 sm:grid-cols-[8rem_12rem_1fr_auto] sm:items-end`; botón borrar `min-h-11 min-w-11` (o "Quitar" full-width mobile); separar filas con border/card para que el wrap no confunda; footer `flex flex-col gap-2 sm:flex-row`. | P0 |
| `MateriaDashboardConfigPage` | Tabla Unidades 4 col → cards; cabeceras `flex flex-col gap-2 sm:flex-row`; iconos acción `min-h-11 min-w-11`; `max-h-[420px]`→`max-h-[60vh] sm:max-h-[420px]`; lista de secciones `py-3 sm:py-2.5` + `min-w-0`/`truncate` + badge `shrink-0`. | P0 |
| `GestionPage` | Botones "Pendientes por Práctico/Comisión" `flex flex-col gap-2 sm:flex-row sm:flex-wrap`, `w-full sm:w-auto`; header `flex flex-wrap items-start gap-3`, texto `min-w-0`, HelpButton `shrink-0`. | P1 |
| `EstadoPie` (recharts) | Radios en porcentaje (`outerRadius="80%" innerRadius="55%"`), `height={240}` en mobile; leyenda táctil `min-h-11 px-2 py-1.5` (es el medio principal de interacción en pantalla chica, el slice es muy chico para tocar). | P1 |
| `DashboardGestorPage` | Cabecera gráfico `flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between`; h2 `min-w-0 break-words`; Excel `w-full sm:w-auto`; verificar `px-4 sm:px-6` en root. | P1 |
| `ConfigForm` | "Unidad actual" `inputMode="numeric" pattern="[0-9]*"`; Guardar `w-full sm:w-auto`; grid `sm:grid-cols-2`. | P2 |
| `CronConfigPage` | Filas materia `flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between` + `min-w-0`/`truncate`; header responsive; botón "Seleccionar todas" `min-h-11 w-full sm:w-auto`. | P2 |

### Cluster E — Notificaciones / Tutores Nexo / Perfil (esfuerzo: medio)

| Pantalla | Cambios clave | Prio |
|----------|--------------|------|
| `TutoresNexoPage` | Tabla 5 col **sin overflow** → cards (`hidden md:block` + `md:hidden`), email `break-all`; trigger acciones `min-h-11 min-w-11` + `gap-2` (evitar borrado accidental); header `flex-col gap-3 sm:flex-row`, botón `w-full sm:w-auto` o FAB; reemplazar `window.confirm` por ConfirmDialog. | P0 |
| `NotificacionesPage` | Tabla Historial 5 col → cards (`hidden sm:block` + `sm:hidden`), destinatario `break-all`, error en bloque destacado; checkboxes con labels largos `items-start` + `mt-0.5 shrink-0` + fila `min-h-11`; ayuda con `<code>` `break-words`; botones vista previa `grid grid-cols-1 gap-2 sm:flex` `min-h-11`. | P1 |
| `PerfilPage` | 2 modales (API Key, Password) → bottom-sheet (§6.2, footer sticky, `max-h-[90dvh]`); filas "Estado API Key"/"Seguridad" `flex-col gap-3 sm:flex-row`; inputs con `inputMode`/`autoComplete`/`autoCapitalize` correctos (email/url/username/password/api-key); botones ojo `min-h-11 min-w-11`; `break-all` en emails/`****last4`; opcional header sticky + `pb-[env(safe-area-inset-bottom)]`. | P1 |

---

## 8. ROADMAP POR FASES

Principio: **fundación primero** (desbloquea N pantallas), luego pantallas por prioridad de uso real, QA al final.

| Fase | Contenido | Depende de | Esfuerzo | Desbloquea |
|------|-----------|-----------|----------|-----------|
| **F0 — Design System mobile** | Limpiar `App.css`; `index.css`: safe-area, `100dvh`, touch-target, anti-zoom 16px, `tap-highlight`, animaciones, tipografía fluida; `index.html` viewport-fit + `lang="es"`. | — | Medio | Todo lo demás |
| **F1 — Componentes compartidos** | `Button` (44px), `Input`/`Select` (16px+inputMode), `Modal`→bottom-sheet/full-screen, `Table`→`ResponsiveTable`, `Dropdown`/`MultiSelect`→action-sheet, `Checkbox`/`Accordion`, `ConfirmDialog`, `EmptyState`/`Chip`. | F0 | Alto | Casi todas las pantallas |
| **F2 — Navegación mobile** | Partición `navConfig` (primary/overflow); `BottomNav`; `MoreSheet`/`Sheet` reusable (focus-trap, lock-scroll, swipe); `AppLayout` (100dvh, padding, ScrollRestoration, safe-area); `MobileHeader` simplificado; slot FAB. | F0 (+F1 para sheets) | Alto | Navegación de toda la app |
| **F3 — Fundación PWA** | `vite-plugin-pwa`+Workbox; manifest; iconos/splash; meta tags; SW + update toast + offline banner; `useInstallPrompt`+`InstallButton`; ajustes nginx. | F0 (viewport/index.html) | Alto | Instalabilidad + offline |
| **F4 — Pantallas P0 (uso intenso)** | Cluster C (tutor: Entregas, PorEntregar, Pendientes), Cluster B (ABM: Usuarios, Comisiones, Rubricas, Materias), Cluster D P0 (DetalleModal, editores), Cluster E P0 (TutoresNexo). | F1, F2 | Alto | Valor de negocio principal |
| **F5 — Pantallas P1** | Cluster A (auth/dashboard), resto B/D/E P1 (forms, cohortes, perfil, notificaciones, gestión, recharts). | F1, F2 | Medio | Cobertura completa |
| **F6 — Pulido P2** | QuickActions acordeón, ConfigForm, CronConfig, headers con HelpButton, line-clamps, densidad. | F4, F5 | Bajo | Refinamiento |
| **F7 — QA + Lighthouse** | Matriz de dispositivos, Lighthouse PWA, instalabilidad, safe-area/teclado/offline, DoD por pantalla. | Todo | Medio | Aceptación |

**Camino crítico**: F0 → F1 → F2 → F4. F3 (PWA) corre en paralelo a F2/F4 una vez listo F0. Recomendación: F0 y F1 sin paralelizar (son la base de todo); a partir de F4 se puede repartir por cluster entre devs.

**Orden de dependencias clave**:
- `Modal`→bottom-sheet (F1) debe estar antes que cualquier pantalla con modales (B, D, E).
- `ResponsiveTable` (F1) antes de todas las tablas (B, C, D, E).
- `BottomNav` + `AppLayout` 100dvh + safe-area (F2) antes de validar safe-areas en pantallas.
- `viewport-fit=cover` (F0) habilita `env(safe-area-inset-*)`; sin esto las safe-areas de F2/F3 devuelven 0.

---

## 9. QA Y CRITERIOS DE ACEPTACIÓN

### 9.1 Matriz de dispositivos

| Dispositivo | Viewport | Verificar especialmente |
|-------------|----------|------------------------|
| iPhone SE (2/3 gen) | 375×667 | Pantalla chica + sin notch; densidad, paginación, forms. |
| iPhone 14/15 | 390/393×844 | Dynamic island / notch → safe-area top; home indicator → safe-area bottom; auto-zoom inputs. |
| iPhone 14 Pro Max | 430×932 | Pantalla grande, alcance del pulgar (FAB, bottom-nav, X de cierre). |
| Android chico | 360×640 | **Peor caso de ancho** (360px): tablas→cards, anchos fijos px, overflow horizontal. |
| Android grande / Pixel | 412×915 | `beforeinstallprompt`, install, teclado virtual con `visualViewport`. |
| Tablet vertical | 768/834 | Breakpoint `md:` (tablas reaparecen), grids 2-col. |

### 9.2 Lighthouse PWA — objetivo
- **Installability: PASS** (manifest válido + SW registrado + HTTPS + iconos 192/512/maskable).
- Checks que hoy fallarían y deben pasar: "Web app manifest meets installability requirements", "Registers a service worker", "Configured for a custom splash screen", "Sets a theme color for the address bar", "Provides a valid apple-touch-icon", "Content sized correctly for the viewport" (sin overflow horizontal en 360px).
- Performance mobile ≥ 80 (orientativo, no bloqueante).
- Validar también en **DevTools → Application → Manifest** y verificar el **maskable** en el preview.

### 9.3 Checklist de instalabilidad
- [ ] Manifest con `name`, `short_name`, `start_url`, `display:standalone`, `theme_color`, `background_color`, iconos 192/512/maskable.
- [ ] SW registrado y activo (`Application → Service Workers`).
- [ ] Botón "Instalar app" aparece en Android/desktop; oculto en standalone.
- [ ] iOS: instrucciones "Compartir → Agregar a inicio" visibles en Safari iOS.
- [ ] Apple splash visible al abrir la PWA instalada en iPhone (no pantalla blanca).
- [ ] theme-color sigue al toggle light/dark.
- [ ] Update toast aparece tras nuevo deploy; `updateSW(true)` recarga a la nueva versión.

### 9.4 Pruebas de safe-area / teclado / offline
- **Safe-area**: en iPhone con notch + PWA standalone, header no queda bajo el dynamic island, bottom-nav/FAB/footers de sheet no quedan bajo el home indicator. Probar en modo `black-translucent`.
- **Teclado virtual**: al enfocar inputs NO hay auto-zoom (font ≥16px). En forms largos (ChangePassword, modales) el submit sigue alcanzable (scroll OK, footer sticky). MultiSelect/Dropdown se reposicionan con `visualViewport` y no quedan tapados por el teclado.
- **Offline**: con red cortada, la app abre (shell precacheado), `OfflineBanner` aparece, GETs de `/api` sirven de caché (NetworkFirst), las **mutaciones fallan limpio** (no se cachean), `offline.html` cubre navegaciones sin red.
- **Gestos**: bottom-sheets cierran por swipe-down y tap en backdrop; body no scrollea con sheet abierto; `Escape` cierra; `ScrollRestoration` resetea scroll al navegar.
- **Touch**: ningún target interactivo < 44px (auditar con DevTools). Sin flash gris de tap. `window.confirm/alert/prompt` eliminados (todo con tokens + dark mode).

### 9.5 Definición de "terminado" (DoD) por pantalla
Una pantalla está terminada cuando:
1. **Sin scroll horizontal** en 360px (tablas → cards, anchos fijos px eliminados).
2. **Todos los targets ≥ 44px** (botones, iconos de acción, items de menú, filas tappables).
3. **Inputs con `inputMode`/`autoComplete`/`autoCapitalize` correctos** y font ≥16px (sin auto-zoom).
4. **Modales como bottom-sheet** en mobile, con safe-area y cierre táctil.
5. **Headers/CTAs apilan** (`flex-col gap-3 sm:flex-row`) y botones primarios `w-full sm:w-auto` o FAB.
6. **Paridad visual con desktop** (misma paleta/tokens, dark mode correcto).
7. **Sin `window.confirm/alert/prompt`** ni info crítica en `title=` (hover no existe en touch).
8. **Safe-area respetada** donde haya elementos fijos.
9. **Verificada en al menos**: Android 360px, iPhone 14 (notch), iPhone Pro Max (alcance del pulgar), en light y dark.