# Parte 8: Sistema de Diseño y Estilos

---

## 1. Introducción

Este documento define el sistema de diseño visual de Active-IA, incluyendo:
- Paleta de colores con tokens CSS
- Tipografía
- Espaciado y dimensiones
- Componentes base
- Iconografía
- Guías de uso

El sistema está diseñado para ser **profesional, limpio y funcional**, optimizado para un dashboard de trabajo donde la claridad y la eficiencia son prioritarias.

---

## 2. Tokens de Color (CSS Custom Properties)

### 2.1 Formato de Color: OKLCH

Se utiliza el espacio de color **OKLCH** por sus ventajas:
- Colores perceptualmente uniformes
- Mejor interpolación en gradientes
- Control intuitivo de luminosidad y saturación

```
oklch(L C H)
- L: Luminosidad (0-1)
- C: Croma/saturación (0-0.4)
- H: Hue/tono (0-360)
```

### 2.2 Tema Claro

```css
:root {
  /* ===== FONDOS ===== */
  --background: oklch(0.985 0 0);      /* Gris muy claro - fondo principal */
  --card: oklch(1 0 0);                /* Blanco puro - tarjetas */
  --popover: oklch(1 0 0);             /* Blanco - popovers/dropdowns */
  --muted: oklch(0.965 0 0);           /* Gris claro - fondos secundarios */
  --secondary: oklch(0.965 0 0);       /* Gris claro - botones secundarios */
  --sidebar: oklch(0.98 0 0);          /* Fondo del sidebar */
  --sidebar-accent: oklch(0.95 0 0);   /* Hover en sidebar */

  /* ===== TEXTOS ===== */
  --foreground: oklch(0.145 0 0);      /* Negro suave - texto principal */
  --card-foreground: oklch(0.145 0 0); /* Texto en tarjetas */
  --popover-foreground: oklch(0.145 0 0);
  --muted-foreground: oklch(0.45 0 0); /* Gris medio - texto secundario */
  --secondary-foreground: oklch(0.205 0 0);
  --sidebar-foreground: oklch(0.145 0 0);

  /* ===== PRIMARIO (Botones principales) ===== */
  --primary: oklch(0.205 0 0);         /* Negro - botones principales */
  --primary-foreground: oklch(0.985 0 0); /* Blanco - texto en botones */

  /* ===== ACCENT (Enlaces, focus, highlights) ===== */
  --accent: oklch(0.55 0.15 230);      /* Azul - enlaces y acentos */
  --accent-foreground: oklch(0.985 0 0);
  --ring: oklch(0.55 0.15 230);        /* Ring de focus */
  --sidebar-primary: oklch(0.55 0.15 230);
  --sidebar-ring: oklch(0.55 0.15 230);

  /* ===== ESTADOS SEMÁNTICOS ===== */
  --success: oklch(0.55 0.18 145);     /* Verde - éxito */
  --success-foreground: oklch(0.985 0 0);
  --warning: oklch(0.7 0.18 85);       /* Amarillo - advertencia */
  --warning-foreground: oklch(0.2 0 0);
  --destructive: oklch(0.55 0.22 27);  /* Rojo - error/peligro */
  --destructive-foreground: oklch(0.985 0 0);
  --info: oklch(0.55 0.15 230);        /* Azul - información */
  --info-foreground: oklch(0.985 0 0);

  /* ===== BORDES ===== */
  --border: oklch(0.9 0 0);            /* Bordes generales */
  --input: oklch(0.9 0 0);             /* Bordes de inputs */
  --sidebar-border: oklch(0.9 0 0);

  /* ===== CHARTS/GRÁFICOS ===== */
  --chart-1: oklch(0.55 0.15 230);     /* Azul */
  --chart-2: oklch(0.55 0.18 145);     /* Verde */
  --chart-3: oklch(0.7 0.18 85);       /* Amarillo */
  --chart-4: oklch(0.55 0.22 27);      /* Rojo */
  --chart-5: oklch(0.55 0.18 280);     /* Púrpura */

  /* ===== DIMENSIONES ===== */
  --radius: 0.5rem;                    /* Border radius base */
}
```

