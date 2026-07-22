# 02 - Usuarios y Roles

---

## 1. Resumen de Roles

El sistema tiene **3 roles** con responsabilidades claramente diferenciadas:

| Rol | Responsabilidad Principal | Puede Corregir |
|-----|---------------------------|:--------------:|
| **Administrador** | Gestionar todo el sistema | Sí (opcional) |
| **Coordinador** | Gestionar rúbricas y comisiones de sus materias | No |
| **Tutor** | Corregir entregas de sus comisiones | Sí |

---

## 2. User Personas

### 2.1 Persona: Administrador

| Atributo | Descripción |
|----------|-------------|
| **Nombre representativo** | Laura - Directora de Carrera |
| **Edad** | 48 años |
| **Perfil profesional** | Directora de la Tecnicatura en Programación. 15 años de experiencia en gestión académica universitaria. Competencia tecnológica intermedia. |
| **Responsabilidades** | Definir estructura académica (materias). Crear y gestionar usuarios. Asignar coordinadores a materias. Supervisar el funcionamiento general. Intervenir en casos excepcionales. |
| **Frustraciones actuales** | Falta de visibilidad sobre el estado de correcciones. Quejas de estudiantes por demoras. Dificultad para estandarizar criterios entre tutores. Tiempo excesivo en tareas administrativas. |
| **Objetivos con el sistema** | Configurar la estructura académica de forma simple. Delegar gestión de rúbricas a coordinadores. Tener visibilidad del estado general. Poder intervenir si es necesario. |
| **Frecuencia de uso** | Inicio de cuatrimestre (configuración intensiva), luego esporádico (supervisión) |
| **Dispositivo principal** | Desktop/Laptop |

**Cita representativa:**
> "Necesito poder ver de un vistazo cómo van las correcciones de todas las materias, sin tener que preguntar a cada coordinador."

---

### 2.2 Persona: Coordinador

| Atributo | Descripción |
|----------|-------------|
| **Nombre representativo** | María - Coordinadora de Programación 1 y 2 |
| **Edad** | 42 años |
| **Perfil profesional** | Ingeniera en Sistemas con 12 años de experiencia docente. Coordina las materias iniciales de programación. Competencia tecnológica alta. |
| **Responsabilidades** | Crear y mantener rúbricas de evaluación. Crear comisiones cada cuatrimestre. Asignar tutores a comisiones. Supervisar que los tutores corrijan a tiempo. Garantizar consistencia en evaluaciones. |
| **Frustraciones actuales** | **Falta de visibilidad:** No sabe cuántas entregas faltan corregir ni cómo van los tutores. **Inconsistencia:** Cada tutor evalúa diferente, no hay criterios unificados. **Carga administrativa:** Mucho tiempo creando rúbricas desde cero cada cuatrimestre. |
| **Objetivos con el sistema** | Crear rúbricas una vez y reutilizarlas. Ver el estado de correcciones de todos los tutores. Garantizar que todos usen los mismos criterios. Reducir trabajo administrativo repetitivo. |
| **Frecuencia de uso** | Semanal (revisión de estado), intensivo al inicio de cada TP |
| **Dispositivo principal** | Desktop/Laptop |

**Cita representativa:**
> "Quiero crear la rúbrica del TP1 una vez y que todos los tutores la usen igual. Y poder ver quién ya corrigió y quién está atrasado."

---

### 2.3 Persona: Tutor

