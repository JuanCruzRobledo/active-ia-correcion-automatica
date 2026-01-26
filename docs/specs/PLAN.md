# Plan de Trabajo - Especificación del Nuevo Proyecto

---

## ¿Qué es este documento?

Este es el **plan maestro** para crear una especificación detallada de un nuevo proyecto de corrección automática con IA.

### El contexto

Existe un **proyecto actual** (`proyecto-correccion`) que es un sistema de corrección automática de trabajos prácticos de programación usando inteligencia artificial. Este proyecto tiene funcionalidades útiles pero también tiene cosas que no queremos mantener y otras que queremos agregar.

### El objetivo

Crear una **especificación detallada dividida en múltiples archivos .md** que sirva como base para **desarrollar el proyecto desde cero** (con IA o sin ella). Esta especificación:

- **NO contiene código** - Solo descripciones, objetivos, requisitos y guías
- **Es completa** - Abarca todo lo necesario para recrear el proyecto
- **Es práctica** - Incluye detalles específicos de UI, tooltips, jerarquía visual, etc.
- **Está organizada en partes** - 14 archivos que cubren diferentes aspectos

### Cómo se trabaja

1. **Parte por parte:** Se analiza el proyecto actual y se decide qué mantener, qué quitar y qué agregar
2. **Con preguntas:** En cada parte se hacen preguntas para tomar decisiones
3. **Entre sesiones:** Este archivo sirve como referencia para continuar donde se dejó
4. **Stack abierto:** Las tecnologías no están definidas, se decidirán en su momento

### Resultado final

Al completar las 14 partes, tendremos una especificación tan detallada que permitirá:

- Desarrollar el proyecto desde cero sin dudas
- Mantener consistencia en todo el desarrollo
- Servir como referencia durante y después del desarrollo

---

## Estado Actual

| Aspecto                | Estado                    |
| ---------------------- | ------------------------- |
| **Parte actual**       | ¡Especificación completa! |
| **Próximo paso**       | Desarrollo del proyecto   |
| **Partes completadas** | 14 de 14                  |

---

## Las 14 Partes de la Especificación

Cada checkbox se marca cuando la parte está **completamente terminada**.

> **IMPORTANTE:** Al finalizar cada parte, se debe:
>
> 1. Marcar el checkbox correspondiente como completado `[x]`
> 2. Actualizar la tabla de "Estado Actual"
> 3. Registrar las decisiones en "Registro de Sesiones"

### Fase 1: Fundamentos

- [x] `01-VISION-OBJETIVOS.md` - Problema, propuesta de valor, alcance, qué SÍ y qué NO
- [x] `02-USUARIOS-ROLES.md` - Personas, roles, permisos, flujos de usuario

### Fase 2: Requisitos

- [x] `03-REQUISITOS-FUNCIONALES.md` - Historias de usuario, módulos, funcionalidades
- [x] `04-REQUISITOS-NO-FUNCIONALES.md` - Rendimiento, escalabilidad, restricciones

### Fase 3: Arquitectura y Datos

- [x] `05-ARQUITECTURA-STACK.md` - Tecnologías, justificación, diagramas
- [x] `06-MODELO-DATOS.md` - Entidades, relaciones, estructuras JSON

### Fase 4: Diseño y Experiencia

- [x] `07-DISENO-UI-UX.md` - Navegación, wireframes, flujos de pantallas
- [x] `08-SISTEMA-DISENO-ESTILOS.md` - Variables CSS, componentes, tooltips, jerarquía visual

### Fase 5: Desarrollo

- [x] `09-PATRONES-CODIGO.md` - Estructura de carpetas, convenciones, buenas prácticas

### Fase 6: Integraciones y Seguridad

- [x] `10-INTEGRACIONES.md` - IA (Gemini), N8N, APIs externas, prompts
- [x] `11-SEGURIDAD.md` - Autenticación, protección de datos, validaciones

### Fase 7: Infraestructura y Cierre

- [x] `12-ACCESIBILIDAD.md` - WCAG, navegación por teclado, contraste
- [x] `13-INFRAESTRUCTURA-DEPLOY.md` - Docker, ambientes, configuración
- [x] `14-GLOSARIO-REFERENCIAS.md` - Términos técnicos, documentación

---

## Metodología de Trabajo

### Para cada parte:

```
1. Revisar archivos relevantes (documento de ideas + código actual)
2. Hacer preguntas: ¿Qué mantener? ¿Qué quitar? ¿Qué agregar?
3. Tomar decisiones basadas en las respuestas
4. Escribir la parte completa en su archivo .md
5. MARCAR EL CHECKBOX COMO COMPLETADO [x] en este plan
6. Actualizar "Estado Actual" con la próxima parte
7. Registrar decisiones importantes en "Registro de Sesiones"
```

### Principios acordados:

| Principio                 | Descripción                                                         |
| ------------------------- | ------------------------------------------------------------------- |
| **Sin código**            | La especificación describe QUÉ hacer, no CÓMO codificarlo           |
| **Stack abierto**         | Las tecnologías se deciden en la parte 05, no antes                 |
| **UI práctica**           | Incluir tooltips, explicaciones de campos, jerarquía visual         |
| **Completo**              | Cada parte debe tener suficiente detalle para implementar sin dudas |
| **Decisiones explícitas** | Documentar qué NO se incluye, no solo qué SÍ                        |

---

## Fuentes de Información

### Documento de ideas principales:

```
docs/INFORME_SRS_TDD_ACTIVE_IA.md
```

Este documento contiene las **ideas principales** de lo que se quiere lograr en el nuevo proyecto. NO es una especificación completa, sino una referencia inicial que vamos a analizar y expandir parte por parte.

### Proyecto actual (código existente):

```
proyecto-correccion/
├── frontend/src/           → Componentes, páginas, estilos
├── backend/src/            → Controladores, servicios, rutas
├── prisma/                 → Esquema de base de datos
├── n8n/                    → Workflows de IA
├── docker-compose.yml      → Infraestructura
└── docs/                   → Documentación
```

En cada parte vamos a revisar tanto el documento de ideas como el código actual para decidir qué mantener, qué quitar y qué agregar.

---

## Registro de Sesiones

### Sesión 1 - Enero 2026

**Actividad:** Planificación inicial

**Decisiones tomadas:**

- Se definieron las 14 partes de la especificación
- El sistema de diseño será práctico: tooltips, explicaciones de UI, optimización de espacio, jerarquía visual
- Stack tecnológico abierto a cambios (se define en parte 05)
- No se incluye documentación de testing por ahora
- Se trabajará parte por parte analizando el proyecto actual con preguntas

**Archivos creados:**

- `PLAN.md` (este archivo)

**Próxima sesión:** Comenzar con `01-VISION-OBJETIVOS.md`

---

### Sesión 2 - Enero 2026

**Actividad:** Completar Parte 1 - Visión y Objetivos

**Decisiones tomadas:**

- Alcance: TUD primero, luego expandir (sin multi-tenancy inicial)
- Jerarquía: 2 niveles (Materia → Comisión)
- Roles: 3 (Admin, Coordinador, Tutor)
- Coordinador: Gestiona rúbricas y comisiones de sus materias, ve correcciones de tutores
- Integración IA: Con N8N como intermediario (flexibilidad para prompts)
- Similitud: Fase posterior (no MVP)
- Notificaciones: Solo en-app (sin email)
- Lenguajes: Múltiples (configurable)
- Mantener del proyecto actual: lógica consolidación, PDFs, encriptación API keys

**Funcionalidades eliminadas:**

- Multi-tenancy
- Consolidador público
- Detección de similitud (fase posterior)

**Archivos creados:**

- `01-VISION-OBJETIVOS.md`

**Próxima sesión:** Comenzar con `02-USUARIOS-ROLES.md`

---

### Sesión 3 - Enero 2026

**Actividad:** Completar Parte 2 - Usuarios y Roles

**Decisiones tomadas:**

- Datos de usuario: Básico (username, nombre, password, rol, API Key Gemini)
- Asignación Coordinador-Materia: N:M (admin asigna, múltiples coordinadores por materia)
- Coordinador NO corrige: Solo gestiona rúbricas/comisiones y supervisa tutores
- Coordinador necesita API Key: Sí (para generar rúbricas desde PDF)
- Asignación Tutor-Comisión: Admin o Coordinador asigna
- Tutor multi-materia: Sí, sin límite
- Admin puede corregir: Sí, pero no es su función principal
- Primer login forzado: Sí, mantener
- User Personas definidos:
  - Admin: Director de Carrera (48 años, gestión)
  - Coordinador: Docente experimentado (42 años, coordina materias)
  - Tutor: Estudiante avanzado (24 años, part-time, 1-2 comisiones)

