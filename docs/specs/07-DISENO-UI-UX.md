# 07 - Diseño UI/UX

---

## 1. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Layout** | Sidebar fijo izquierda + contenido principal |
| **Sidebar** | w-64, oculto en mobile, logo + nav + footer usuario |
| **Navegación** | Por rol: Admin, Coordinador, Tutor con secciones específicas |
| **Lista de entregas** | Tabla con filtros, acciones en línea, checkboxes |
| **Detalle corrección** | Modal amplio con campos editables |
| **Corrección en lote** | Botón destacado + checkboxes de selección |
| **Tooltips** | En campos, títulos de sección, botones importantes |
| **Temas** | Claro y oscuro (toggle en perfil) |

---

## 2. Estructura de Layout Principal

### 2.1 Diagrama de Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌─────────────┐  ┌─────────────────────────────────────────────────┐  │
│  │   SIDEBAR   │  │              CONTENIDO PRINCIPAL                 │  │
│  │   (w-64)    │  │                                                  │  │
│  │             │  │  ┌───────────────────────────────────────────┐  │  │
│  │ ┌─────────┐ │  │  │ HEADER MOBILE (solo mobile)               │  │  │
│  │ │  Logo   │ │  │  │ hamburguesa | título | avatar             │  │  │
│  │ │ Active  │ │  │  └───────────────────────────────────────────┘  │  │
│  │ │   IA    │ │  │                                                  │  │
│  │ └─────────┘ │  │  ┌───────────────────────────────────────────┐  │  │
│  │             │  │  │                                           │  │  │
│  │ ┌─────────┐ │  │  │          PAGE CONTENT                     │  │  │
│  │ │ Nav     │ │  │  │          (p-6 lg:p-8)                     │  │  │
│  │ │ Items   │ │  │  │                                           │  │  │
│  │ │         │ │  │  │                                           │  │  │
│  │ │ - Home  │ │  │  │                                           │  │  │
│  │ │ - ...   │ │  │  │                                           │  │  │
│  │ │ - ...   │ │  │  │                                           │  │  │
│  │ └─────────┘ │  │  │                                           │  │  │
│  │             │  │  │                                           │  │  │
│  │ ┌─────────┐ │  │  │                                           │  │  │
│  │ │ Footer  │ │  │  │                                           │  │  │
│  │ │ Avatar  │ │  │  │                                           │  │  │
│  │ │ Usuario │ │  │  └───────────────────────────────────────────┘  │  │
│  │ │ Logout  │ │  │                                                  │  │
│  │ └─────────┘ │  │                                                  │  │
│  └─────────────┘  └─────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Especificaciones del Sidebar

```
SIDEBAR
├── Ancho: w-64 (256px) en desktop
├── Posición: fixed left-0 top-0 h-screen
├── Background: bg-bg-secondary
├── Borde: border-r border-border-primary
│
├── HEADER (Logo)
│   ├── Padding: p-6
│   ├── Logo: 40x40px
│   ├── Texto: "Active-IA" font-semibold text-lg
│   └── Separador: border-b border-border-primary
│
├── NAVEGACIÓN
│   ├── Padding: p-4
│   ├── Items: flex flex-col gap-1
│   └── Cada item:
│       ├── Padding: px-4 py-3
│       ├── Border-radius: rounded-xl
│       ├── Icono: 20x20px (lucide-react)
│       ├── Texto: font-medium text-sm
│       ├── Estado normal: text-text-secondary hover:bg-bg-tertiary
│       └── Estado activo: bg-accent-1 text-white
│
└── FOOTER (Usuario)
    ├── Posición: absolute bottom-0
    ├── Padding: p-4
    ├── Border: border-t border-border-primary
    ├── Avatar: 40x40px rounded-full
    ├── Nombre: font-medium text-sm truncate
    ├── Rol: text-xs text-text-disabled capitalize
    └── Botón logout: hover:bg-bg-tertiary rounded-lg p-2
```

### 2.3 Comportamiento Responsive

| Breakpoint | Sidebar | Header Mobile |
|------------|---------|---------------|
| **Mobile (< 768px)** | Oculto (off-canvas) | Visible con hamburguesa |
| **Tablet (768px - 1024px)** | Visible (colapsable a iconos) | Oculto |
| **Desktop (> 1024px)** | Visible completo | Oculto |