| Atributo | Descripción |
|----------|-------------|
| **Nombre representativo** | Carlos - Tutor de Programación 1 |
| **Edad** | 24 años |
| **Perfil profesional** | Estudiante avanzado de Ingeniería en Sistemas (4to año). Trabaja como tutor part-time mientras termina la carrera. Alta competencia técnica. Maneja 1-2 comisiones. |
| **Responsabilidades** | Corregir trabajos prácticos de sus comisiones. Proporcionar retroalimentación a estudiantes. Identificar alumnos con dificultades. Entregar notas a tiempo. |
| **Frustraciones actuales** | **Tiempo de corrección:** Dedica 20-30 minutos por entrega en tareas repetitivas. **Feedback genérico:** La presión de tiempo lo obliga a dar comentarios breves. **Detectar copias:** Imposible revisar similitudes entre 30 entregas manualmente. **Competencia con estudios:** El tiempo de corrección compite con sus propias materias. |
| **Objetivos con el sistema** | Reducir tiempo de corrección a menos de 5 minutos por entrega. Obtener evaluación automática que pueda ajustar. Generar PDFs de devolución profesionales sin esfuerzo. Tener más tiempo para sus estudios. |
| **Frecuencia de uso** | Intensivo después de cada fecha de entrega de TP |
| **Dispositivo principal** | Laptop |
| **Comisiones típicas** | 1-2 (puede tener más en casos excepcionales) |

**Cita representativa:**
> "Si la IA me da una corrección base que puedo revisar y ajustar, me ahorro horas. Y puedo dar mejor feedback a los alumnos."

---

## 3. Datos del Usuario

### 3.1 Campos del Modelo de Usuario

| Campo | Tipo | Requerido | Descripción |
|-------|------|:---------:|-------------|
| `id` | UUID/Serial | Sí | Identificador único |
| `username` | String | Sí | Nombre de usuario para login (único, lowercase, sin espacios) |
| `nombre` | String | Sí | Nombre completo para mostrar |
| `password` | String | Sí | Contraseña hasheada (bcrypt) |
| `rol` | Enum | Sí | 'ADMIN', 'COORDINADOR', 'TUTOR' |
| `primer_login` | Boolean | Sí | True si debe cambiar contraseña en próximo login |
| `gemini_api_key_encrypted` | String | No | API Key de IA encriptada con Fernet (AES-128-CBC + HMAC-SHA256) |
| `gemini_api_key_valid` | Boolean | No | Flag de validación de la API Key |
| `activo` | Boolean | Sí | False = eliminado (soft delete) |
| `created_at` | Timestamp | Sí | Fecha de creación |
| `updated_at` | Timestamp | Sí | Fecha de última modificación |

### 3.2 Validaciones

| Campo | Validación |
|-------|------------|
| `username` | Mínimo 3 caracteres. Solo letras, números, guiones y guiones bajos. Único en el sistema. |
| `nombre` | Mínimo 2 caracteres. |
| `password` | Mínimo 8 caracteres. Hash bcrypt con salt factor 10. |
| `gemini_api_key` | Debe empezar con "AIza". Se valida con llamada de prueba antes de guardar. |

### 3.3 Contraseña Provisional

Cuando el Admin crea un usuario:
1. Se asigna una contraseña provisional
2. `primer_login` se establece en `true`
3. Al hacer login, si `primer_login` es `true`:
   - Se fuerza cambio de contraseña
   - El usuario no puede navegar hasta cambiarla
   - Después del cambio, `primer_login` pasa a `false`

---

## 4. Definición Detallada de Roles

### 4.1 Administrador (ADMIN)

**Descripción:** Usuario con acceso total al sistema. Gestiona la estructura académica y los usuarios.

**Características:**
- Solo puede existir uno o pocos administradores
- No requiere asignación a materias ni comisiones
- Puede acceder a cualquier parte del sistema
- Su trabajo principal es gestión, no corrección

#### Permisos del Administrador

