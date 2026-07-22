# 03 - Requisitos Funcionales

> ⚠️ **Sección/spec parcialmente obsoleta:** la integración de IA ya NO usa N8N. La corrección es nativa en el backend (`backend/app/integrations/`: `ia_provider.py` rutea a `gemini_correction_client.py` / `openrouter_client.py`, llamada HTTP directa a Gemini Studio / OpenRouter). Las menciones a N8N a continuación son históricas.

---

## 1. Resumen de Módulos

El sistema se organiza en los siguientes módulos funcionales:

| # | Módulo | Descripción |
|---|--------|-------------|
| 1 | Autenticación | Login, logout, cambio de contraseña, gestión de sesiones |
| 2 | Gestión de Usuarios | CRUD de usuarios, asignación de roles |
| 3 | Gestión de Materias | CRUD de materias, asignación de coordinadores |
| 4 | Gestión de Comisiones | CRUD de comisiones, asignación de tutores |
| 5 | Gestión de Rúbricas | Crear manual, crear desde PDF, editar, duplicar |
| 6 | Gestión de Entregas | Carga individual, carga masiva, consolidación |
| 7 | Corrección Automática | Corrección individual, corrección en lote |
| 8 | Edición de Correcciones | Modificar cualquier campo de la corrección |
| 9 | Generación de Documentos | PDFs de devolución, exportación de notas |
| 10 | Perfil de Usuario | Configuración de API Key Gemini, cambio de contraseña |

---

## 2. Módulo 1: Autenticación

### 2.1 Funcionalidades

| Funcionalidad | Descripción |
|---------------|-------------|
| **Login** | Inicio de sesión con username y contraseña |
| **Validación JWT** | Token JWT firmado con expiración de 7 días (configurable) |
| **Cambio de contraseña obligatorio** | Usuarios nuevos deben cambiar contraseña en primer login |
| **Logout** | Cierre de sesión (invalidación de token en cliente) |

### 2.2 Historias de Usuario

#### HU-AUTH-01: Iniciar Sesión
**Como** usuario registrado
**Quiero** poder iniciar sesión con mis credenciales
**Para** acceder a las funcionalidades según mi rol

**Criterios de Aceptación:**
- Sistema presenta formulario con campos username y contraseña
- Credenciales correctas generan token JWT y redirigen al dashboard correspondiente al rol
- Credenciales incorrectas muestran mensaje genérico "Credenciales inválidas"
- Usuario eliminado (soft delete) recibe mensaje "Cuenta deshabilitada"
- Si es primer login (`primer_login = true`), redirige a cambio de contraseña obligatorio

#### HU-AUTH-02: Cambio de Contraseña Obligatorio
**Como** usuario con contraseña provisional
**Quiero** ser obligado a cambiar mi contraseña en el primer acceso
**Para** garantizar la seguridad de mi cuenta

**Criterios de Aceptación:**
- Modal de cambio de contraseña aparece automáticamente si `primer_login = true`
- Usuario no puede cerrar el modal ni navegar hasta cambiar contraseña
- Requiere: contraseña actual, nueva contraseña (mín. 8 caracteres), confirmación
- Nueva contraseña debe ser diferente a la actual
- Después del cambio exitoso, `primer_login = false` y redirige al dashboard

#### HU-AUTH-03: Cerrar Sesión
**Como** usuario autenticado
**Quiero** poder cerrar mi sesión
**Para** proteger mi cuenta cuando termino de usar el sistema

**Criterios de Aceptación:**
- Botón "Cerrar sesión" visible en el header
- Al cerrar sesión se elimina el token del almacenamiento local
- Redirige a la página de login

---

## 3. Módulo 2: Gestión de Usuarios