### 2.3 Tema Oscuro

```css
[data-theme="dark"] {
  /* ===== FONDOS ===== */
  --background: oklch(0.1 0 0);        /* Negro profundo */
  --card: oklch(0.14 0 0);             /* Gris muy oscuro */
  --popover: oklch(0.14 0 0);
  --muted: oklch(0.2 0 0);             /* Gris oscuro */
  --secondary: oklch(0.2 0 0);
  --sidebar: oklch(0.12 0 0);
  --sidebar-accent: oklch(0.2 0 0);

  /* ===== TEXTOS ===== */
  --foreground: oklch(0.98 0 0);       /* Blanco */
  --card-foreground: oklch(0.98 0 0);
  --popover-foreground: oklch(0.98 0 0);
  --muted-foreground: oklch(0.65 0 0); /* Gris claro */
  --secondary-foreground: oklch(0.98 0 0);
  --sidebar-foreground: oklch(0.98 0 0);

  /* ===== PRIMARIO ===== */
  --primary: oklch(0.98 0 0);          /* Blanco */
  --primary-foreground: oklch(0.1 0 0); /* Negro */

  /* ===== ACCENT (Cyan/Teal en tema oscuro) ===== */
  --accent: oklch(0.7 0.15 180);       /* Cyan - más vibrante en oscuro */
  --accent-foreground: oklch(0.1 0 0);
  --ring: oklch(0.7 0.15 180);
  --sidebar-primary: oklch(0.7 0.15 180);
  --sidebar-ring: oklch(0.7 0.15 180);

  /* ===== ESTADOS SEMÁNTICOS ===== */
  --success: oklch(0.7 0.2 145);       /* Verde brillante */
  --success-foreground: oklch(0.1 0 0);
  --warning: oklch(0.75 0.18 85);      /* Amarillo brillante */
  --warning-foreground: oklch(0.1 0 0);
  --destructive: oklch(0.55 0.22 27);  /* Rojo */
  --destructive-foreground: oklch(0.98 0 0);
  --info: oklch(0.7 0.15 180);         /* Cyan */
  --info-foreground: oklch(0.1 0 0);

  /* ===== BORDES ===== */
  --border: oklch(0.25 0 0);           /* Gris oscuro */
  --input: oklch(0.2 0 0);
  --sidebar-border: oklch(0.25 0 0);

  /* ===== CHARTS/GRÁFICOS ===== */
  --chart-1: oklch(0.7 0.15 180);      /* Cyan */
  --chart-2: oklch(0.7 0.2 145);       /* Verde */
  --chart-3: oklch(0.75 0.18 85);      /* Amarillo */
  --chart-4: oklch(0.55 0.22 27);      /* Rojo */
  --chart-5: oklch(0.6 0.2 280);       /* Púrpura */
}
```

