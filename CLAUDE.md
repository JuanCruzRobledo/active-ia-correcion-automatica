# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Active-IA** is a full-stack platform for AI-powered automatic correction of student practical assignments for TUD (Technical University). It integrates with N8N workflows and Google Gemini to evaluate code submissions against rubric criteria.

## Commands

### Backend

```bash
cd backend
pip install -r requirements.txt          # Install dependencies
python scripts/init_db.py                # Initialize DB + seed admin user
uvicorn app.main:app --reload            # Dev server (port 8000)
alembic revision --autogenerate -m ""    # Generate new migration
alembic upgrade head                     # Apply migrations
pytest                                   # Run all tests
pytest --cov=app                         # Run with coverage
```

Default admin credentials after `init_db.py`: `admin` / `admin123`

### Frontend

```bash
cd frontend
npm install
npm run dev          # Dev server (Vite HMR)
npm run build        # Production build
npm run lint         # ESLint
npm run typecheck    # TypeScript check
```

### Docker

```bash
docker-compose -f docker-compose.local.yml up -d   # Local dev (all services)
docker-compose up -d                                # Production
docker-compose logs -f backend
```

## Architecture

### Backend: Clean Architecture

```
REQUEST → Routers → Services → Repositories → Database
```

- **Routers** (`app/routers/`): HTTP handling, Pydantic validation only — no business logic
- **Services** (`app/services/`): Business logic — no direct DB access
- **Repositories** (`app/repositories/`): All SQLAlchemy queries
- **Models** (`app/models/`): SQLAlchemy ORM entities
- **Schemas** (`app/schemas/`): Pydantic DTOs for request/response validation

### Frontend: Feature-based modules

Each feature under `frontend/src/features/{name}/` has:
- `components/` — feature-specific React components
- `hooks/` — React Query hooks wrapping the service
- `services/` — Axios calls (import from `@/shared/services/api`)
- `types/` — TypeScript interfaces
- `pages/` — full page views

Shared reusable code lives in `frontend/src/shared/`.

### AI Correction Flow

```
Entrega upload → Code consolidation (ZIP/TXT → string)
  → Direct AI call (Gemini / OpenRouter, model from settings.GEMINI_MODEL)
  → Correccion record (nota + JSONB criteria scores)
```

The backend calls the AI provider directly (no N8N intermediary): `app/integrations/gemini_correction_client.py` / `openrouter_client.py`, routed by `ia_provider.py`. The model name comes from `settings.GEMINI_MODEL` (single source of truth). Each user stores their AI API key encrypted with AES-256 (`app/core/security.py`).

## Critical Rules

### Backend
- Never put business logic in Routers; never access DB directly from Services
- API Keys (Gemini) must always be stored AES-256 encrypted — never plaintext
- Use JSONB columns for rubric criteria and correction scores
- Max 500 LOC per file
- Use soft delete (never hard delete) for audit purposes
- Validate role-based permissions on every endpoint

### Frontend
- Functional components with TypeScript only — no class components, no `any`
- All API calls go through `services/` — never fetch directly in components
- Use React Query for server state; React Hook Form + Zod for forms
- Tailwind CSS only — no CSS modules, no inline styles (except dynamic values)
- Components < 200 LOC; pages lazy-loaded
- Always handle loading and error states

### Error Handling (Backend)
| Type | Response |
|------|----------|
| Validation | `HTTPException 400` |
| Not found | `HTTPException 404` |
| Forbidden | `HTTPException 403` |
| AI/N8N error | `HTTPException 502` + retry |
| Internal | `HTTPException 500` + detailed log |

## Data Model Summary

```
Usuario (roles: ADMIN | COORDINADOR | TUTOR)
  ├── N:M → Materia (as CoordinadorMateria)
  └── N:M → Comision (as ComisionTutor)
       └── 1:N → Entrega
                  └── 1:N → Correccion (nota, criterios JSONB, fortalezas, recomendaciones)
Materia → 1:N → Comision
Materia → 1:N → Rubrica (criterios JSONB, puntaje_maximo, tipo)
Actividad = audit log (every action tracked)
```

## Commit Conventions

Conventional Commits: `<type>(<scope>): <description>`

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
**Scopes:** `auth`, `users`, `materias`, `comisiones`, `rubricas`, `entregas`, `correcciones`, `docs`, `api`, `ui`

## Environment Variables

Key vars from `.env.example`:
- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT signing (min 32 chars)
- `ENCRYPTION_KEY` — AES-256 key for Gemini API keys (exactly 32 chars)
- `N8N_WEBHOOK_URL` — N8N service URL
- `UPLOAD_DIR` — File upload path
- `ACCESS_TOKEN_EXPIRE_DAYS` — JWT expiry (default: 7)

## Skills (Auto-invoke)

| Action | Skill file |
|--------|-----------|
| Creating FastAPI endpoints / Pydantic schemas / SQLAlchemy models | `skills/python-fastapi/SKILL.md` |
| Creating React components / hooks / Tailwind styling | `skills/react-typescript/SKILL.md` |
| Implementing correction flow | `skills/correccion-ia/SKILL.md` |
| Managing rubrics/criteria | `skills/rubricas/SKILL.md` |