| Módulo | Acción | Permitido |
|--------|--------|:---------:|
| **Usuarios** | Crear usuarios (cualquier rol) | ✓ |
| **Usuarios** | Editar usuarios | ✓ |
| **Usuarios** | Eliminar usuarios (soft delete) | ✓ |
| **Usuarios** | Restaurar usuarios eliminados | ✓ |
| **Usuarios** | Ver todos los usuarios | ✓ |
| **Materias** | Crear materias | ✓ |
| **Materias** | Editar materias | ✓ |
| **Materias** | Eliminar materias | ✓ |
| **Materias** | Asignar coordinadores a materias | ✓ |
| **Comisiones** | Crear comisiones | ✓ |
| **Comisiones** | Editar comisiones | ✓ |
| **Comisiones** | Eliminar comisiones | ✓ |
| **Comisiones** | Asignar tutores a comisiones | ✓ |
| **Comisiones** | Ver todas las comisiones | ✓ |
| **Rúbricas** | Crear rúbricas | ✓ |
| **Rúbricas** | Editar rúbricas | ✓ |
| **Rúbricas** | Eliminar rúbricas | ✓ |
| **Entregas** | Ver entregas de cualquier comisión | ✓ |
| **Entregas** | Subir entregas | ✓ |
| **Corrección** | Corregir entregas (opcional) | ✓ |
| **Corrección** | Editar correcciones | ✓ |
| **Corrección** | Ver correcciones de cualquier tutor | ✓ |
| **Documentos** | Descargar PDFs | ✓ |
| **Documentos** | Exportar notas | ✓ |
| **Perfil** | Configurar su API Key Gemini | ✓ |

---

### 4.2 Coordinador (COORDINADOR)

**Descripción:** Usuario que gestiona rúbricas y comisiones de las materias que tiene asignadas. Supervisa el trabajo de los tutores pero NO corrige.

**Características:**
- Asignado a una o más materias por el Admin (relación N:M)
- Una materia puede tener uno o más coordinadores
- Solo ve y gestiona lo relacionado a sus materias asignadas
- Necesita API Key Gemini para generar rúbricas desde PDF

#### Asignación de Materias

```
Coordinador ←──── N:M ────→ Materia
```

- El Admin asigna materias al Coordinador
- Un Coordinador puede tener múltiples materias
- Una Materia puede tener múltiples Coordinadores
- Se requiere tabla intermedia: `CoordinadorMateria`

#### Permisos del Coordinador

| Módulo | Acción | Permitido | Restricción |
|--------|--------|:---------:|-------------|
| **Usuarios** | Ver usuarios | ✗ | - |
| **Usuarios** | Gestionar usuarios | ✗ | - |
| **Materias** | Ver materias | ✓ | Solo sus materias asignadas |
| **Materias** | Gestionar materias | ✗ | - |
| **Comisiones** | Crear comisiones | ✓ | Solo en sus materias |
| **Comisiones** | Editar comisiones | ✓ | Solo en sus materias |
| **Comisiones** | Eliminar comisiones | ✓ | Solo en sus materias |
| **Comisiones** | Asignar tutores | ✓ | Solo en sus materias |
| **Comisiones** | Ver comisiones | ✓ | Solo de sus materias |
| **Rúbricas** | Crear rúbricas | ✓ | Solo en sus materias |
| **Rúbricas** | Crear desde PDF | ✓ | Solo en sus materias |
| **Rúbricas** | Editar rúbricas | ✓ | Solo en sus materias |
| **Rúbricas** | Eliminar rúbricas | ✓ | Solo en sus materias |
| **Rúbricas** | Duplicar rúbricas | ✓ | Solo en sus materias |
| **Entregas** | Ver entregas | ✓ | Solo de sus materias |
| **Entregas** | Subir entregas | ✓ | Solo en sus materias |
| **Corrección** | Corregir entregas | ✗ | No corrige |
| **Corrección** | Editar correcciones | ✗ | No edita |
| **Corrección** | Ver correcciones de tutores | ✓ | Solo de sus materias |
| **Documentos** | Descargar PDFs | ✓ | Solo de sus materias |
| **Documentos** | Exportar notas | ✓ | Solo de sus materias |
| **Perfil** | Configurar su API Key Gemini | ✓ | Necesaria para rúbricas desde PDF |

---

### 4.3 Tutor (TUTOR)

**Descripción:** Usuario que corrige las entregas de las comisiones que tiene asignadas.

**Características:**
- Asignado a una o más comisiones por Admin o Coordinador
- Puede tener comisiones de diferentes materias (sin límite)
- Típicamente maneja 1-2 comisiones (puede ser más)
- Necesita API Key Gemini para corregir