### 2.4 Mapeo a Tailwind

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // Fondos
        background: 'oklch(var(--background) / <alpha-value>)',
        card: 'oklch(var(--card) / <alpha-value>)',
        popover: 'oklch(var(--popover) / <alpha-value>)',
        muted: 'oklch(var(--muted) / <alpha-value>)',
        secondary: 'oklch(var(--secondary) / <alpha-value>)',

        // Textos
        foreground: 'oklch(var(--foreground) / <alpha-value>)',
        'card-foreground': 'oklch(var(--card-foreground) / <alpha-value>)',
        'muted-foreground': 'oklch(var(--muted-foreground) / <alpha-value>)',

        // Primario
        primary: {
          DEFAULT: 'oklch(var(--primary) / <alpha-value>)',
          foreground: 'oklch(var(--primary-foreground) / <alpha-value>)',
        },

        // Accent
        accent: {
          DEFAULT: 'oklch(var(--accent) / <alpha-value>)',
          foreground: 'oklch(var(--accent-foreground) / <alpha-value>)',
        },

        // Estados
        success: {
          DEFAULT: 'oklch(var(--success) / <alpha-value>)',
          foreground: 'oklch(var(--success-foreground) / <alpha-value>)',
        },
        warning: {
          DEFAULT: 'oklch(var(--warning) / <alpha-value>)',
          foreground: 'oklch(var(--warning-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT: 'oklch(var(--destructive) / <alpha-value>)',
          foreground: 'oklch(var(--destructive-foreground) / <alpha-value>)',
        },
        info: {
          DEFAULT: 'oklch(var(--info) / <alpha-value>)',
          foreground: 'oklch(var(--info-foreground) / <alpha-value>)',
        },

        // Bordes
        border: 'oklch(var(--border) / <alpha-value>)',
        input: 'oklch(var(--input) / <alpha-value>)',
        ring: 'oklch(var(--ring) / <alpha-value>)',

        // Sidebar
        sidebar: {
          DEFAULT: 'oklch(var(--sidebar) / <alpha-value>)',
          foreground: 'oklch(var(--sidebar-foreground) / <alpha-value>)',
          accent: 'oklch(var(--sidebar-accent) / <alpha-value>)',
          border: 'oklch(var(--sidebar-border) / <alpha-value>)',
        },

        // Charts
        chart: {
          1: 'oklch(var(--chart-1) / <alpha-value>)',
          2: 'oklch(var(--chart-2) / <alpha-value>)',
          3: 'oklch(var(--chart-3) / <alpha-value>)',
          4: 'oklch(var(--chart-4) / <alpha-value>)',
          5: 'oklch(var(--chart-5) / <alpha-value>)',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
}
```

---

## 3. Tipografía

### 3.1 Familia Tipográfica

**Geist** como fuente principal (sans-serif y monospace):

```css
:root {
  --font-sans: 'Geist', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace;
}
```

**Instalación:**
```bash
npm install geist
```

**Importación:**
```javascript
import { GeistSans, GeistMono } from 'geist/font'
```

### 3.2 Escala Tipográfica

| Clase | Tamaño | Peso | Uso |
|-------|--------|------|-----|
| `text-xs` | 0.75rem (12px) | normal | Etiquetas pequeñas, badges |
| `text-sm` | 0.875rem (14px) | normal | Texto secundario, labels |
| `text-base` | 1rem (16px) | normal | Texto principal |
| `text-lg` | 1.125rem (18px) | medium | Subtítulos |
| `text-xl` | 1.25rem (20px) | semibold | Títulos de sección |
| `text-2xl` | 1.5rem (24px) | bold | Títulos de página |
| `text-3xl` | 1.875rem (30px) | bold | Títulos principales |

### 3.3 Uso de Fuentes

| Contexto | Fuente |
|----------|--------|
| UI general | Geist Sans |
| Código fuente | Geist Mono |
| Números en tablas | Geist Mono (opcional) |
| Datos técnicos | Geist Mono |

---

## 4. Espaciado

### 4.1 Escala de Espaciado (Tailwind Default)

Se utiliza la escala estándar de Tailwind:

| Clase | Valor | Uso común |
|-------|-------|-----------|
| `1` | 0.25rem (4px) | Micro espaciados |
| `2` | 0.5rem (8px) | Entre elementos inline |
| `3` | 0.75rem (12px) | Padding interno pequeño |
| `4` | 1rem (16px) | Espaciado estándar |
| `5` | 1.25rem (20px) | - |
| `6` | 1.5rem (24px) | Padding de cards |
| `8` | 2rem (32px) | Separación entre secciones |
| `10` | 2.5rem (40px) | - |
| `12` | 3rem (48px) | Márgenes grandes |
| `16` | 4rem (64px) | Secciones principales |
| `20` | 5rem (80px) | Padding de página |

### 4.2 Patrones de Espaciado

```
┌─────────────────────────────────────┐
│ Página (py-8, px-6)                 │
│ ┌─────────────────────────────────┐ │
│ │ Card (p-6)                      │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ Header (pb-4)               │ │ │
│ │ └─────────────────────────────┘ │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ Content (space-y-4)         │ │ │
│ │ │ • Item (gap-2)              │ │ │
│ │ │ • Item (gap-2)              │ │ │
│ │ └─────────────────────────────┘ │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ Footer (pt-4)               │ │ │
│ │ └─────────────────────────────┘ │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

