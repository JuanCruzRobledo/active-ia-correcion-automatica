# Active-IA

Plataforma web de corrección automática de trabajos prácticos con inteligencia artificial para la Tecnicatura Universitaria a Distancia (TUD).

## Descripción

Active-IA automatiza la corrección de trabajos prácticos de programación, genera retroalimentación pedagógica contextualizada con IA y reduce el tiempo de corrección de 25 minutos a menos de 5 minutos por entrega.

## Stack Tecnológico

### Frontend
- React 18+ con TypeScript
- Vite
- Tailwind CSS
- React Router 6
- React Query
- Axios

### Backend
- Python 3.11
- FastAPI
- SQLAlchemy 2.0
- Alembic (migraciones)
- PostgreSQL 15+

### Integración IA
- N8N (orquestación de workflows)
- Google Gemini API (gemini-2.0-flash)

## Estructura del Proyecto

```
active-ia/
├── frontend/          # Aplicación React
├── backend/           # API FastAPI
├── skills/            # Skills para agentes IA
├── AGENTS.md          # Instrucciones para agentes IA
└── README.md          # Este archivo
```

## Roles del Sistema

| Rol | Descripción |
|-----|-------------|
| **Admin** | Gestiona plataforma, usuarios, materias |
| **Coordinador** | Gestiona rúbricas y comisiones de sus materias |
| **Tutor** | Corrige entregas, genera PDFs y exporta notas |

## Instalación Rápida con Docker (Recomendado) 🐳

### Requisitos previos
- Docker 20.10+
- Docker Compose 2.0+

### Opción 1: Modo HÍBRIDO (Base de datos en la nube - DEFAULT)

```bash
# 1. Clonar repositorio
git clone <url-del-repo>
cd active-ia

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones (DATABASE_URL, JWT_SECRET, etc.)

# 3. Levantar servicios
docker-compose up -d

# 4. Acceder a la aplicación
# Frontend: http://localhost:3000
# Backend:  http://localhost:5000
# N8N:      http://localhost:5678
```

### Opción 2: Modo LOCAL COMPLETO (Base de datos local en Docker)

```bash
# 1. Clonar y configurar (igual que opción 1)
git clone <url-del-repo>
cd active-ia
cp .env.example .env

# 2. Levantar servicios (incluye PostgreSQL local)
docker-compose -f docker-compose.local.yml up -d

# 3. Acceder a la aplicación
# Frontend:   http://localhost:3000
# Backend:    http://localhost:5000
# N8N:        http://localhost:5678
# PostgreSQL: localhost:5432
```

**Ver documentación completa:** [docs/DEPLOY.md](docs/DEPLOY.md)

---

## Instalación Manual (Sin Docker)

### Requisitos previos
- Node.js 20+
- Python 3.11+
- PostgreSQL 15+

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### N8N
```bash
# Seguir instrucciones en n8n/README.md
```

## Configuración de AI Assistants

```bash
cd skills
./setup.sh --all
```

## Documentación

- `AGENTS.md` - Instrucciones para agentes de IA
- `frontend/AGENTS.md` - Instrucciones específicas de frontend
- `backend/AGENTS.md` - Instrucciones específicas de backend
- `skills/README.md` - Sistema de skills

## Licencia

MIT