#### Asignación de Comisiones

```
Tutor ←──── N:M ────→ Comisión
```

- Admin o Coordinador asigna comisiones al Tutor
- Un Tutor puede tener múltiples comisiones (incluso de diferentes materias)
- Una Comisión puede tener múltiples Tutores
- Se usa tabla existente: `ComisionTutor`

#### Permisos del Tutor

| Módulo | Acción | Permitido | Restricción |
|--------|--------|:---------:|-------------|
| **Usuarios** | Ver/Gestionar usuarios | ✗ | - |
| **Materias** | Ver/Gestionar materias | ✗ | - |
| **Comisiones** | Ver comisiones | ✓ | Solo sus comisiones asignadas |
| **Comisiones** | Gestionar comisiones | ✗ | - |
| **Rúbricas** | Ver rúbricas | ✓ | Solo de sus comisiones |
| **Rúbricas** | Gestionar rúbricas | ✗ | - |
| **Entregas** | Ver entregas | ✓ | Solo de sus comisiones |
| **Entregas** | Subir entregas | ✓ | Solo en sus comisiones |
| **Entregas** | Eliminar entregas | ✓ | Solo en sus comisiones |
| **Corrección** | Corregir con IA | ✓ | Solo en sus comisiones |
| **Corrección** | Corregir en lote | ✓ | Solo en sus comisiones |
| **Corrección** | Editar correcciones | ✓ | Solo las de sus comisiones |
| **Corrección** | Re-corregir | ✓ | Solo en sus comisiones |
| **Corrección** | Ver correcciones de otros | ✗ | Solo las propias |
| **Documentos** | Descargar PDFs | ✓ | Solo de sus comisiones |
| **Documentos** | Descarga masiva PDFs | ✓ | Solo de sus comisiones |
| **Documentos** | Exportar notas | ✓ | Solo de sus comisiones |
| **Perfil** | Configurar su API Key Gemini | ✓ | Obligatoria para corregir |

---

## 5. Matriz de Permisos Consolidada

### 5.1 Gestión de Entidades

| Acción | Admin | Coordinador | Tutor |
|--------|:-----:|:-----------:|:-----:|
| **Crear usuarios** | ✓ | - | - |
| **Editar usuarios** | ✓ | - | - |
| **Eliminar usuarios** | ✓ | - | - |
| **Crear materias** | ✓ | - | - |
| **Editar materias** | ✓ | - | - |
| **Asignar coordinadores** | ✓ | - | - |
| **Crear comisiones** | ✓ | ✓ (sus materias) | - |
| **Editar comisiones** | ✓ | ✓ (sus materias) | - |
| **Asignar tutores** | ✓ | ✓ (sus materias) | - |
| **Crear rúbricas** | ✓ | ✓ (sus materias) | - |
| **Crear rúbricas desde PDF** | ✓ | ✓ (sus materias) | - |
| **Editar rúbricas** | ✓ | ✓ (sus materias) | - |

### 5.2 Operaciones de Corrección

| Acción | Admin | Coordinador | Tutor |
|--------|:-----:|:-----------:|:-----:|
| **Subir entregas** | ✓ | ✓ (sus materias) | ✓ (sus comisiones) |
| **Corregir con IA** | ✓ | - | ✓ (sus comisiones) |
| **Corregir en lote** | ✓ | - | ✓ (sus comisiones) |
| **Editar corrección** | ✓ | - | ✓ (sus comisiones) |
| **Re-corregir** | ✓ | - | ✓ (sus comisiones) |
| **Ver correcciones** | ✓ (todas) | ✓ (sus materias) | ✓ (sus comisiones) |

### 5.3 Documentos y Exportación