### 3.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Listar usuarios** | Ver todos los usuarios del sistema | Admin |
| **Crear usuario** | Crear usuario con username, nombre, rol y contraseña provisional | Admin |
| **Editar usuario** | Modificar nombre, rol | Admin |
| **Eliminar usuario** | Soft delete (marcar como inactivo) | Admin |
| **Restaurar usuario** | Reactivar usuario eliminado | Admin |
| **Resetear contraseña** | Generar nueva contraseña provisional | Admin |

### 3.2 Historias de Usuario

#### HU-USER-01: Crear Usuario
**Como** administrador
**Quiero** crear nuevos usuarios en el sistema
**Para** dar acceso a coordinadores y tutores

**Criterios de Aceptación:**
- Formulario solicita: username (único), nombre completo, rol (Coordinador/Tutor)
- Sistema genera contraseña provisional automática
- `primer_login` se establece en `true`
- Username debe ser único (no puede reutilizar usernames de usuarios eliminados)
- Al crear, muestra la contraseña provisional para comunicarla al usuario

#### HU-USER-02: Listar Usuarios
**Como** administrador
**Quiero** ver la lista de todos los usuarios
**Para** gestionar el acceso al sistema

**Criterios de Aceptación:**
- Tabla con columnas: Nombre, Username, Rol, Estado, Fecha creación
- Filtro por rol (Todos, Admin, Coordinador, Tutor)
- Filtro por estado (Activos, Eliminados, Todos)
- Búsqueda por nombre o username
- Acciones por fila: Editar, Eliminar/Restaurar

---

## 4. Módulo 3: Gestión de Materias

### 4.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Listar materias** | Ver todas las materias activas | Admin |
| **Crear materia** | Crear materia con código y nombre | Admin |
| **Editar materia** | Modificar nombre, descripción | Admin |
| **Eliminar materia** | Soft delete | Admin |
| **Asignar coordinadores** | Asignar uno o más coordinadores a la materia | Admin |

### 4.2 Historias de Usuario

#### HU-MAT-01: Crear Materia
**Como** administrador
**Quiero** crear materias
**Para** organizar la estructura académica

**Criterios de Aceptación:**
- Formulario solicita: código (único, ej: PROG1), nombre completo, descripción (opcional)
- Código debe ser único y en mayúsculas
- Al crear, la materia queda sin coordinadores asignados

#### HU-MAT-02: Asignar Coordinadores a Materia
**Como** administrador
**Quiero** asignar coordinadores a una materia
**Para** delegar la gestión de rúbricas y comisiones

**Criterios de Aceptación:**
- Selector múltiple de coordinadores disponibles
- Una materia puede tener varios coordinadores
- Un coordinador puede estar asignado a varias materias
- Al asignar, se crea registro en tabla `CoordinadorMateria`

---

## 5. Módulo 4: Gestión de Comisiones

### 5.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Listar comisiones** | Ver comisiones de una materia | Admin, Coordinador (sus materias) |
| **Crear comisión** | Crear comisión con nombre y año | Admin, Coordinador (sus materias) |
| **Editar comisión** | Modificar nombre | Admin, Coordinador (sus materias) |
| **Eliminar comisión** | Soft delete | Admin, Coordinador (sus materias) |
| **Asignar tutores** | Asignar uno o más tutores a la comisión | Admin, Coordinador (sus materias) |

### 5.2 Historias de Usuario

#### HU-COM-01: Crear Comisión
**Como** coordinador
**Quiero** crear comisiones para mi materia
**Para** organizar los grupos de alumnos

**Criterios de Aceptación:**
- Selector de materia (solo materias asignadas al coordinador)
- Formulario solicita: nombre (ej: "Comisión A"), año académico (default: año actual)
- Combinación materia + nombre + año debe ser única
- Al crear, la comisión queda sin tutores asignados

#### HU-COM-02: Asignar Tutores a Comisión
**Como** coordinador
**Quiero** asignar tutores a una comisión
**Para** que puedan corregir las entregas