**Header Mobile:**
```
┌─────────────────────────────────────────────┐
│  ☰  │        Active-IA         │    👤     │
│     │      (título página)     │           │
└─────────────────────────────────────────────┘
```

---

## 3. Navegación por Rol

### 3.1 Administrador (ADMIN)

```
SIDEBAR ADMIN
│
├── 🏠 Dashboard
│   └── Resumen general, estadísticas, acciones rápidas
│
├── 📚 Materias
│   └── CRUD de materias, asignar coordinadores
│
├── 🏛️ Comisiones
│   └── Ver todas las comisiones, filtrar por materia
│
├── 👥 Usuarios
│   └── CRUD de usuarios (coordinadores, tutores)
│
├── 📋 Rúbricas
│   └── Ver todas las rúbricas, filtrar por materia
│
└── ⚙️ Configuración (futuro)
    └── Settings del sistema
```

### 3.2 Coordinador (COORDINADOR)

```
SIDEBAR COORDINADOR
│
├── 🏠 Dashboard
│   └── Resumen de sus materias, estado de correcciones
│
├── 🏛️ Comisiones
│   └── Gestionar comisiones de sus materias
│
├── 📋 Rúbricas
│   └── Crear/editar rúbricas de sus materias
│
├── 👥 Tutores
│   └── Ver tutores asignados, su progreso
│
└── 📊 Supervisión
    └── Ver estado de correcciones de todas sus comisiones
```

### 3.3 Tutor (TUTOR)

```
SIDEBAR TUTOR
│
├── 🏠 Dashboard
│   └── Resumen de sus comisiones, entregas pendientes
│
├── 📦 Entregas
│   └── Subir y gestionar entregas de alumnos
│
├── ✏️ Correcciones
│   └── Corregir entregas, editar correcciones
│
└── 📄 Reportes
    └── Descargar PDFs, exportar notas
```

---

## 4. Páginas por Rol

### 4.1 Dashboard (Todos los Roles)

El Dashboard es la página de inicio con resumen y acciones rápidas.

**Dashboard Admin:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard Administrativo                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │ 📚 Materias │ │ 🏛️ Comisiones│ │ 👥 Usuarios │ │ 📋 Rúbricas│ │
│  │     5       │ │     85      │ │     25      │ │     42     │ │
│  │   activas   │ │   activas   │ │   activos   │ │   activas  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │
│                                                                  │
│  ┌─────────────────────────────┐ ┌─────────────────────────────┐ │
│  │ Acciones Rápidas            │ │ Actividad Reciente          │ │
│  │                             │ │                             │ │
│  │ [+ Crear Materia]           │ │ • Usuario X creado          │ │
│  │ [+ Crear Usuario]           │ │ • Materia Y actualizada     │ │
│  │ [+ Crear Comisión]          │ │ • Rúbrica Z creada          │ │
│  └─────────────────────────────┘ └─────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Dashboard Coordinador:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard - Mis Materias                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ 🏛️ Comisiones│ │ 📋 Rúbricas │ │ ⏳ Pendientes│               │
│  │     17      │ │     12      │ │    145      │                │
│  │  asignadas  │ │   activas   │ │  de corregir│                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Estado de Correcciones por Comisión                         │ │
│  │                                                             │ │
│  │ Prog1 - Comisión A (Carlos)  ████████░░░░ 75%              │ │
│  │ Prog1 - Comisión B (Ana)     ██████████░░ 85%              │ │
│  │ Prog2 - Comisión A (Luis)    ████░░░░░░░░ 35%              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Dashboard Tutor:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard - Mis Comisiones                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ 🏛️ Comisiones│ │ ⏳ Pendientes│ │ ✅ Corregidas│               │
│  │     2       │ │     28      │ │     156     │                │
│  │  asignadas  │ │  de corregir│ │   entregas  │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Mis Comisiones                                              │ │
│  │                                                             │ │
│  │ ┌─────────────────────────┐ ┌─────────────────────────┐    │ │
│  │ │ Programación 1          │ │ Programación 2          │    │ │
│  │ │ Comisión A - 2026       │ │ Comisión B - 2026       │    │ │
│  │ │ 35 alumnos              │ │ 32 alumnos              │    │ │
│  │ │ 12 pendientes           │ │ 16 pendientes           │    │ │
│  │ │ [Ver entregas]          │ │ [Ver entregas]          │    │ │
│  │ └─────────────────────────┘ └─────────────────────────┘    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.2 Página de Entregas (Tutor)