## 5. Border Radius

### 5.1 Escala de Radios

| Variable | Valor | Clase Tailwind | Uso |
|----------|-------|----------------|-----|
| `--radius` | 0.5rem (8px) | `rounded-lg` | Cards, modales, contenedores |
| `--radius - 2px` | 0.375rem (6px) | `rounded-md` | Botones, inputs, selects |
| `--radius - 4px` | 0.25rem (4px) | `rounded-sm` | Badges, tags pequeños |
| `9999px` | - | `rounded-full` | Avatares, indicadores circulares |

### 5.2 Aplicación por Componente

| Componente | Radio |
|------------|-------|
| Card | `rounded-lg` |
| Modal | `rounded-lg` |
| Button | `rounded-md` |
| Input | `rounded-md` |
| Select | `rounded-md` |
| Badge | `rounded-md` o `rounded-full` |
| Avatar | `rounded-full` |
| Tooltip | `rounded-md` |
| Dropdown | `rounded-lg` |
| Alert | `rounded-lg` |

---

## 6. Iconografía

### 6.1 Librería: Lucide React

```bash
npm install lucide-react
```

**Uso básico:**
```jsx
import { FileText, Users, Settings } from 'lucide-react'

<FileText className="h-4 w-4" />
<Users className="h-5 w-5 text-muted-foreground" />
```

### 6.2 Tamaños Estándar

| Tamaño | Clase | Uso |
|--------|-------|-----|
| 16px | `h-4 w-4` | Inline con texto, botones pequeños |
| 20px | `h-5 w-5` | Botones, navegación |
| 24px | `h-6 w-6` | Headers, destacados |
| 32px | `h-8 w-8` | Estados vacíos, ilustraciones |

### 6.3 Iconos por Contexto

**Navegación:**
- `Menu` - Menú hamburguesa
- `X` - Cerrar
- `ChevronDown`, `ChevronRight` - Expandir/colapsar
- `ArrowLeft`, `ArrowRight` - Navegación
- `ExternalLink` - Enlaces externos

**Acciones:**
- `Plus` - Agregar/crear
- `Upload` - Subir archivos
- `Download` - Descargar
- `Edit`, `Pencil` - Editar
- `Trash2` - Eliminar
- `RefreshCw` - Recargar
- `Eye`, `EyeOff` - Ver/ocultar
- `MoreVertical`, `MoreHorizontal` - Más opciones
- `Copy` - Copiar
- `Save` - Guardar

**Estados:**
- `CheckCircle` - Éxito/completado
- `AlertCircle` - Error
- `AlertTriangle` - Advertencia
- `Info` - Información
- `Clock` - Pendiente/tiempo
- `Loader2` - Cargando (con `animate-spin`)
- `CircleDot` - En progreso

**Dominio (Active-IA):**
- `FileText` - Entregas/documentos
- `Code` - Código fuente
- `Users` - Usuarios/tutores
- `GraduationCap` - Estudiantes/educación
- `BookOpen` - Materias/rúbricas
- `FolderOpen` - Comisiones/carpetas
- `Settings` - Configuración
- `LogOut` - Cerrar sesión
- `User` - Perfil
- `Key` - API Key/seguridad
- `Sparkles` - IA/corrección automática

---

## 7. Componentes Base

### 7.1 Catálogo de Componentes