**Criterios de Aceptación:**
- Selector múltiple de tutores disponibles
- Una comisión puede tener varios tutores
- Un tutor puede estar asignado a varias comisiones (incluso de diferentes materias)
- Al asignar, se crea registro en tabla `ComisionTutor`

---

## 6. Módulo 5: Gestión de Rúbricas

### 6.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Listar rúbricas** | Ver rúbricas de una materia | Admin, Coordinador, Tutor (solo sus comisiones) |
| **Crear rúbrica manual** | Definir criterios manualmente | Admin, Coordinador (sus materias) |
| **Crear rúbrica desde PDF** | IA extrae criterios de PDF de consigna | Admin, Coordinador (sus materias) |
| **Editar rúbrica** | Modificar criterios, puntajes | Admin, Coordinador (sus materias) |
| **Duplicar rúbrica** | Copiar rúbrica existente para nuevo año | Admin, Coordinador (sus materias) |
| **Eliminar rúbrica** | Soft delete | Admin, Coordinador (sus materias) |

### 6.2 Tipos de Rúbrica

| Tipo | Código | Descripción |
|------|--------|-------------|
| Trabajo Práctico | `TP` | Trabajos prácticos regulares |
| Parcial 1 | `PARCIAL_1` | Primer examen parcial |
| Parcial 2 | `PARCIAL_2` | Segundo examen parcial |
| Recuperatorio | `RECUPERATORIO` | Examen recuperatorio |
| Final | `FINAL` | Examen final |
| Global | `GLOBAL` | Evaluación global/integradora |

### 6.3 Estructura de una Rúbrica

```json
{
  "nombre": "TP1 - Listas en Python",
  "puntaje_maximo": 100,
  "criterios": [
    {
      "id": "c1",
      "nombre": "Funcionalidad correcta",
      "descripcion": "El programa realiza las operaciones solicitadas",
      "puntaje_maximo": 40,
      "niveles": [
        { "puntaje": 40, "descripcion": "Todas las funciones operan correctamente" },
        { "puntaje": 30, "descripcion": "Funciona con errores menores" },
        { "puntaje": 20, "descripcion": "Funciona parcialmente" },
        { "puntaje": 10, "descripcion": "Errores graves" },
        { "puntaje": 0, "descripcion": "No funciona" }
      ]
    },
    {
      "id": "c2",
      "nombre": "Uso correcto de listas",
      "descripcion": "Implementa operaciones de listas según requerido",
      "puntaje_maximo": 30
    },
    {
      "id": "c3",
      "nombre": "Estilo y legibilidad",
      "descripcion": "Código limpio, bien indentado, nombres descriptivos",
      "puntaje_maximo": 20
    },
    {
      "id": "c4",
      "nombre": "Manejo de errores",
      "descripcion": "Validación de entradas y casos borde",
      "puntaje_maximo": 10
    }
  ]
}
```

### 6.4 Scope de Rúbricas

**Principio fundamental:** Las rúbricas se definen a nivel de **materia** y son compartidas automáticamente por **todas las comisiones** de esa materia en el mismo año académico.

```
MATERIA (Programación 1)
│
├── RÚBRICAS (año 2026)
│   ├── TP1 - Listas
│   ├── TP2 - Funciones
│   ├── Parcial 1
│   └── ...
│
└── COMISIONES (año 2026)
    ├── Comisión A → usa las mismas rúbricas
    └── Comisión B → usa las mismas rúbricas
```

### 6.5 Historias de Usuario

#### HU-RUB-01: Crear Rúbrica Manual
**Como** coordinador
**Quiero** crear una rúbrica definiendo criterios manualmente
**Para** establecer los criterios de evaluación de un TP

**Criterios de Aceptación:**
- Selector de materia (solo sus materias asignadas)
- Formulario solicita: nombre, tipo (TP, Parcial, etc.), número, año
- Editor de criterios:
  - Agregar/eliminar criterios
  - Por cada criterio: nombre, descripción, puntaje máximo
  - Opcionalmente: niveles de logro con puntajes y descripciones