La página de entregas es donde el tutor gestiona las entregas de alumnos.

**Estructura de la Página:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Entregas                                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ SELECTORES (en fila)                                        │ │
│  │                                                             │ │
│  │ Materia: [Programación 1 ▼]   Comisión: [Comisión A ▼]     │ │
│  │                                                             │ │
│  │ Rúbrica: [TP1 - Listas ▼]                                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ BARRA DE ACCIONES                                           │ │
│  │                                                             │ │
│  │ [+ Subir Entrega]  [📦 Subir Lote]  │  [✨ Corregir Pend.]  │ │
│  │                                     │                       │ │
│  │ 🔍 Buscar alumno...                 │  Filtro: [Todos ▼]   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ TABLA DE ENTREGAS                                           │ │
│  │                                                             │ │
│  │ ☐ │ Alumno          │ Estado    │ Nota  │ Fecha    │ Acc.  │ │
│  │───┼─────────────────┼───────────┼───────┼──────────┼───────│ │
│  │ ☐ │ Pérez, Juan     │ ✅ Correg │ 85    │ 15/01/26 │ ••• │ │
│  │ ☐ │ González, María │ ⏳ Pend.  │ -     │ 15/01/26 │ ••• │ │
│  │ ☐ │ López, Carlos   │ ⚠️ Subido │ -     │ 14/01/26 │ ••• │ │
│  │ ☐ │ Martínez, Ana   │ ❌ Error  │ -     │ 14/01/26 │ ••• │ │
│  │                                                             │ │
│  │ Mostrando 1-20 de 35                    [< 1 2 >]          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Menú de Acciones (•••) por Fila:**
- ✏️ Corregir / Recorregir
- 📊 Ver Detalle (si corregido)
- ✏️ Editar Corrección (si corregido)
- 📄 Descargar PDF (si corregido)
- 🗑️ Eliminar

**Estados y Badges:**

| Estado | Badge | Color |
|--------|-------|-------|
| Subido | ⚠️ Subido | Amarillo (warning) |
| Pendiente | ⏳ Corrigiendo | Azul (info) |
| Corregido | ✅ Corregido | Verde (success) |
| Error | ❌ Error | Rojo (danger) |

---

### 4.3 Modal de Detalle/Edición de Corrección

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ╳                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Corrección: Pérez, Juan                                         │   │
│  │ TP1 - Listas en Python                                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ NOTA FINAL                                          [Recalcular]│   │
│  │ ┌─────────────────────────────────────────────────────────────┐ │   │
│  │ │                         85 / 100                            │ │   │
│  │ └─────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ CRITERIOS DE EVALUACIÓN                                         │   │
│  │                                                                 │   │
│  │ ┌─ Funcionalidad correcta ──────────────────────────────────┐  │   │
│  │ │ Puntaje: [35 ▼] / 40      Estado: [⚠️ Warning ▼]          │  │   │
│  │ │                                                           │  │   │
│  │ │ Feedback:                                                 │  │   │
│  │ │ ┌───────────────────────────────────────────────────────┐ │  │   │
│  │ │ │ Error en el manejo de lista vacía. El resto de las    │ │  │   │
│  │ │ │ funciones operan correctamente.                       │ │  │   │
│  │ │ └───────────────────────────────────────────────────────┘ │  │   │
│  │ └───────────────────────────────────────────────────────────┘  │   │
│  │                                                                 │   │
│  │ ┌─ Uso correcto de listas ──────────────────────────────────┐  │   │
│  │ │ Puntaje: [30 ▼] / 30      Estado: [✅ OK ▼]               │  │   │
│  │ │ ...                                                       │  │   │
│  │ └───────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ FORTALEZAS                                              [+ Add] │   │
│  │ • Buen uso de list comprehensions                         [x]  │   │
│  │ • Código bien organizado y legible                        [x]  │   │
│  │ • Nombres de variables descriptivos                       [x]  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ RECOMENDACIONES                                         [+ Add] │   │
│  │ 1. Agregar validación para listas vacías                  [x]  │   │
│  │ 2. Incluir docstrings en las funciones                    [x]  │   │
│  │ 3. Considerar manejo de excepciones                       [x]  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ COMENTARIO GENERAL                                              │   │
│  │ ┌───────────────────────────────────────────────────────────┐   │   │
│  │ │ Buen trabajo en general. El código demuestra comprensión  │   │   │
│  │ │ de los conceptos de listas. Las principales áreas de      │   │   │
│  │ │ mejora son el manejo de casos borde y la documentación.   │   │   │
│  │ └───────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    [Cancelar]        [Guardar Cambios]          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 4.4 Modal de Subir Entrega

