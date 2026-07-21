# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Active-IA** is a full-stack platform for AI-powered automatic correction of student practical assignments for TUD (Technical University). The backend calls Google Gemini (AI Studio) or OpenRouter directly (no N8N intermediary) to evaluate code submissions against rubric criteria.

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

The backend calls the AI provider directly (no N8N intermediary): `app/integrations/gemini_correction_client.py` / `openrouter_client.py`, routed by `ia_provider.py`. The model name comes from `settings.GEMINI_MODEL` (single source of truth; today `gemini-3.5-flash` for Gemini, `google/gemini-3.5-flash` for OpenRouter). Each user stores their AI API key encrypted with Fernet — AES-128-CBC + HMAC-SHA256 (`app/core/security.py`).

## Critical Rules

### Backend
- Never put business logic in Routers; never access DB directly from Services
- API Keys (Gemini/OpenRouter) must always be stored encrypted with Fernet (AES-128-CBC + HMAC-SHA256) — never plaintext
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
| AI provider error | `HTTPException 502` + retry |
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

Full reference: `backend/.env.example` (derived from `backend/app/core/config.py`). Key vars:
- `DATABASE_URL` — PostgreSQL connection string (async: `postgresql+asyncpg://...`)
- `SECRET_KEY` — JWT signing key; generate with `openssl rand -hex 32`
- `ENCRYPTION_KEY` — Fernet key for AI API keys; generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` (base64 url-safe, 44 chars — NOT a raw 32-char string)
- `GEMINI_MODEL` — Gemini Studio model (default `gemini-3.5-flash`); `GEMINI_TIMEOUT_SECONDS` (default 90)
- `OPENROUTER_BASE_URL` / `OPENROUTER_MODEL` — OpenRouter provider (default model `google/gemini-3.5-flash`)
- `UPLOAD_DIR` — File upload path; `MAX_UPLOAD_SIZE`, `ALLOWED_EXTENSIONS`, ZIP-bomb limits (`MAX_ZIP_EXPANDED_SIZE`, `MAX_ZIP_ENTRIES`)
- `CORS_ORIGINS` — comma-separated allowed origins
- `RESEND_API_KEY` / `EMAIL_REMITENTE` / `EMAIL_RATE_POR_SEGUNDO` — email notifications (Resend)
- `ACCESS_TOKEN_EXPIRE_DAYS` — JWT expiry (default: 7)
- (CRUD-002) `ALLOW_HARD_DELETE` fue eliminado: los DELETE son SIEMPRE soft (baja lógica), nunca físico — regla dura del proyecto. Una purga física real, si se necesitara, debe ser una feature deliberada y auditada, no un toggle de env.

DEBUG must be `false` in production; with `false`, the app aborts on startup if `SECRET_KEY`/`ENCRYPTION_KEY` still hold their placeholder values.

## Skills (Auto-invoke)

| Action | Skill file |
|--------|-----------|
| Creating FastAPI endpoints / Pydantic schemas / SQLAlchemy models | `skills/python-fastapi/SKILL.md` |
| Creating React components / hooks / Tailwind styling | `skills/react-typescript/SKILL.md` |
| Implementing correction flow | `skills/correccion-ia/SKILL.md` |
| Managing rubrics/criteria | `skills/rubricas/SKILL.md` |