- La suma de puntajes máximos de criterios debe igualar 100
- No puede haber dos rúbricas con mismo tipo y número en la misma materia/año

#### HU-RUB-02: Crear Rúbrica desde PDF
**Como** coordinador
**Quiero** crear una rúbrica subiendo el PDF de la consigna
**Para** que la IA extraiga los criterios automáticamente

**Criterios de Aceptación:**
- Selector de materia, tipo, número, año (igual que manual)
- Campo para subir archivo PDF
- Al subir, el backend llama directo al proveedor de IA (Gemini Studio / OpenRouter) para extracción
- Muestra criterios extraídos para revisión
- Coordinador puede editar criterios antes de confirmar
- Requiere API Key Gemini configurada

#### HU-RUB-03: Duplicar Rúbrica
**Como** coordinador
**Quiero** duplicar una rúbrica del año anterior
**Para** no tener que crearla desde cero cada cuatrimestre

**Criterios de Aceptación:**
- Botón "Duplicar" en rúbrica existente
- Solicita nuevo año y permite cambiar nombre/número
- Copia todos los criterios y estructura
- La nueva rúbrica queda editable

---

## 7. Módulo 6: Gestión de Entregas

### 7.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Listar entregas** | Ver entregas de una comisión/rúbrica | Admin, Coordinador (sus materias), Tutor (sus comisiones) |
| **Carga individual** | Subir entrega de un alumno (ZIP o TXT) | Admin, Coordinador, Tutor |
| **Carga masiva** | Subir ZIP con múltiples entregas | Admin, Coordinador, Tutor |
| **Ver contenido** | Ver código consolidado de una entrega | Admin, Coordinador, Tutor |
| **Eliminar entrega** | Soft delete | Admin, Coordinador, Tutor |

### 7.2 Estados de una Entrega

| Estado | Código | Descripción |
|--------|--------|-------------|
| Subida | `SUBIDA` | Archivo cargado, pendiente de corrección |
| Pendiente | `PENDIENTE` | En proceso de corrección (enviada a IA) |
| Corregida | `CORREGIDA` | Corrección completada |
| Error | `ERROR` | Falló el proceso de corrección |

### 7.3 Modos de Consolidación

Al subir entregas, el usuario puede seleccionar el modo de consolidación:

| Modo | Descripción | Extensiones por defecto |
|------|-------------|------------------------|
| **Solo código** | Solo archivos de código fuente | .py, .java, .js, .ts, .c, .cpp, .go |
| **Web completo** | Código + archivos web | + .html, .css, .json |
| **Proyecto completo** | Todo excepto binarios/media | + .md, .txt, .yml, .xml |
| **Personalizado** | Usuario define extensiones | Selección con tags |

**Extensiones personalizadas:** El usuario puede agregar extensiones adicionales usando un selector de tags (ej: agregar `.sql`, `.sh`).

### 7.4 Estructura de Carga Masiva

```
entregas_tp1.zip
├── perez_juan/
│   └── proyecto.zip (o archivos sueltos)
├── gonzalez_maria/
│   └── proyecto.zip
└── rodriguez_carlos/
    └── proyecto.zip
```

El nombre de la carpeta se usa como nombre del alumno.

### 7.5 Manejo de Duplicados

Al subir entregas, si ya existe una entrega del mismo alumno para la misma rúbrica:

- **Opción "Sobrescribir existentes"** (checkbox en formulario de carga)
- Si está marcado: reemplaza la entrega anterior (soft delete de la anterior)
- Si no está marcado: muestra error para ese alumno, continúa con los demás

### 7.6 Historias de Usuario

#### HU-ENT-01: Carga Individual de Entrega
**Como** tutor
**Quiero** subir la entrega de un alumno
**Para** que quede registrada y lista para corrección