| Componente | Descripción | Prioridad |
|------------|-------------|-----------|
| **Button** | Botón con variantes primary, secondary, destructive, outline, ghost | Alta |
| **Input** | Campo de texto con label, error, helper text, tooltip | Alta |
| **Select** | Dropdown de selección | Alta |
| **Textarea** | Campo de texto multilínea | Alta |
| **Checkbox** | Casilla de verificación | Alta |
| **Card** | Contenedor con fondo elevado | Alta |
| **Badge** | Etiqueta de estado | Alta |
| **Modal/Dialog** | Ventana modal | Alta |
| **Table** | Tabla de datos | Alta |
| **Tabs** | Navegación por pestañas | Alta |
| **Alert** | Mensaje de alerta/notificación | Alta |
| **Tooltip** | Información en hover | Alta |
| **TooltipIcon** | Icono (?) con tooltip | Alta |
| **Progress** | Barra de progreso | Media |
| **Avatar** | Imagen/iniciales de usuario | Media |
| **Dropdown** | Menú desplegable | Media |
| **Skeleton** | Placeholder de carga | Media |
| **Separator** | Línea divisoria | Baja |
| **Sheet** | Panel lateral deslizante | Baja |

### 7.2 Especificación de Componentes

#### Button

**Variantes:**

| Variante | Fondo | Texto | Uso |
|----------|-------|-------|-----|
| `primary` | `--primary` | `--primary-foreground` | Acciones principales |
| `secondary` | `--secondary` | `--secondary-foreground` | Acciones secundarias |
| `destructive` | `--destructive` | `--destructive-foreground` | Eliminar, cancelar |
| `outline` | transparente | `--foreground` | Acciones alternativas |
| `ghost` | transparente | `--foreground` | Acciones sutiles |
| `link` | transparente | `--accent` | Enlaces |

**Tamaños:**

| Tamaño | Padding | Altura | Texto |
|--------|---------|--------|-------|
| `sm` | `px-3` | `h-8` | `text-xs` |
| `default` | `px-4` | `h-9` | `text-sm` |
| `lg` | `px-6` | `h-10` | `text-base` |
| `icon` | `p-2` | `h-9 w-9` | - |

**Estados:**
- `:hover` - Fondo más oscuro/claro según tema
- `:focus-visible` - Ring con `--ring`
- `:disabled` - `opacity-50`, `cursor-not-allowed`
- `loading` - Icono `Loader2` con `animate-spin`

#### Input

**Estructura:**
```
┌─────────────────────────────────────┐
│ Label (?)                           │  ← TooltipIcon opcional
├─────────────────────────────────────┤
│ [Input field                      ] │  ← rounded-md, border
├─────────────────────────────────────┤
│ Helper text o Error message         │  ← text-sm, text-muted o text-destructive
└─────────────────────────────────────┘
```

**Estados:**
- `default` - Borde `--input`
- `:focus` - Ring `--ring`, borde `--accent`
- `error` - Borde `--destructive`, mensaje rojo
- `success` - Borde `--success` (opcional)
- `:disabled` - `opacity-50`, `cursor-not-allowed`

#### Badge

**Variantes:**

| Variante | Fondo | Texto | Uso |
|----------|-------|-------|-----|
| `default` | `--secondary` | `--secondary-foreground` | General |
| `success` | `--success/20` | `--success` | Completado, OK |
| `warning` | `--warning/20` | `--warning` | Advertencia |
| `destructive` | `--destructive/20` | `--destructive` | Error |
| `info` | `--info/20` | `--info` | Información |
| `outline` | transparente | `--foreground` | Neutral |

**Ejemplos de uso:**
- Estado de entrega: "Pendiente" (warning), "Corregido" (success), "Error" (destructive)
- Nivel de criterio: "OK" (success), "WARNING" (warning), "ERROR" (destructive)
- Rol de usuario: "Admin", "Coordinador", "Tutor"

#### Modal/Dialog