| Acción | Admin | Coordinador | Tutor |
|--------|:-----:|:-----------:|:-----:|
| **Ver PDF individual** | ✓ | ✓ (sus materias) | ✓ (sus comisiones) |
| **Descargar PDF** | ✓ | ✓ (sus materias) | ✓ (sus comisiones) |
| **Descarga masiva PDFs** | ✓ | ✓ (sus materias) | ✓ (sus comisiones) |
| **Exportar notas CSV/Excel** | ✓ | ✓ (sus materias) | ✓ (sus comisiones) |

---

## 6. Flujos de Usuario

### 6.1 Flujo: Primer Login (Todos los Roles)

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRIMER LOGIN                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Usuario recibe credenciales provisionales                    │
│     (username + contraseña temporal)                             │
│                         │                                        │
│                         ▼                                        │
│  2. Usuario ingresa credenciales en /login                       │
│                         │                                        │
│                         ▼                                        │
│  3. Sistema detecta primer_login = true                          │
│                         │                                        │
│                         ▼                                        │
│  4. Redirige a modal de cambio de contraseña obligatorio         │
│     - No puede cerrar el modal                                   │
│     - No puede navegar a otra página                             │
│                         │                                        │
│                         ▼                                        │
│  5. Usuario ingresa:                                             │
│     - Contraseña actual (la provisional)                         │
│     - Nueva contraseña (mín. 8 caracteres)                       │
│     - Confirmar nueva contraseña                                 │
│                         │                                        │
│                         ▼                                        │
│  6. Sistema valida y actualiza:                                  │
│     - password = hash(nueva)                                     │
│     - primer_login = false                                       │
│                         │                                        │
│                         ▼                                        │
│  7. Redirige al dashboard según rol                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 6.2 Flujo: Configuración de API Key Gemini

```
┌─────────────────────────────────────────────────────────────────┐
│                CONFIGURAR API KEY GEMINI                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Usuario accede a /perfil                                     │
│                         │                                        │
│                         ▼                                        │
│  2. Sección "API Key de Google Gemini"                           │
│     - Si no configurada: "No configurada"                        │
│     - Si configurada: "****XXXX" (últimos 4 dígitos)             │
│                         │                                        │
│                         ▼                                        │
│  3. Usuario hace clic en "Configurar" o "Cambiar"                │
│                         │                                        │
│                         ▼                                        │
│  4. Modal solicita:                                              │
│     - API Key completa (campo password)                          │
│     - Link a "¿Cómo obtener una API Key?"                        │
│                         │                                        │
│                         ▼                                        │
│  5. Usuario ingresa API Key y confirma                           │
│                         │                                        │
│                         ▼                                        │
│  6. Sistema valida:                                              │
│     a. Formato (debe empezar con "AIza")                         │
│     b. Llamada de prueba a Gemini                                │
│                         │                                        │
│              ┌─────────┴─────────┐                               │
│              ▼                   ▼                                │
│         Válida              Inválida                             │
│              │                   │                                │
│              ▼                   ▼                                │
│     - Encripta con Fernet       - Muestra error                  │
│     - Guarda en BD              - No guarda                      │
│     - gemini_api_key_valid=true - Pide reintentar                │
│     - Muestra confirmación                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Cuándo se requiere API Key:**

| Rol | Acción que requiere API Key |
|-----|----------------------------|
| **Admin** | Corregir entregas (si decide hacerlo) |
| **Coordinador** | Crear rúbrica desde PDF |
| **Tutor** | Corregir entregas (obligatorio) |

---

### 6.3 Flujo: Administrador - Configuración Inicial

```
┌─────────────────────────────────────────────────────────────────┐
│           CONFIGURACIÓN INICIAL DEL SISTEMA (ADMIN)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PASO 1: Crear Materias                                          │
│  ────────────────────────                                        │
│  Admin accede a /admin/materias                                  │
│  → Crear: Programación 1 (PROG1)                                 │
│  → Crear: Programación 2 (PROG2)                                 │
│  → Crear: Programación 3 (PROG3)                                 │
│  → Crear: Programación 4 (PROG4)                                 │
│                         │                                        │
│                         ▼                                        │
│  PASO 2: Crear Usuarios Coordinadores                            │
│  ────────────────────────────────────                            │
│  Admin accede a /admin/usuarios                                  │
│  → Crear coordinador: María (rol: COORDINADOR)                   │
│  → Sistema genera contraseña provisional                         │
│  → Admin comunica credenciales a María                           │
│                         │                                        │
│                         ▼                                        │
│  PASO 3: Asignar Materias a Coordinadores                        │
│  ────────────────────────────────────────                        │
│  Admin accede a /admin/materias                                  │
│  → Selecciona PROG1 → Asignar coordinador → María                │
│  → Selecciona PROG2 → Asignar coordinador → María                │
│  (María ahora coordina PROG1 y PROG2)                            │
│                         │                                        │
│                         ▼                                        │
│  PASO 4: Crear Usuarios Tutores                                  │
│  ──────────────────────────                                      │
│  Admin accede a /admin/usuarios                                  │
│  → Crear tutor: Carlos (rol: TUTOR)                              │
│  → Crear tutor: Ana (rol: TUTOR)                                 │
│  → Sistema genera contraseñas provisionales                      │
│                         │                                        │
│                         ▼                                        │
│  PASO 5: (Opcional) Crear Comisiones                             │
│  ───────────────────────────────────                             │
│  Admin puede crear comisiones o delegar a Coordinador            │
│                                                                  │
│  ════════════════════════════════════════════════════════════    │
│  RESULTADO: Sistema configurado, listo para que Coordinadores    │
│             creen comisiones y rúbricas                          │
│  ════════════════════════════════════════════════════════════    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 6.4 Flujo: Coordinador - Preparar Cuatrimestre