**Nueva tabla requerida:**

- `CoordinadorMateria` (relación N:M entre coordinadores y materias)

**Archivos creados:**

- `02-USUARIOS-ROLES.md`

**Próxima sesión:** Comenzar con `03-REQUISITOS-FUNCIONALES.md`

---

### Sesión 4 - Enero 2026

**Actividad:** Completar Parte 3 - Requisitos Funcionales

**Decisiones tomadas:**

- Escala de notas: 0-100 (no 0-10)
- Datos de corrección: Completa (nota + criterios + fortalezas + recomendaciones + comentario)
- Tipos de rúbrica: Mantener todos (TP, Parcial 1, Parcial 2, Recuperatorio, Final, Global)
- Exportación de notas: Excel (.xlsx)
- Campos editables en corrección: Todos
- Identificación alumno: Solo nombre
- Consolidación: Modos + extensiones personalizadas con tags
- Scope de rúbricas: A nivel materia (compartida por todas las comisiones del año)
- Indicadores de criterio: 3 estados (OK, WARNING, ERROR)
- Preview código: Opcional, expandible
- Duplicados: Opción "Sobrescribir existentes" al subir

**Módulos documentados:**

1. Autenticación
2. Gestión de Usuarios
3. Gestión de Materias
4. Gestión de Comisiones
5. Gestión de Rúbricas
6. Gestión de Entregas
7. Corrección Automática
8. Edición de Correcciones
9. Generación de Documentos
10. Perfil de Usuario

**Archivos creados:**

- `03-REQUISITOS-FUNCIONALES.md`

**Próxima sesión:** Comenzar con `04-REQUISITOS-NO-FUNCIONALES.md`

---

### Sesión 5 - Enero 2026

**Actividad:** Completar Parte 4 - Requisitos No Funcionales

**Decisiones tomadas:**

- Tiempo corrección IA: 60 segundos nominal, flexible para casos excepcionales
- Concurrencia: 20 usuarios sin degradación (modo servidor)
- Tamaño máximo ZIP masivo: 100 MB
- JWT expiración: 7 días
- Navegadores: Modernos (últimas 2 versiones de Chrome, Firefox, Edge, Safari)
- Rate limiting: Sí, por IP (100/min) y por usuario (200/min)
- Logging: Completo (logins, correcciones, ediciones, descargas)
- Móvil: Responsive básico (optimizado para desktop)
- Modelo de despliegue: Híbrido (local + servidor web opcionalmente)
- Storage de archivos: Local en modo PC, cloud configurable en servidor
- Backups BD: Diarios automáticos, retención 7 días
- Tiempo ZIP PDFs: 60 segundos máximo

**Capacidad real TUD documentada:**

- ~20 tutores activos
- 5+ materias
- ~17 comisiones por materia
- ~40 alumnos por comisión
- ~20,000+ entregas estimadas por cuatrimestre

**Archivos creados:**

- `04-REQUISITOS-NO-FUNCIONALES.md`

**Próxima sesión:** Comenzar con `05-ARQUITECTURA-STACK.md`

---

### Sesión 6 - Enero 2026

**Actividad:** Completar Parte 5 - Arquitectura y Stack Tecnológico

**Decisiones tomadas:**

- Frontend: React 18+ con TypeScript, Vite, Tailwind CSS
- Backend: Python 3.11 con FastAPI (cambio respecto a Express.js propuesto)
- ORM: SQLAlchemy 2.0 + Alembic para migraciones
- Base de datos: PostgreSQL 15+
- Autenticación: JWT con python-jose
- Integración IA: N8N como intermediario a Google Gemini
- Generación PDFs: ReportLab
- Contenedores: Docker + Docker Compose
- Servidor web: Nginx como proxy reverso y para servir estáticos
- Modelo de despliegue: Híbrido (local en PC del tutor o servidor web centralizado)

**Cambio importante:**

- Se cambió de Node.js/Express a Python/FastAPI como backend
- Esto implica usar SQLAlchemy en lugar de Prisma
- ReportLab en lugar de PDFKit para generación de PDFs

**Archivos creados:**

- `05-ARQUITECTURA-STACK.md`

