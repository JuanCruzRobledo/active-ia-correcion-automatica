# Handoff: Pendientes Moodle

## Overview

Nueva página **Pendientes** en el dashboard de Active-IA para tutores.
Muestra las entregas de trabajos prácticos que están **a la espera de calificación en Moodle**, organizadas por Unidad → Comisión, con acceso directo vía URL profunda al grader de Moodle con filtros exactos de estado y grupo.

Esta sección es **distinta** al concepto de "Pendientes" ya existente en el dashboard (que refiere a trabajos subidos a la plataforma Active-IA sin corregir). Los nuevos pendientes se obtienen desde Moodle vía **Moodle Mobile App webservice**.

---

## Sobre los archivos de diseño

Los archivos `.html` incluidos en este bundle son **prototipos de referencia creados en HTML** — muestran el aspecto visual y el comportamiento esperado. **No son código de producción para copiar directamente.**

La tarea es **recrear estos diseños en el codebase existente** (React + TypeScript + Tailwind v4 + Tanstack Query), siguiendo los patrones, componentes y convenciones ya establecidos en el proyecto.

## Fidelidad

**Alta fidelidad (hifi):** Los prototipos son pixel-perfect con colores finales, tipografía, espaciados e interacciones. El desarrollador debe recrear la UI con fidelidad usando las librerías y patrones existentes del codebase.

---

## Contexto del codebase

| Aspecto | Detalle |
|---|---|
| Framework | React 18 + TypeScript |
| Estilos | Tailwind CSS v4 + tokens OKLCH en `src/index.css` |
| Routing | React Router v6 |
| Data fetching | Tanstack Query (React Query) |
| Iconos | Lucide React |
| Estructura | Feature-based (`src/features/<feature>/`) |
| Auth / roles | `useAuth()` hook, roles: `TUTOR`, `ADMIN`, `COORDINADOR` |

---

## Pantallas / Vistas

### 1. Página: Pendientes (`/pendientes`)

**Propósito:** Ver todas las entregas de Moodle que requieren calificación, agrupadas por unidad y comisión, con acceso directo al grader de Moodle.

#### Layout general
- Mismo layout que `DashboardTutor.tsx`: `<div className="space-y-8">`
- Header con título + subtítulo + botón "Actualizar" (alineado a la derecha)
- Grid de 3 stat cards (igual que el dashboard)
- Barra de filtros
- Lista de bloques por Unidad (acordeón)

#### Stat Cards (top)
Usar el componente existente `<StatCard>` con variantes:

| Card | Título | Subtítulo | Variante | Ícono Lucide |
|---|---|---|---|---|
| 1 | En espera | requieren calificación | `destructive` | `AlertCircle` |
| 2 | Corregidos | entregas calificadas | `success` | `CheckCircle` |
| 3 | Sin entrega | alumnos no entregaron | `default` | `MinusCircle` |

Los valores son la **suma de todas las comisiones de todas las unidades**.

#### Filtro rápido
Dos botones tipo chip (pill):
- `"Todas las unidades"` — muestra todas las unidades
- `"Solo con pendientes (N)"` — filtra unidades que tienen al menos 1 comisión con `espera > 0`

Estilos chip:
```css
/* inactivo */
padding: 6px 14px; border-radius: 999px; border: 1px solid var(--border);
background: var(--card); font-size: 13px; font-weight: 500; color: var(--muted-fg);

/* activo */
background: oklch(var(--accent)); border-color: oklch(var(--accent)); color: white;
```

#### Bloque por Unidad (acordeón)
Componente: `UnidadBlock.tsx`

**Header del acordeón:**
- Badge numérico de la unidad (fondo `--accent`, texto blanco, `8px border-radius`)
- Título: `"Unidad N: Nombre"`, subtítulo: `"X comisiones"`
- Pills resumen a la derecha:
  - Rojo si `totalEspera > 0`: `oklch(0.55 0.22 27 / 0.1)` bg, `oklch(0.55 0.22 27)` text
  - Verde siempre: `oklch(0.55 0.18 145 / 0.1)` bg, `oklch(0.45 0.18 145)` text
  - Gris siempre: `oklch(0.965 0 0)` bg, `var(--muted-fg)` text, con borde
- Chevron que rota 180° al expandir

**Body del acordeón:**
Lista de `ComisionRow` separados por `border-bottom: 1px solid var(--border)`.

#### Fila por Comisión
Componente: `ComisionRow.tsx`

**Layout:** `grid-template-columns: 1fr auto` con `gap: 16px; padding: 16px 24px`

**Izquierda:**
- Label comisión (ej: `"Comisión 1"`) — `font-size: 13px; font-weight: 600; min-width: 100px`
- Stats en línea separados por punto `·`:
  - 🔴 `N en espera de calificación` — número en `oklch(0.55 0.22 27)`, texto en `--muted-fg`
  - 🟢 `N corregidos` — número en `oklch(0.45 0.18 145)`
  - ⚫ `N sin entrega` — número en `--muted-fg`

**Derecha (solo si `espera > 0`):**
Botón "Ver en Moodle" que abre la URL en nueva pestaña.

```
URL: https://tup.sied.utn.edu.ar/mod/assign/view.php
  ?id={cmid}
  &action=grading
  &status=requiregrading
  &groupsearchvalue={comision.codigo}
  &group={comision.groupId}
```

Estilos del botón:
```css
/* normal */
border: 1px solid var(--border); color: oklch(var(--accent));
padding: 7px 14px; border-radius: var(--radius); font-size: 12px; font-weight: 600;
background: none;

/* hover */
background: oklch(var(--accent)); border-color: oklch(var(--accent)); color: white;
```
Incluir ícono `ExternalLink` (Lucide, 13px) a la izquierda del texto.