**Estructura:**
```
┌─────────────────────────────────────────────┐
│ ╔═════════════════════════════════════════╗ │
│ ║ Header                              [X] ║ │
│ ╠═════════════════════════════════════════╣ │
│ ║                                         ║ │
│ ║ Content                                 ║ │
│ ║ (puede contener Tabs)                   ║ │
│ ║                                         ║ │
│ ╠═════════════════════════════════════════╣ │
│ ║ Footer                    [Cancel][OK]  ║ │
│ ╚═════════════════════════════════════════╝ │
└─────────────────────────────────────────────┘
  ↑ Overlay oscuro (backdrop)
```

**Especificaciones:**
- Ancho: `max-w-lg` (default), `max-w-xl`, `max-w-2xl`, `max-w-4xl`
- Border radius: `rounded-lg`
- Backdrop: Negro con `opacity-50`
- Animación: Fade in + scale sutil

#### Table

**Estructura:**
```
┌──────────────────────────────────────────────────────────┐
│ [Filtros]                              [Buscar...]       │
├────────┬─────────────┬──────────┬──────────┬────────────┤
│ □      │ Alumno ↕    │ Fecha ↕  │ Estado   │ Acciones   │
├────────┼─────────────┼──────────┼──────────┼────────────┤
│ □      │ Juan Pérez  │ 15/01/26 │ ●Pend    │ [···]      │
│ □      │ María López │ 14/01/26 │ ●Corr    │ [···]      │
│ □      │ Pedro García│ 14/01/26 │ ●Error   │ [···]      │
├────────┴─────────────┴──────────┴──────────┴────────────┤
│ Mostrando 1-10 de 45          [<] [1] [2] [3] [4] [>]   │
└──────────────────────────────────────────────────────────┘
```

**Elementos:**
- Header: `bg-muted`, `text-muted-foreground`, `text-sm`, `font-medium`
- Rows: `border-b border-border`, hover `bg-muted/50`
- Checkbox: Primera columna para selección múltiple
- Sort: Iconos `ChevronUp/Down` en headers ordenables
- Pagination: Controles en footer

#### Tabs

**Variantes:**

1. **Default (underline):**
```
┌─────────────────────────────────────┐
│ [Tab 1]  [Tab 2]  [Tab 3]           │
│ ────────                             │  ← Línea bajo tab activo
├─────────────────────────────────────┤
│ Contenido del tab activo            │
└─────────────────────────────────────┘
```

2. **Pills:**
```
┌─────────────────────────────────────┐
│ [Tab 1] [Tab 2] [Tab 3]             │  ← Fondos redondeados
├─────────────────────────────────────┤
│ Contenido del tab activo            │
└─────────────────────────────────────┘
```

**Estados:**
- Default: `text-muted-foreground`
- Active: `text-foreground`, indicador visual
- Hover: `text-foreground`

#### Alert

**Variantes:**

| Variante | Icono | Borde izquierdo | Uso |
|----------|-------|-----------------|-----|
| `default` | `Info` | `--border` | Información general |
| `success` | `CheckCircle` | `--success` | Operación exitosa |
| `warning` | `AlertTriangle` | `--warning` | Advertencia |
| `destructive` | `AlertCircle` | `--destructive` | Error |

**Estructura:**
```
┌────────────────────────────────────────────┐
│ │ ⓘ  Título del alert                      │
│ │    Descripción opcional con más detalles │
└────────────────────────────────────────────┘
  ↑ Borde izquierdo de 4px
```

#### Tooltip

**Posiciones:** `top`, `bottom`, `left`, `right`

**Especificaciones:**
- Fondo: `--popover`
- Texto: `--popover-foreground`
- Border: `--border`
- Padding: `px-3 py-1.5`
- Max width: `max-w-xs`
- Border radius: `rounded-md`
- Shadow: `shadow-md`
- Delay: 200ms antes de mostrar

#### TooltipIcon

Icono de información (?) que muestra un Tooltip al hacer hover.