**Próxima sesión:** Comenzar con `06-MODELO-DATOS.md`

---

### Sesión 7 - Enero 2026

**Actividad:** Completar Parte 6 - Modelo de Datos

**Decisiones tomadas:**

- Historial de correcciones: NO para re-corrección, SÍ para sobrescritura de entrega (tabla EntregaHistorial)
- Metadata de entrega: Básica (nombre, tamaño, tipo, fecha, hash SHA-256)
- Tipos de rúbrica: Enum fijo en código (TP, PARCIAL_1, PARCIAL_2, RECUPERATORIO_1, RECUPERATORIO_2, FINAL, GLOBAL)
- Respuesta IA: Guardada en campo `raw_response` (JSONB) - igual que proyecto actual
- Estructura de corrección basada en proyecto actual (criteria, fortalezas, recomendaciones, general_feedback, raw_response)

**Entidades definidas:**

- Usuario (con roles Admin, Coordinador, Tutor)
- Materia
- CoordinadorMateria (relación N:M)
- Comision
- ComisionTutor (relación N:M)
- Rubrica (con criterios_json)
- Entrega
- Correccion (con criterios_json y raw_response)
- EntregaHistorial (para sobrescrituras)

**Archivos creados:**

- `06-MODELO-DATOS.md`

**Proyecto actual revisado:**

- Se revisó el modelo de Submission.js y Rubric.js del proyecto actual
- Se adaptó la estructura de corrección (criteria, strengths_list, recommendations_list, raw_response)
- Se mantuvo compatibilidad con el formato de respuesta de IA existente

**Próxima sesión:** Comenzar con `07-DISENO-UI-UX.md`

---

### Sesión 8 - Enero 2026

**Actividad:** Completar Parte 7 - Diseño UI/UX

**Decisiones tomadas:**

- Layout: Sidebar fijo izquierdo (w-64), contenido principal a la derecha
- Sidebar estructura: Logo arriba, navegación central, usuario abajo
- Navegación por rol:
  - Admin: Dashboard, Materias, Comisiones, Usuarios, Rúbricas
  - Coordinador: Dashboard, Comisiones, Rúbricas, Tutores, Supervisión
  - Tutor: Dashboard, Entregas, Correcciones, Reportes
- Entregas: Tabla con filtros, checkboxes para selección múltiple, botón "Corregir Seleccionadas"
- Corrección: Modal para ver/editar detalles (no página separada)
- Tooltips: Sistema de iconos (?) con hover para explicaciones
- Responsive: Sidebar oculto en móvil, menú hamburguesa
- Sistema de variables CSS para personalización de estilos (mantener del proyecto actual)

**Frontend del proyecto actual revisado:**

- Layout.tsx, AppSidebar.tsx para estructura
- SubmissionsList.tsx para lista de entregas
- TooltipIcon.tsx para tooltips
- styles.css y tailwind.config.js para variables CSS

**Archivos creados:**

- `07-DISENO-UI-UX.md`

**Próxima sesión:** Comenzar con `08-SISTEMA-DISENO-ESTILOS.md`

---

### Sesión 9 - Enero 2026

**Actividad:** Completar Parte 8 - Sistema de Diseño y Estilos

**Decisiones tomadas:**

