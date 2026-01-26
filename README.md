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

## Instalación

### Requisitos previos
- Node.js 18+
- Python 3.11+
- PostgreSQL 15+
- Docker (opcional)

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