**Criterios de Aceptación:**
- Selector de comisión (solo sus comisiones asignadas)
- Selector de rúbrica (rúbricas de esa materia)
- Campo: nombre del alumno
- Campo: archivo (ZIP o TXT)
- Selector de modo de consolidación (si es ZIP)
- Si es ZIP: sistema extrae, consolida y guarda como TXT
- Entrega queda en estado `SUBIDA`
- Muestra preview de las primeras líneas del código

#### HU-ENT-02: Carga Masiva de Entregas
**Como** tutor
**Quiero** subir un ZIP con todas las entregas de la comisión
**Para** agilizar el proceso de carga

**Criterios de Aceptación:**
- Selector de comisión y rúbrica
- Campo: archivo ZIP con estructura de carpetas por alumno
- Selector de modo de consolidación
- Checkbox: "Sobrescribir entregas existentes"
- Sistema procesa cada carpeta como entrega individual
- Muestra resumen: X exitosas, Y errores
- Errores no detienen el proceso
- Detalle de errores visible al finalizar

#### HU-ENT-03: Ver Contenido de Entrega
**Como** tutor
**Quiero** ver el código de una entrega
**Para** revisarlo antes o después de corregir

**Criterios de Aceptación:**
- En lista de entregas: botón expandible para ver preview (500 chars)
- Modal o página de detalle muestra código completo
- Código con syntax highlighting
- Opción de descargar archivo original

---

## 8. Módulo 7: Corrección Automática

### 8.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Corregir individual** | Enviar una entrega a corrección | Admin, Tutor (sus comisiones) |
| **Corregir en lote** | Corregir todas las pendientes | Admin, Tutor (sus comisiones) |
| **Re-corregir** | Generar nueva corrección descartando la anterior | Admin, Tutor (sus comisiones) |

### 8.2 Flujo de Corrección

```
1. Tutor selecciona entrega(s) a corregir
2. Sistema valida la API Key de IA del tutor
3. El backend (ia_provider.py) rutea según correction_provider y envía directo al proveedor:
   - Contenido consolidado del código
   - Rúbrica con criterios
   (la API Key del tutor se usa para autenticar la llamada HTTP)
4. El proveedor de IA (Gemini Studio / OpenRouter) evalúa con prompt estructurado
5. La IA evalúa según cada criterio y retorna:
   - Nota total (0-100)
   - Evaluación por criterio (puntaje, estado, feedback)
   - Lista de fortalezas
   - Lista de recomendaciones
   - Comentario general pedagógico
6. Sistema almacena la corrección
7. Entrega pasa a estado CORREGIDA
```

### 8.3 Estructura de una Corrección

```json
{
  "nota": 85,
  "criterios": [
    {
      "id": "c1",
      "nombre": "Funcionalidad correcta",
      "puntaje_obtenido": 35,
      "puntaje_maximo": 40,
      "estado": "WARNING",
      "feedback": "Error en el manejo de lista vacía, el resto funciona correctamente"
    },
    {
      "id": "c2",
      "nombre": "Uso correcto de listas",
      "puntaje_obtenido": 30,
      "puntaje_maximo": 30,
      "estado": "OK",
      "feedback": "Excelente uso de list comprehensions y métodos de lista"
    }
  ],
  "fortalezas": [
    "Buen uso de list comprehensions",
    "Código bien organizado y legible",
    "Nombres de variables descriptivos"
  ],
  "recomendaciones": [
    "Agregar validación para listas vacías",
    "Incluir docstrings en las funciones",
    "Considerar manejo de excepciones"
  ],
  "comentario_general": "Buen trabajo en general. El código demuestra comprensión de los conceptos de listas. Las principales áreas de mejora son el manejo de casos borde y la documentación.",
  "respuesta_ia_raw": { ... }
}
```

### 8.4 Estados de Criterio