```
┌─────────────────────────────────────────────────────────────────┐
│          PREPARAR CUATRIMESTRE (COORDINADOR)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PASO 1: Crear Comisiones del Año                                │
│  ────────────────────────────────                                │
│  Coordinador accede a su materia (ej: PROG1)                     │
│  → Crear comisión: "Comisión A - 2026"                           │
│  → Crear comisión: "Comisión B - 2026"                           │
│                         │                                        │
│                         ▼                                        │
│  PASO 2: Asignar Tutores a Comisiones                            │
│  ────────────────────────────────────                            │
│  Coordinador selecciona "Comisión A"                             │
│  → Asignar tutor: Carlos                                         │
│  Coordinador selecciona "Comisión B"                             │
│  → Asignar tutor: Ana                                            │
│                         │                                        │
│                         ▼                                        │
│  PASO 3: Crear/Duplicar Rúbricas                                 │
│  ───────────────────────────────                                 │
│  Coordinador accede a /rubricas de su materia                    │
│                                                                  │
│  Opción A: Duplicar del año anterior                             │
│  → Selecciona "TP1 - Listas (2025)"                              │
│  → Duplicar para 2026                                            │
│  → Ajustar criterios si necesario                                │
│                                                                  │
│  Opción B: Crear desde PDF                                       │
│  → Subir PDF de consigna del TP                                  │
│  → IA extrae criterios automáticamente                           │
│  → Revisar y ajustar criterios                                   │
│  → Confirmar rúbrica                                             │
│                                                                  │
│  Opción C: Crear manual                                          │
│  → Definir nombre, tipo (TP, Parcial, etc.)                      │
│  → Agregar criterios uno a uno                                   │
│  → Definir niveles de logro por criterio                         │
│                         │                                        │
│                         ▼                                        │
│  PASO 4: Verificar Configuración                                 │
│  ───────────────────────────────                                 │
│  Coordinador ve resumen:                                         │
│  - 2 comisiones creadas                                          │
│  - 2 tutores asignados                                           │
│  - 6 rúbricas listas (TP1-TP6)                                   │
│                                                                  │
│  ════════════════════════════════════════════════════════════    │
│  RESULTADO: Materia lista para que tutores suban y corrijan      │
│  ════════════════════════════════════════════════════════════    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 6.5 Flujo: Tutor - Ciclo Completo de Corrección

```
┌─────────────────────────────────────────────────────────────────┐
│            CICLO DE CORRECCIÓN (TUTOR)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PASO 1: Ver Comisiones Asignadas                                │
│  ────────────────────────────────                                │
│  Tutor accede a /tutor (su dashboard)                            │
│  Ve tarjetas de sus comisiones:                                  │
│  ┌─────────────────────┐                                         │
│  │ PROG1 - Comisión A  │                                         │
│  │ 28 entregas         │                                         │
│  │ 0 pendientes        │                                         │
│  └─────────────────────┘                                         │
│                         │                                        │
│                         ▼                                        │
│  PASO 2: Seleccionar Comisión y TP                               │
│  ─────────────────────────────────                               │
│  Tutor hace clic en "Comisión A"                                 │
│  → Ve selector de rúbricas (TPs)                                 │
│  → Selecciona "TP1 - Listas"                                     │
│                         │                                        │
│                         ▼                                        │
│  PASO 3: Subir Entregas                                          │
│  ──────────────────────                                          │
│  Opción A: Carga masiva                                          │
│  → Clic en "Subir entregas"                                      │
│  → Selecciona ZIP con estructura de carpetas por alumno          │
│  → Sistema procesa y muestra resumen                             │
│     "28 entregas procesadas, 2 errores"                          │
│                                                                  │
│  Opción B: Carga individual                                      │
│  → Clic en "Subir entrega"                                       │
│  → Ingresa nombre del alumno                                     │
│  → Selecciona archivo ZIP o TXT                                  │
│                         │                                        │
│                         ▼                                        │
│  PASO 4: Corregir                                                │
│  ────────────────────                                            │
│  Opción A: Corregir en lote                                      │
│  → Clic en "Corregir pendientes"                                 │
│  → Sistema procesa secuencialmente                               │
│  → Muestra progreso: "12/28 completadas..."                      │
│  → Al terminar: resumen de éxitos/errores                        │
│                                                                  │
│  Opción B: Corregir individual                                   │
│  → Clic en botón "Corregir" de una entrega                       │
│  → Espera ~30-60 segundos                                        │
│  → Ve resultado inmediatamente                                   │
│                         │                                        │
│                         ▼                                        │
│  PASO 5: Revisar y Ajustar                                       │
│  ─────────────────────────                                       │
│  Tutor ordena por nota (más bajas primero)                       │
│  → Revisa correcciones sospechosas                               │
│  → Abre modal de edición                                         │
│  → Ajusta nota, feedback, fortalezas si necesario                │
│  → Guarda cambios                                                │
│                         │                                        │
│                         ▼                                        │
│  PASO 6: Generar Devoluciones                                    │
│  ────────────────────────────                                    │
│  → Clic en "Descargar todos los PDFs"                            │
│  → Sistema genera ZIP con 28 PDFs                                │
│  → Tutor distribuye PDFs a alumnos                               │
│                         │                                        │
│                         ▼                                        │
│  PASO 7: Exportar Notas                                          │
│  ─────────────────────────                                       │
│  → Clic en "Exportar notas"                                      │
│  → Descarga CSV/Excel con listado                                │
│  → Carga en sistema institucional                                │
│                                                                  │
│  ════════════════════════════════════════════════════════════    │
│  RESULTADO: TP corregido en ~30 minutos de trabajo activo        │
│  ════════════════════════════════════════════════════════════    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 6.6 Flujo: Coordinador - Supervisar Correcciones