```
┌─────────────────────────────────────────────────────────────────┐
│  ╳                                                              │
│  Subir Entrega                                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Nombre del Alumno *                              ℹ️      │   │
│  │ ┌─────────────────────────────────────────────────────┐ │   │
│  │ │ Pérez, Juan                                         │ │   │
│  │ └─────────────────────────────────────────────────────┘ │   │
│  │ Tooltip: "Ingresa el nombre como aparecerá en el PDF"   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Archivo *                                        ℹ️      │   │
│  │ ┌─────────────────────────────────────────────────────┐ │   │
│  │ │  📁  Arrastra un archivo aquí o haz clic           │ │   │
│  │ │      Formatos: .zip, .txt (máx 10MB)               │ │   │
│  │ └─────────────────────────────────────────────────────┘ │   │
│  │ Tooltip: "ZIP con el proyecto o TXT con código"         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Modo de Consolidación                            ℹ️      │   │
│  │ ┌─────────────────────────────────────────────────────┐ │   │
│  │ │ ○ Solo código (.py, .java, .js...)                 │ │   │
│  │ │ ● Web completo (+ .html, .css, .json)              │ │   │
│  │ │ ○ Proyecto completo (+ .md, .yml, .xml)            │ │   │
│  │ │ ○ Personalizado                                    │ │   │
│  │ └─────────────────────────────────────────────────────┘ │   │
│  │ Tooltip: "Qué tipos de archivo incluir en la corrección"│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ☐ Sobrescribir si ya existe una entrega del alumno      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                [Cancelar]         [Subir Entrega]        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Sistema de Tooltips

### 5.1 Componente TooltipIcon

El icono ℹ️ aparece junto a elementos que necesitan explicación:

```tsx
<TooltipIcon
  content="Explicación del campo o acción"
  position="top" // top | bottom | left | right