**Uso:**
- Junto a labels de formularios
- En headers de secciones
- En títulos de cards que necesiten explicación

**Especificaciones:**
- Icono: `Info` o círculo con "?"
- Tamaño: `h-4 w-4`
- Color: `text-muted-foreground`
- Hover: `text-foreground`

---

## 8. Animaciones y Transiciones

### 8.1 Principios

- **Funcionales, no decorativas:** Las animaciones deben comunicar estado o guiar la atención
- **Sutiles y rápidas:** Máximo 300ms para transiciones de UI
- **Respeto por preferencias:** Respetar `prefers-reduced-motion`

### 8.2 Animaciones Permitidas

| Animación | Clase | Uso |
|-----------|-------|-----|
| Spin | `animate-spin` | Indicadores de carga (Loader2) |
| Pulse | `animate-pulse` | Skeletons de loading |
| Fade in | Personalizada | Aparición de modales, tooltips |

### 8.3 Transiciones Estándar

```css
/* Transición base para colores */
.transition-colors {
  transition-property: color, background-color, border-color;
  transition-timing-function: ease;
  transition-duration: 150ms;
}

/* Transición para transformaciones */
.transition-transform {
  transition-property: transform;
  transition-timing-function: ease;
  transition-duration: 200ms;
}

/* Transición completa */
.transition-all {
  transition-property: all;
  transition-timing-function: ease;
  transition-duration: 200ms;
}
```

### 8.4 Efectos de Hover

| Componente | Efecto |
|------------|--------|
| Button | `bg` más oscuro/claro |
| Card interactiva | `scale-[1.02]` + `shadow-lg` |
| Row de tabla | `bg-muted/50` |
| Link | `underline` o cambio de color |
| Sidebar item | `bg-sidebar-accent` |

### 8.5 Animaciones Prohibidas

- Aurora/gradientes animados de fondo
- Floating/bouncing decorativo
- Parallax
- Transiciones largas (>500ms)
- Animaciones en loop sin propósito

---

## 9. Tema y Modo Oscuro

### 9.1 Implementación

**Atributo de tema:**
```html
<html data-theme="light">  <!-- o "dark" -->
```

**Detección de preferencia del sistema:**
```javascript
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
```

**Persistencia:**
- Guardar preferencia en `localStorage`
- Key: `active-ia-theme`
- Valores: `light`, `dark`, `system`

### 9.2 Toggle de Tema

**Ubicación:** En el footer del sidebar o en el dropdown de usuario

**Iconos:**
- Light: `Sun`
- Dark: `Moon`
- System: `Monitor`

### 9.3 Consideraciones de Contraste

| Tema | Ratio mínimo texto | Ratio mínimo UI |
|------|--------------------|--------------------|
| Light | 4.5:1 (AA) | 3:1 |
| Dark | 4.5:1 (AA) | 3:1 |

---

## 10. Responsive Design

### 10.1 Breakpoints (Tailwind Default)

| Breakpoint | Ancho | Dispositivo |
|------------|-------|-------------|
| `sm` | 640px | Móvil grande |
| `md` | 768px | Tablet |
| `lg` | 1024px | Desktop pequeño |
| `xl` | 1280px | Desktop |
| `2xl` | 1536px | Desktop grande |

### 10.2 Patrones Responsive

**Sidebar:**
- `lg+`: Sidebar visible, fijo
- `<lg`: Sidebar oculto, toggle con Sheet

**Tablas:**
- `lg+`: Todas las columnas
- `md`: Columnas esenciales
- `<md`: Cards en lugar de tabla (opcional)

**Cards en grid:**
- `2xl`: 4 columnas
- `xl`: 3 columnas
- `lg`: 2 columnas
- `<lg`: 1 columna

---

## 11. Guías de Uso

### 11.1 Jerarquía Visual