```
┌─────────────────────────────────────────────────────────────────┐
│         SUPERVISAR CORRECCIONES (COORDINADOR)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Coordinador accede a su materia                              │
│                         │                                        │
│                         ▼                                        │
│  2. Ve panel de estado por comisión:                             │
│                                                                  │
│     ┌─────────────────────────────────────────────┐              │
│     │ PROG1 - Estado de Correcciones - TP1        │              │
│     ├─────────────────────────────────────────────┤              │
│     │ Comisión A (Carlos)                         │              │
│     │ ████████████████░░░░ 28/35 (80%)           │              │
│     │ Última actividad: hace 2 horas              │              │
│     ├─────────────────────────────────────────────┤              │
│     │ Comisión B (Ana)                            │              │
│     │ ████████████████████ 30/30 (100%)          │              │
│     │ Completado: 15/01/2026                      │              │
│     └─────────────────────────────────────────────┘              │
│                         │                                        │
│                         ▼                                        │
│  3. Coordinador puede:                                           │
│     - Ver detalle de correcciones (solo lectura)                 │
│     - Ver distribución de notas                                  │
│     - Descargar PDFs para revisión                               │
│     - Exportar notas consolidadas                                │
│                                                                  │
│  4. Si detecta inconsistencias:                                  │
│     - Contacta al tutor para que revise                          │
│     - NO puede editar correcciones directamente                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Relaciones Entre Entidades

### 7.1 Diagrama de Relaciones Usuario-Materia-Comisión

```
┌─────────────┐
│   Usuario   │
├─────────────┤
│ id          │
│ username    │
│ nombre      │
│ rol         │
│ ...         │
└──────┬──────┘
       │
       │ Si rol = COORDINADOR
       │
       ▼