/>
```

### 5.2 Dónde Usar Tooltips

| Ubicación | Ejemplo de Tooltip |
|-----------|-------------------|
| **Campos de formulario** | "Ingresa el nombre como aparecerá en el PDF de devolución" |
| **Títulos de sección** | "Sube un archivo ZIP con el proyecto del alumno" |
| **Botones importantes** | "Corrige todas las entregas pendientes de esta rúbrica" |
| **Estados** | "Esta entrega está siendo procesada por la IA" |
| **Iconos de acción** | "Descargar PDF de devolución" |

### 5.3 Tooltips Obligatorios por Sección

**Página de Entregas:**
- Selector de Rúbrica: "Selecciona el trabajo práctico a corregir"
- Botón "Corregir Pendientes": "Corrige automáticamente todas las entregas sin corregir"
- Columna Nota: "Calificación sobre 100 puntos"
- Columna Estado: "Estado actual del proceso de corrección"

**Modal Subir Entrega:**
- Campo Nombre: "Nombre del alumno como aparecerá en los reportes"
- Campo Archivo: "Sube un ZIP con el proyecto o un TXT con el código consolidado"
- Modo Consolidación: "Define qué tipos de archivo se incluyen en la corrección"
- Checkbox Sobrescribir: "Si ya existe una entrega del alumno, la reemplazará"

**Modal Edición Corrección:**
- Botón Recalcular: "Suma los puntajes de todos los criterios"
- Campo Estado: "OK = cumplido, WARNING = observaciones, ERROR = problemas graves"
- Botón Agregar Fortaleza: "Añade un punto positivo del trabajo"

**Página de Rúbricas:**
- Botón "Crear desde PDF": "La IA extraerá los criterios del PDF de la consigna"
- Campo Puntaje Máximo: "La suma de todos los criterios debe ser 100"
- Campo Niveles: "Define diferentes niveles de logro con sus puntajes"

---

## 6. Componentes UI Reutilizables

### 6.1 Catálogo de Componentes

| Componente | Descripción |
|------------|-------------|
| **Button** | Botones con variantes: primary, secondary, danger, ghost |
| **Input** | Campo de texto con label, error, tooltip |
| **Select** | Selector desplegable |
| **Modal** | Ventana modal con header, body, footer |
| **Card** | Contenedor con título opcional |
| **Table** | Tabla con sorting, paginación, selección |
| **Badge** | Etiqueta de estado con colores |
| **Tooltip** | Tooltip posicionable |
| **TooltipIcon** | Icono ℹ️ con tooltip |
| **Spinner** | Indicador de carga |
| **Alert** | Mensaje de alerta/error/éxito |
| **Dropdown** | Menú desplegable |
| **Checkbox** | Casilla de verificación |
| **Radio** | Botones de opción |
| **Textarea** | Campo de texto multilínea |
| **FileUpload** | Zona de drag & drop para archivos |
| **Tabs** | Pestañas de navegación |
| **Progress** | Barra de progreso |
| **Avatar** | Imagen/iniciales de usuario |
| **Skeleton** | Placeholder de carga |

### 6.2 Variantes de Button

```tsx
// Variantes
<Button variant="primary">Acción Principal</Button>
<Button variant="secondary">Acción Secundaria</Button>
<Button variant="danger">Eliminar</Button>
<Button variant="ghost">Cancelar</Button>

// Tamaños
<Button size="sm">Pequeño</Button>
<Button size="md">Normal</Button>
<Button size="lg">Grande</Button>

// Estados
<Button loading>Cargando...</Button>
<Button disabled>Deshabilitado</Button>
```

### 6.3 Variantes de Badge

```tsx
<Badge variant="success">✅ Corregido</Badge>
<Badge variant="warning">⚠️ Subido</Badge>
<Badge variant="info">⏳ Corrigiendo</Badge>
<Badge variant="danger">❌ Error</Badge>
<Badge variant="neutral">Borrador</Badge>
```

---

## 7. Flujos de Usuario

### 7.1 Flujo: Tutor Corrige Entregas

```
1. Tutor hace login
   │
   ▼
2. Ve Dashboard con resumen de comisiones
   │
   ▼
3. Clic en "Entregas" en sidebar
   │
   ▼
4. Selecciona Materia → Comisión → Rúbrica
   │
   ▼
5. Ve tabla de entregas
   ├── Filtra por estado si necesario
   │
   ▼
6. Opción A: Corregir Individual
   │  └── Clic en menú (•••) → Corregir
   │      └── Espera ~60 segundos
   │      └── Ve resultado en tabla (nota)
   │
   └── Opción B: Corregir en Lote
       └── Clic en "Corregir Pendientes"
       └── Ve progreso (12/28...)
       └── Al terminar, ve resumen
   │
   ▼
7. Revisa correcciones
   └── Clic en menú (•••) → Ver Detalle
   └── Si necesita ajustar → Editar Corrección
   └── Modal con campos editables
   └── Guardar cambios
   │
   ▼
8. Genera PDFs
   └── Clic en "Descargar todos los PDFs"
   └── Descarga ZIP
```

### 7.2 Flujo: Coordinador Crea Rúbrica desde PDF

```
1. Coordinador en Dashboard
   │
   ▼
2. Clic en "Rúbricas" en sidebar
   │
   ▼
3. Clic en "+ Nueva Rúbrica"
   │
   ▼
4. Selecciona "Crear desde PDF"
   │
   ▼