- Espacio de color: OKLCH (colores perceptualmente uniformes)
- Paleta nueva con tokens semánticos: background, foreground, primary, accent, etc.
- Tema claro: Accent azul (#3b82f6)
- Tema oscuro: Accent cyan/teal (#22d3ee)
- Estados semánticos agregados: success, warning, info (además de destructive)
- Tipografía: Geist (sans y mono)
- Border radius base: 0.5rem (rounded-lg/md) - más profesional
- Componentes base definidos: Button, Input, Select, Textarea, Checkbox, Card, Badge, Modal, Table, Tabs, Alert, Tooltip, TooltipIcon
- Iconografía: Lucide React
- Animaciones: Solo funcionales (spin, pulse, transitions) - sin decorativas
- Temas: Ambos (light y dark) con toggle
- Espaciado: Default de Tailwind

**Proyecto actual revisado:**

- styles.css (variables CSS actuales)
- tailwind.config.js (mapeo a Tailwind)
- Componentes: Button, Input, Select, Card, Tooltip, TooltipIcon

**Archivos creados:**

- `08-SISTEMA-DISENO-ESTILOS.md`

**Próxima sesión:** Comenzar con `09-PATRONES-CODIGO.md`

---

### Sesión 10 - Enero 2026

**Actividad:** Completar Parte 9 - Patrones de Código

**Decisiones tomadas:**

- Arquitectura Backend: Clean Architecture con 3 capas (Routers → Services → Repositories)
- Routers: Solo request/response y validación con Pydantic. Prohibida lógica de negocio
- Services: Lógica de negocio pura, orquestación de flujo
- Repositories: Capa de persistencia exclusiva con SQLAlchemy
- Dependency Injection: Con Depends() de FastAPI
- Quality Gate: 500 LOC máximo por archivo/clase (innegociable)
- Arquitectura Frontend: Feature-based (carpetas por feature: auth/, entregas/, rubricas/)
- Naming: snake_case para archivos, camelCase para código Python/JS, PascalCase para clases
- Límite LOC Frontend: Sí, mismo límite de 500 LOC
- Docstrings: Completos en todas las funciones (Google Style para Python, TSDoc para TS)
- Manejo de errores: Excepciones personalizadas + Handler global en FastAPI
- Testing: Unit tests (services/repositories) + Integration tests (endpoints)
- Linting Backend: Ruff + Black con configuración específica
- Linting Frontend: ESLint + Prettier
- Imports Python: Absolute imports siempre (nunca relativos)

**Archivos modificados:**

- `05-ARQUITECTURA-STACK.md` - Actualizado con Clean Architecture y estructura de carpetas

**Archivos creados:**

- `09-PATRONES-CODIGO.md`

**Próxima sesión:** Comenzar con `10-INTEGRACIONES.md`

---

### Sesión 11 - Enero 2026

**Actividad:** Completar Parte 10 - Integraciones

**Decisiones tomadas:**

- Google Drive/Sheets: ELIMINADO del proyecto (archivos locales, Excel generado localmente)
- Workflows N8N: Solo 2 (Corrección de entregas + Generación de rúbricas desde PDF)
- Health Check: Sí, endpoint /webhook/health para verificar conexión
- Modelo IA predeterminado: gemini-2.0-flash (rápido y económico)
- Respuesta IA: JSON estructurado estricto con schema fijo
- Reintentos: 1 reintento automático para errores recuperables, luego marcar fallida
- Timeout: 60s nominal, extensible a 120s para códigos largos
- Prompts: Documentados con ejemplos completos (corrección y generación de rúbricas)
- API Keys: Por usuario, encriptadas con AES-256/Fernet
- Estados durante corrección: uploaded → pending_correction → corrected/failed

**Funcionalidades eliminadas del proyecto actual:**

- Integración con Google Drive (crear carpetas)
- Integración con Google Sheets (sincronizar notas)
- Workflows de creación de carpetas jerárquicas (universidad/facultad/carrera)

**Archivos creados:**

- `10-INTEGRACIONES.md`

**Próxima sesión:** Comenzar con `11-SEGURIDAD.md`

---

### Sesión 12 - Enero 2026

**Actividad:** Completar Parte 11 - Seguridad

**Decisiones tomadas:**

- Creación usuarios: Admin crea con password temporal, forzar cambio en primer login
- Política passwords: Mínimo 8 caracteres + al menos 1 número
- Bloqueo cuenta: 5 intentos fallidos → bloqueo 15 minutos (automático)
- Token storage: localStorage
- Encriptación BD: Solo API Keys Gemini (AES-256/Fernet). Passwords con bcrypt
- Auditoría: Log de acciones críticas (login, logout, cambio password, CRUD usuarios, correcciones editadas)
- Upload security: Validar extensión + MIME type + tamaño (máx 100MB)
- Webhooks N8N: Header Auth con X-Webhook-Secret + red interna Docker
- Rate limiting: Por IP, configurable por endpoint (10/15min login, 100/min API general)
- CORS: Configurado solo con dominios permitidos
- Headers seguridad: X-Frame-Options, X-Content-Type-Options, CSP via Nginx

**Archivos creados:**

- `11-SEGURIDAD.md`

**Próxima sesión:** Comenzar con `12-ACCESIBILIDAD.md`

---

### Sesión 13 - Enero 2026

**Actividad:** Completar Parte 12 - Accesibilidad

**Decisiones tomadas:**

- Nivel WCAG: 2.1 AA (estándar de la industria)
- Temas: Claro + Oscuro con preferencia del sistema + toggle manual
- Contraste: 4.5:1 texto normal, 3:1 texto grande (AA)
- Skip links: Sí, "Saltar al contenido principal"
- Screen readers: Soporte completo (ARIA labels, roles, landmarks, live regions)
- Focus visible: Ring con color accent
- Notificaciones: Toast con aria-live (polite para info, assertive para errores)
- Navegación teclado: Completa (Tab, Escape, Arrows en selects/menus)
- Modales: Focus trap, cierre con ESC, restaurar focus al cerrar
- Títulos página: Dinámicos por ruta
- Tablas: caption, scope en headers, aria-label en acciones

**Componentes documentados:**

- SkipLink, ThemeSwitcher, Modal accesible, Select accesible
- FormField con aria-describedby/errormessage
- DataTable accesible, Spinner/Skeleton con aria-busy
- ToastContainer con aria-live region

**Archivos creados:**

- `12-ACCESIBILIDAD.md`

**Próxima sesión:** Comenzar con `13-INFRAESTRUCTURA-DEPLOY.md`

---

### Sesión 14 - Enero 2026

**Actividad:** Completar Parte 13 - Infraestructura y Deploy

**Decisiones tomadas:**

- Ambientes: Solo desarrollo y producción (no staging)
- Base de datos: PostgreSQL en la nube por defecto, opción local con Docker Compose
- Dos docker-compose: `docker-compose.yml` (BD nube) y `docker-compose.local.yml` (BD local)
- Volúmenes: backend_uploads, backend_backups, n8n_data, postgres_data (solo local)
- Variables de entorno: `.env.example` con documentación, separadas por ambiente
- Nginx: Centralizado como proxy reverso + servir frontend
- Health checks: Simples (servidor + BD + espacio en disco)
- Backups: Archivos de entregas y correcciones (sin borrado automático)
- Migraciones: Automáticas al iniciar backend (Alembic)
- Logs: Simples con `docker logs` (nivel INFO en producción, DEBUG en desarrollo)
- N8N: Imagen preconfigurada con workflows + carpeta con scripts de ayuda
- Sin CI/CD por ahora
- Sin Docker Secrets (solo .env)

**Archivos creados:**

- `13-INFRAESTRUCTURA-DEPLOY.md`

**Próxima sesión:** Comenzar con `14-GLOSARIO-REFERENCIAS.md`

---

### Sesión 15 - Enero 2026

**Actividad:** Completar Parte 14 - Glosario y Referencias (FINAL)

**Decisiones tomadas:**

- Glosario alfabético completo con todos los términos técnicos usados en la especificación
- Referencias a documentación oficial de todas las tecnologías del stack
- Herramientas de desarrollo: linting, testing, control de versiones
- Estándares y convenciones: PEP 8, REST API, WCAG, OWASP
- Guía de uso de la especificación según rol (desarrollador, diseñador, PM, QA)
- Enlaces a recursos adicionales: patrones de diseño, performance, UI/UX
- Referencia cruzada a los 14 documentos de la especificación

**Archivos creados:**

- `14-GLOSARIO-REFERENCIAS.md`

**¡ESPECIFICACIÓN COMPLETA!**

Las 14 partes de la especificación han sido completadas exitosamente. El proyecto ahora cuenta con una base sólida y detallada para iniciar el desarrollo desde cero.

**Próxima sesión:** Desarrollo del proyecto

---

## Cómo Continuar en una Nueva Sesión

1. **Leer este archivo** para entender el contexto y estado actual
2. **Ver "Estado Actual"** para saber en qué parte estamos
3. **Ver el último registro de sesión** para saber qué se hizo y qué sigue
4. **Continuar con la parte indicada** en "Próximo paso"

---

## Resumen Rápido (para inicio de sesión)

> **¿Qué estamos haciendo?**
> Analizando el proyecto actual de corrección automática para crear una especificación detallada en 14 partes, la cual servirá para desarrollar el proyecto desde cero.
>
> **¿Cómo?**
> Parte por parte, con preguntas sobre qué mantener/quitar/agregar, sin código, con detalles prácticos de UI.
>
> **¿Dónde quedamos?**
> Ver sección "Estado Actual" arriba.

---

_Última actualización: Sesión 15 - ESPECIFICACIÓN COMPLETA_