┌──────────────────────┐         ┌─────────────┐
│ CoordinadorMateria   │         │   Materia   │
├──────────────────────┤         ├─────────────┤
│ coordinador_id (FK)  │────────→│ id          │
│ materia_id (FK)      │         │ codigo      │
│ asignado_en          │         │ nombre      │
└──────────────────────┘         └──────┬──────┘
                                        │
       │ Si rol = TUTOR                 │ 1:N
       │                                ▼
       ▼                         ┌─────────────┐
┌──────────────────────┐         │  Comision   │
│   ComisionTutor      │         ├─────────────┤
├──────────────────────┤         │ id          │
│ tutor_id (FK)        │────────→│ materia_id  │
│ comision_id (FK)     │         │ nombre      │
│ asignado_en          │         │ anio        │
└──────────────────────┘         └─────────────┘
```

### 7.2 Tabla: CoordinadorMateria (Nueva)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Serial PK | Identificador único |
| `coordinador_id` | FK Usuario | Referencia al coordinador |
| `materia_id` | FK Materia | Referencia a la materia |
| `asignado_en` | Timestamp | Fecha de asignación |

**Índice único:** (coordinador_id, materia_id)

### 7.3 Tabla: ComisionTutor (Existente)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | Serial PK | Identificador único |
| `tutor_id` | FK Usuario | Referencia al tutor |
| `comision_id` | FK Comision | Referencia a la comisión |
| `asignado_en` | Timestamp | Fecha de asignación |

**Índice único:** (tutor_id, comision_id)

---

## 8. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Cantidad de roles** | 3: Admin, Coordinador, Tutor |
| **Datos de usuario** | Básico: username, nombre, password, rol, API Key Gemini |
| **Asignación Coordinador-Materia** | N:M (un coordinador puede tener varias materias, una materia varios coordinadores) |
| **Coordinador corrige** | No, solo gestiona y supervisa |
| **Asignación Tutor-Comisión** | N:M, por Admin o Coordinador |
| **Tutor multi-materia** | Sí, sin límite |
| **Admin corrige** | Puede, pero no es su función principal |
| **Primer login forzado** | Sí, mantener |
| **API Key Gemini** | Admin y Tutor para corregir, Coordinador para rúbricas desde PDF |
| **Perfil Admin** | Director de Carrera |
| **Perfil Coordinador** | Docente experimentado, coordina materias |
| **Perfil Tutor** | Estudiante avanzado, part-time, 1-2 comisiones típicamente |

---

## 9. Próximos Pasos

Este documento define los usuarios, roles y flujos. Los siguientes documentos detallarán:

- **03-REQUISITOS-FUNCIONALES.md**: Historias de usuario detalladas, módulos, funcionalidades específicas
- **04-REQUISITOS-NO-FUNCIONALES.md**: Rendimiento, seguridad, escalabilidad

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