5. Formulario:
   ├── Selecciona Materia
   ├── Selecciona Tipo (TP, Parcial, etc.)
   ├── Ingresa Número y Año
   └── Sube PDF de consigna
   │
   ▼
6. Clic en "Generar Criterios"
   │
   ▼
7. IA procesa y extrae criterios
   │
   ▼
8. Muestra criterios extraídos para revisión
   ├── Coordinador puede editar
   ├── Ajustar puntajes
   └── Agregar/quitar criterios
   │
   ▼
9. Clic en "Guardar Rúbrica"
   │
   ▼
10. Rúbrica disponible para todas las comisiones
```

---

## 8. Estados Vacíos y Errores

### 8.1 Estados Vacíos

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                           📭                                    │
│                                                                 │
│                   No hay entregas aún                           │
│                                                                 │
│     Sube la primera entrega usando el botón "Subir Entrega"     │
│                                                                 │
│                   [+ Subir Entrega]                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Estados de Error

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️ Error al cargar entregas                                    │
│                                                                 │
│  No se pudo conectar con el servidor. Verifica tu conexión      │
│  a internet e intenta nuevamente.                               │
│                                                                 │
│                    [Reintentar]                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 Estados de Carga

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                          ⏳                                     │
│                     Cargando...                                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Responsive Design

### 9.1 Breakpoints

| Nombre | Ancho | Uso |
|--------|-------|-----|
| **sm** | 640px | Mobile landscape |
| **md** | 768px | Tablet |
| **lg** | 1024px | Desktop pequeño |
| **xl** | 1280px | Desktop |
| **2xl** | 1536px | Desktop grande |

### 9.2 Adaptaciones por Breakpoint

**Mobile (< 768px):**
- Sidebar oculto, accesible por hamburguesa
- Header móvil visible
- Tablas convertidas a cards
- Modales full-screen
- Botones de acción en menú flotante

**Tablet (768px - 1024px):**
- Sidebar colapsable (solo iconos)
- Tablas con scroll horizontal
- Modales con ancho máximo 90%

**Desktop (> 1024px):**
- Sidebar expandido completo
- Tablas normales
- Modales centrados (max-width: 800px)

---

## 10. Accesibilidad

### 10.1 Requisitos

| Aspecto | Implementación |
|---------|----------------|
| **Contraste** | Ratio mínimo 4.5:1 para texto |
| **Focus visible** | Ring de focus en todos los elementos interactivos |
| **Keyboard navigation** | Tab para navegar, Enter/Space para activar |
| **Screen readers** | Labels apropiados, aria-labels donde necesario |
| **Errores** | Mensajes claros, asociados al campo |

### 10.2 ARIA Labels

```tsx
// Ejemplo de accesibilidad en botón
<Button
  aria-label="Corregir entrega de Pérez, Juan"
  aria-busy={isLoading}
>
  Corregir
</Button>

// Ejemplo de accesibilidad en modal
<Modal
  role="dialog"
  aria-labelledby="modal-title"
  aria-describedby="modal-description"
>
  ...
</Modal>
```

---

## 11. Resumen de Decisiones UI/UX

| Aspecto | Decisión |
|---------|----------|
| **Layout** | Sidebar fijo + contenido principal |
| **Sidebar** | w-64, logo, nav items, footer usuario |
| **Mobile** | Sidebar off-canvas con hamburguesa |
| **Nav Admin** | Dashboard, Materias, Comisiones, Usuarios, Rúbricas |
| **Nav Coordinador** | Dashboard, Comisiones, Rúbricas, Tutores, Supervisión |
| **Nav Tutor** | Dashboard, Entregas, Correcciones, Reportes |
| **Lista entregas** | Tabla con filtros, checkboxes, acciones en línea |
| **Corrección lote** | Botón destacado + checkboxes selección |
| **Detalle corrección** | Modal amplio con campos editables |
| **Tooltips** | Campos, títulos, botones importantes |
| **Temas** | Claro y oscuro con toggle |

---

## 12. Próximos Pasos

Este documento define el diseño UI/UX. Los siguientes documentos detallarán:

- **08-SISTEMA-ESTILOS.md**: Variables CSS, tokens de diseño, componentes base
- **09-API-ENDPOINTS.md**: Definición completa de la API REST

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