```
1. TÍTULO PRINCIPAL (text-2xl/3xl, font-bold)
   └── 2. Subtítulo de sección (text-xl, font-semibold)
       └── 3. Título de card (text-lg, font-medium)
           └── 4. Labels (text-sm, font-medium, text-muted-foreground)
               └── 5. Texto de ayuda (text-sm, text-muted-foreground)
```

### 11.2 Cuándo Usar Cada Color

| Color | Uso | Ejemplo |
|-------|-----|---------|
| `primary` | Acciones principales | "Guardar", "Corregir" |
| `secondary` | Acciones secundarias | "Cancelar", "Volver" |
| `accent` | Enlaces, highlights | Links, texto destacado |
| `destructive` | Eliminar, errores | "Eliminar", mensajes de error |
| `success` | Éxito, completado | Badge "Corregido", confirmaciones |
| `warning` | Advertencias | Badge "Pendiente", alertas |
| `muted` | Contenido secundario | Texto de ayuda, placeholders |

### 11.3 Espaciado Consistente

| Contexto | Espaciado |
|----------|-----------|
| Entre secciones de página | `space-y-8` |
| Entre cards | `gap-6` |
| Dentro de card | `space-y-4` |
| Entre campos de formulario | `space-y-4` |
| Entre label y input | `space-y-1.5` |
| Entre elementos inline | `gap-2` |

### 11.4 Tooltips - Dónde Usarlos

**Usar tooltips en:**
- Campos de formulario que necesiten explicación
- Iconos de acción sin texto
- Términos técnicos o abreviaciones
- Configuraciones que afecten comportamiento

**Contenido del tooltip:**
- Máximo 2 líneas
- Lenguaje claro y directo
- Sin jerga técnica innecesaria

**Ejemplos:**
| Campo | Tooltip |
|-------|---------|
| API Key Gemini | "Tu clave personal de Google Gemini para usar la IA. Se obtiene en ai.google.dev" |
| Modo consolidación | "Define cómo se combinan los archivos antes de enviarlos a corregir" |
| Sobrescribir | "Si ya existe una entrega del mismo alumno, se reemplazará por la nueva" |

---

## 12. Decisiones de Diseño Tomadas

| Decisión | Valor | Razón |
|----------|-------|-------|
| Espacio de color | OKLCH | Colores perceptualmente uniformes |
| Color accent light | Azul | Profesional, confiable |
| Color accent dark | Cyan/Teal | Vibrante, buena legibilidad |
| Tipografía | Geist | Moderna, legible, con monospace |
| Border radius | 0.5rem base | Profesional sin ser excesivo |
| Iconos | Lucide React | Ligera, consistente, amplia |
| Animaciones | Solo funcionales | Dashboard de trabajo, no distracción |
| Temas | Light + Dark | Preferencia del usuario |
| Espaciado | Tailwind default | Consistencia, sin personalización innecesaria |

---

## 13. Checklist de Implementación

### Variables CSS
- [ ] Definir tokens en `:root` y `[data-theme="dark"]`
- [ ] Configurar Tailwind para usar tokens
- [ ] Implementar toggle de tema
- [ ] Persistir preferencia en localStorage

### Tipografía
- [ ] Instalar y configurar Geist
- [ ] Definir variables de font-family
- [ ] Aplicar escala tipográfica

### Componentes Base
- [ ] Button (5 variantes, 4 tamaños)
- [ ] Input (con label, error, tooltip)
- [ ] Select
- [ ] Textarea
- [ ] Checkbox
- [ ] Card
- [ ] Badge (6 variantes)
- [ ] Modal/Dialog
- [ ] Table (con sort, pagination)
- [ ] Tabs
- [ ] Alert (4 variantes)
- [ ] Tooltip
- [ ] TooltipIcon

### Iconografía
- [ ] Instalar Lucide React
- [ ] Definir tamaños estándar
- [ ] Crear constantes de iconos por contexto

---

*Documento creado para el proyecto Active-IA*
*Parte 8 de 14 de la especificación*