| Estado | Código | Color | Descripción |
|--------|--------|-------|-------------|
| Cumplido | `OK` | Verde | Criterio cumplido satisfactoriamente |
| Observaciones | `WARNING` | Amarillo | Criterio con observaciones menores |
| Problemas | `ERROR` | Rojo | Criterio con problemas significativos |

### 8.5 Escala de Calificación

- **Rango:** 0 - 100
- **Decimales:** Permitidos (ej: 85.5)
- **Cálculo:** Suma de puntajes de criterios (IA calcula automáticamente)
- **Editable:** Sí, tutor puede ajustar manualmente

### 8.6 Historias de Usuario

#### HU-COR-01: Corrección Individual
**Como** tutor
**Quiero** corregir una entrega específica
**Para** obtener evaluación basada en la rúbrica

**Criterios de Aceptación:**
- Botón "Corregir" visible en entregas con estado `SUBIDA`
- Al hacer clic, entrega pasa a estado `PENDIENTE`
- Sistema valida que tutor tenga API Key Gemini configurada
- Muestra indicador de progreso durante procesamiento
- Al completar, muestra resultado inmediatamente
- Si falla, entrega pasa a estado `ERROR` con mensaje descriptivo
- Tiempo máximo de espera: 60 segundos

#### HU-COR-02: Corrección en Lote
**Como** tutor
**Quiero** corregir todas las entregas pendientes
**Para** procesar la comisión completa eficientemente

**Criterios de Aceptación:**
- Botón "Corregir pendientes" en vista de entregas
- Procesa secuencialmente todas las entregas con estado `SUBIDA`
- Muestra progreso: "12/28 completadas..."
- Errores individuales no detienen el lote
- Al finalizar muestra resumen: exitosas, fallidas
- Detalle de errores visible

#### HU-COR-03: Re-corrección
**Como** tutor
**Quiero** re-corregir una entrega ya corregida
**Para** obtener nueva evaluación (ej: si cambió la rúbrica)

**Criterios de Aceptación:**
- Botón "Re-corregir" visible en entregas con estado `CORREGIDA`
- Muestra confirmación antes de proceder
- Al confirmar, descarta corrección anterior y genera nueva
- Entrega pasa por estados: `PENDIENTE` → `CORREGIDA`

---

## 9. Módulo 8: Edición de Correcciones

### 9.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Ver corrección** | Ver detalle completo de una corrección | Admin, Coordinador (solo lectura), Tutor |
| **Editar corrección** | Modificar cualquier campo | Admin, Tutor (sus comisiones) |

### 9.2 Campos Editables

Todos los campos de la corrección son editables:

| Campo | Descripción |
|-------|-------------|
| **Nota final** | Calificación total (0-100) |
| **Puntaje por criterio** | Ajustar puntaje de cada criterio individual |
| **Feedback por criterio** | Modificar comentario de cada criterio |
| **Estado por criterio** | Cambiar entre OK, WARNING, ERROR |
| **Fortalezas** | Agregar, editar o eliminar items |
| **Recomendaciones** | Agregar, editar o eliminar items |
| **Comentario general** | Feedback global para el alumno |

### 9.3 Comportamiento

- Los cambios se guardan al hacer clic en "Guardar"
- Se marca que la corrección fue "editada manualmente" (para auditoría)
- La nota puede editarse directamente o recalcularse sumando criterios
- Al editar puntajes de criterios, se ofrece botón "Recalcular nota"

### 9.4 Historias de Usuario

#### HU-EDIT-01: Editar Corrección
**Como** tutor
**Quiero** modificar una corrección automática
**Para** ajustar la evaluación según mi criterio profesional

**Criterios de Aceptación:**
- Modal o página de edición con todos los campos
- Nota final editable directamente
- Por cada criterio: puntaje (dropdown o input), estado (selector), feedback (textarea)
- Fortalezas y recomendaciones: lista editable (agregar/eliminar/editar)
- Comentario general: textarea
- Botón "Recalcular nota" suma puntajes de criterios
- Botón "Guardar cambios"
- Botón "Cancelar" descarta cambios
- Al guardar, se marca `editado_manualmente = true`

