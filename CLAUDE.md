# Active-IA - Instrucciones para Claude Code

> Este archivo se carga automaticamente al iniciar. Sigue los pasos en orden.

---

## PASO 1: Ver estado actual

Lee @ESTADO.md para saber la fase y tarea actual.

---

## PASO 2: Obtener tarea

Lee @ROADMAP.md y busca la primera tarea `[ ]` pendiente.

---

## PASO 3: Cargar reglas segun el trabajo

- No cargar reglas hasta definir trabajo

### Para BACKEND (FastAPI + Python):

- Reglas: @.claude/rules/backend.md
- Skill detallado: @skills/python-fastapi/SKILL.md
- Modelos de datos: @docs/specs/06-MODELO-DATOS.md

### Para FRONTEND (React + TypeScript):

- Reglas: @.claude/rules/frontend.md
- Skill detallado: @skills/react-typescript/SKILL.md
- Diseno UI: @docs/specs/07-DISENO-UI-UX.md

### Para CORRECCION IA:

- Skill: @skills/correccion-ia/SKILL.md
- Integraciones: @docs/specs/10-INTEGRACIONES.md

### Para RUBRICAS:

- Skill: @skills/rubricas/SKILL.md

---

## PASO 4: Consultar especificaciones si necesitas

- No consultar especificaciones hasta definir trabajo

| Necesitas...           | Archivo                                  |
| ---------------------- | ---------------------------------------- |
| Requisitos funcionales | @docs/specs/03-REQUISITOS-FUNCIONALES.md |
| Modelo de datos        | @docs/specs/06-MODELO-DATOS.md           |
| Roles y permisos       | @docs/specs/02-USUARIOS-ROLES.md         |
| Seguridad              | @docs/specs/11-SEGURIDAD.md              |
| Estilos/colores        | @docs/specs/08-SISTEMA-DISENO-ESTILOS.md |

---

## PASO 5: Implementar siguiendo las reglas

Ver @AGENTS.md para reglas globales del proyecto.

---

## PASO 6: Al terminar

1. Marca `[x]` la tarea en ROADMAP.md
2. Actualiza ESTADO.md con lo que hiciste

---

## REGLAS CRITICAS

### SIEMPRE

- Leer el skill/reglas correspondiente ANTES de escribir codigo
- Clean Architecture: `Router -> Service -> Repository`
- Validar permisos en cada endpoint
- Maximo 500 LOC por archivo
- Actualizar ESTADO.md al terminar

### NUNCA

- Logica de negocio en Routers
- Acceso a BD desde Services
- `any` en TypeScript
- API Keys en texto plano
- Saltear tareas del ROADMAP

---

## ESTRUCTURA DEL PROYECTO

```
active-ia/
├── CLAUDE.md           # Este archivo (cargado automaticamente)
├── ESTADO.md           # Estado actual del proyecto
├── ROADMAP.md          # 103 tareas atomicas
├── AGENTS.md           # Reglas globales
│
├── .claude/
│   ├── settings.json   # Permisos de Claude Code
│   └── rules/          # Reglas por area
│       ├── backend.md
│       └── frontend.md
│
├── docs/specs/         # 14 documentos de especificacion
├── skills/             # 4 skills con patrones detallados
│
├── backend/app/        # Codigo FastAPI (a crear)
└── frontend/src/       # Codigo React (a crear)
```

---

## COMANDOS

```bash
# Backend
cd backend && uvicorn app.main:app --reload
cd backend && alembic revision --autogenerate -m "mensaje"
cd backend && alembic upgrade head
cd backend && pytest

# Frontend
cd frontend && npm run dev
cd frontend && npm run build
cd frontend && npm run lint
```

---

## FLUJO RESUMIDO

```
ESTADO.md → ROADMAP.md → Skill/Reglas → Implementar → Actualizar ESTADO.md
```