---

### 2. Modificación: Dashboard Tutor (`DashboardTutor.tsx`)

Agregar **banner de alerta** al final del componente, después del grid de comisiones:

- Solo se muestra si `totalEspera > 0`
- Fondo: `oklch(0.55 0.22 27 / 0.05)`, borde: `oklch(0.55 0.22 27 / 0.25)`
- Ícono `AlertCircle` en rojo a la izquierda
- Texto: `"N entregas esperando calificación en Moodle"` + subtexto `"Distribuidas en X unidades · sincronizado hace 5 min"`
- Botón a la derecha: `"Ver pendientes"` → navega a `/pendientes`

---

### 3. Modificación: Sidebar (`Sidebar.tsx`)

Agregar ítem de navegación:
```typescript
{ to: '/pendientes', icon: Clock, label: 'Pendientes', roles: ['TUTOR', 'ADMIN'] }
```
Posición: **después de `Entregas`**.

---

## Tipos TypeScript

Crear en `src/features/pendientes/types/index.ts`:

```typescript
export interface ComisionPendiente {
  id: string;
  nombre: string;         // "Comisión 1"
  codigo: string;         // groupsearchvalue para URL Moodle (ej: "m26")
  groupId: number;        // group param para URL Moodle (ej: 4149)
  espera: number;         // submissions con status=requiregrading
  corregidos: number;     // submissions ya calificadas
  sinEntrega: number;     // alumnos sin entrega
}

export interface UnidadPendiente {
  id: number;
  titulo: string;         // "Unidad 1"
  subtitulo: string;      // "Secuenciales"
  cmid: number;           // mod/assign course module ID en Moodle
  comisiones: ComisionPendiente[];
}

export interface PendientesResumen {
  totalEspera: number;
  totalCorregidos: number;
  totalSinEntrega: number;
  unidades: UnidadPendiente[];
  syncedAt: string;       // ISO timestamp
}
```

---

## Estructura de archivos a crear

```
src/features/pendientes/
├── types/
│   └── index.ts
├── services/
│   └── pendientes.service.ts    # GET /api/pendientes/moodle
├── hooks/
│   └── usePendientesMoodle.ts   # Tanstack Query hook
├── components/
│   ├── UnidadBlock.tsx
│   ├── ComisionRow.tsx
│   └── index.ts
├── pages/
│   ├── PendientesPage.tsx
│   └── index.ts
└── index.ts
```

---

## Endpoint Backend

**`GET /api/pendientes/moodle`**

Requiere: autenticación (JWT), rol `TUTOR` o superior.

Responde con `PendientesResumen`.

El backend debe consultar el webservice de Moodle para cada unidad (assign) y cada comisión (group), contando:
- `espera`: submissions donde `status = "requiregrading"` o `gradingstatus = "notgraded"`
- `corregidos`: submissions ya calificadas
- `sinEntrega`: alumnos del grupo que no tienen submission

---

## Design Tokens usados

Todos los tokens viven en `src/index.css` como variables CSS con valores OKLCH.

| Token | Valor OKLCH | Uso |
|---|---|---|
| `--accent` | `0.55 0.15 230` | Sidebar activo, badge unidad, chip activo, botón Moodle hover |
| `--destructive` | `0.55 0.22 27` | Stat card "en espera", dots rojos, banner alerta |
| `--success` | `0.55 0.18 145` | Stat card "corregidos", dots verdes |
| `--muted-fg` | `0.45 0 0` | Textos secundarios, dots grises, sin entrega |
| `--border` | `0.9 0 0` | Bordes de cards, filas |
| `--card` | `1 0 0` | Fondo de cards y bloques |
| `--background` | `0.985 0 0` | Fondo de página |
| `--radius` | `0.5rem` | Border radius de cards y botones |

---

## Interacciones y comportamiento

| Interacción | Comportamiento |
|---|---|
| Click en header de Unidad | Toggle expand/collapse del acordeón |
| Click en "Solo con pendientes" | Filtra y oculta unidades donde todas las comisiones tienen `espera = 0` |
| Click en "Ver en Moodle" | Abre URL en nueva pestaña (`target="_blank"`) |
| Click en "Actualizar" | Invalida la query de Tanstack Query para re-fetch |
| Click en banner del Dashboard | Navega a `/pendientes` |

**Estado inicial:** todas las unidades expandidas.

---

## Archivos en este bundle

| Archivo | Descripción |
|---|---|
| `README.md` | Este documento — especificaciones completas |
| `Pendientes Moodle.html` | Prototipo HTML hifi — referencia visual interactiva |

**Cómo usar el prototipo:**
1. Abrir `Pendientes Moodle.html` en el navegador
2. Navegar entre Dashboard y Pendientes usando el sidebar
3. Activar el panel "Tweaks" (botón en la esquina inferior derecha) para explorar variantes de vista
4. Los botones "Ver en Moodle" apuntan a URLs reales de ejemplo

---

## Notas de implementación

- El componente `UnidadBlock` debe ser un acordeón **controlado localmente** (estado `open` interno con `useState`)
- Si `showUrgentOnly = true` y una unidad no tiene comisiones con `espera > 0`, el bloque no se renderiza
- El botón "Ver en Moodle" solo aparece si `comision.espera > 0`
- El banner del Dashboard solo aparece si `pendientesData?.totalEspera > 0`
- El hook `usePendientesMoodle` debe refetchear cada 5 minutos (`staleTime: 5 * 60 * 1000`)