---

## 10. Módulo 9: Generación de Documentos

### 10.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **PDF individual** | Generar PDF de devolución para una entrega | Admin, Coordinador, Tutor |
| **Descarga masiva PDFs** | Generar ZIP con todos los PDFs de un TP | Admin, Coordinador, Tutor |
| **Exportar notas** | Descargar listado de calificaciones en Excel | Admin, Coordinador, Tutor |

### 10.2 Contenido del PDF de Devolución

```
┌─────────────────────────────────────────────────────────────┐
│                        ACTIVE-IA                             │
│              Devolución de Trabajo Práctico                  │
├─────────────────────────────────────────────────────────────┤
│ Materia: Programación 1                                      │
│ Comisión: Comisión A - 2026                                  │
│ Trabajo: TP1 - Listas en Python                              │
│ Alumno: Pérez, Juan                                          │
│ Fecha de corrección: 15/01/2026                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                    CALIFICACIÓN: 85/100                      │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ EVALUACIÓN POR CRITERIOS                                     │
├─────────────────────────────────────────────────────────────┤
│ ┌─ Funcionalidad correcta ──────────────── 35/40 ⚠ WARNING  │
│ │  Error en el manejo de lista vacía...                     │
│ └────────────────────────────────────────────────────────── │
│ ┌─ Uso correcto de listas ──────────────── 30/30 ✓ OK      │
│ │  Excelente uso de list comprehensions...                  │
│ └────────────────────────────────────────────────────────── │
│ ...                                                          │
├─────────────────────────────────────────────────────────────┤
│ FORTALEZAS                                                   │
│ • Buen uso de list comprehensions                            │
│ • Código bien organizado y legible                           │
├─────────────────────────────────────────────────────────────┤
│ RECOMENDACIONES                                              │
│ 1. Agregar validación para listas vacías                     │
│ 2. Incluir docstrings en las funciones                       │
├─────────────────────────────────────────────────────────────┤
│ COMENTARIOS DEL EVALUADOR                                    │
│ Buen trabajo en general. El código demuestra comprensión...  │
└─────────────────────────────────────────────────────────────┘
```

### 10.3 Indicadores Visuales en PDF

| Estado | Icono | Color |
|--------|-------|-------|
| OK | ✓ | Verde (#16a34a) |
| WARNING | ⚠ | Amarillo (#ca8a04) |
| ERROR | ✗ | Rojo (#dc2626) |

### 10.4 Formato de Exportación de Notas

**Formato:** Excel (.xlsx)

**Columnas:**
| Columna | Descripción |
|---------|-------------|
| Alumno | Nombre del alumno |
| Nota | Calificación (0-100) |
| Estado | CORREGIDA, PENDIENTE, ERROR |
| Fecha | Fecha de corrección |
| Editado | Sí/No (si fue editado manualmente) |

### 10.5 Historias de Usuario

#### HU-DOC-01: Generar PDF Individual
**Como** tutor
**Quiero** generar el PDF de devolución de una entrega
**Para** entregar retroalimentación profesional al alumno

**Criterios de Aceptación:**
- Botón "Descargar PDF" visible en entregas con estado `CORREGIDA`
- PDF se genera en menos de 5 segundos
- Nombre del archivo: `{alumno}_devolucion_{fecha}.pdf`
- PDF incluye todos los datos especificados arriba

#### HU-DOC-02: Descarga Masiva de PDFs
**Como** tutor
**Quiero** descargar todos los PDFs de un TP
**Para** distribuirlos eficientemente a los alumnos

**Criterios de Aceptación:**
- Botón "Descargar todos los PDFs" en vista de entregas
- Genera ZIP con un PDF por cada entrega corregida
- Solo incluye entregas con estado `CORREGIDA`
- Nombre del ZIP: `devoluciones_{materia}_{tp}_{fecha}.zip`
- Nombre de cada PDF: `{alumno}_devolucion.pdf`

#### HU-DOC-03: Exportar Notas a Excel
**Como** tutor
**Quiero** exportar las notas a Excel
**Para** registrarlas en el sistema institucional

**Criterios de Aceptación:**
- Botón "Exportar notas" en vista de entregas
- Genera archivo Excel (.xlsx)
- Incluye todas las entregas (corregidas y pendientes)
- Nombre del archivo: `notas_{materia}_{tp}_{fecha}.xlsx`

---

## 11. Módulo 10: Perfil de Usuario

### 11.1 Funcionalidades

| Funcionalidad | Descripción | Acceso |
|---------------|-------------|--------|
| **Ver perfil** | Ver datos del usuario actual | Todos |
| **Cambiar contraseña** | Actualizar contraseña | Todos |
| **Configurar API Key** | Configurar API Key de Gemini | Admin, Coordinador, Tutor |

### 11.2 Historias de Usuario

#### HU-PERF-01: Configurar API Key Gemini
**Como** tutor
**Quiero** configurar mi API Key de Google Gemini
**Para** poder usar la corrección automática

**Criterios de Aceptación:**
- Sección "API Key de Google Gemini" en perfil
- Si no configurada: muestra "No configurada" y botón "Configurar"
- Si configurada: muestra "****XXXX" (últimos 4 dígitos) y botón "Cambiar"
- Modal solicita API Key (campo tipo password)
- Link a documentación "¿Cómo obtener una API Key?"
- Al guardar:
  - Valida formato (debe empezar con "AIza")
  - Realiza llamada de prueba a Gemini
  - Si válida: encripta con Fernet (AES-128-CBC + HMAC-SHA256) y guarda
  - Si inválida: muestra error, no guarda
- Mensaje de confirmación al guardar exitosamente

#### HU-PERF-02: Cambiar Contraseña
**Como** usuario
**Quiero** cambiar mi contraseña
**Para** mantener mi cuenta segura

**Criterios de Aceptación:**
- Sección "Cambiar contraseña" en perfil
- Campos: contraseña actual, nueva contraseña, confirmar nueva
- Nueva contraseña: mínimo 8 caracteres
- Nueva contraseña debe ser diferente a la actual
- Al guardar exitosamente, muestra mensaje de confirmación

---

## 12. Resumen de Decisiones de Requisitos

| Aspecto | Decisión |
|---------|----------|
| **Escala de notas** | 0-100 |
| **Datos de corrección** | Completa (nota, criterios, fortalezas, recomendaciones, comentario) |
| **Tipos de rúbrica** | TP, Parcial 1, Parcial 2, Recuperatorio, Final, Global |
| **Exportación de notas** | Excel (.xlsx) |
| **Campos editables en corrección** | Todos |
| **Identificación de alumno** | Solo nombre (extraído de carpeta en carga masiva) |
| **Modos de consolidación** | Mantener modos + extensiones personalizadas con tags |
| **Scope de rúbricas** | A nivel materia (compartida por todas las comisiones del año) |
| **Indicadores de criterio** | 3 estados: OK, WARNING, ERROR |
| **Preview de código** | Opcional, expandible en lista de entregas |
| **Manejo de duplicados** | Opción "Sobrescribir existentes" al subir |
| **Cálculo de nota** | IA asigna automáticamente, tutor puede editar todo |

---

## 13. Próximos Pasos

Este documento define los requisitos funcionales del sistema. Los siguientes documentos detallarán:

- **04-REQUISITOS-NO-FUNCIONALES.md**: Rendimiento, seguridad, escalabilidad
- **05-ARQUITECTURA-STACK.md**: Tecnologías, justificación, diagramas

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
