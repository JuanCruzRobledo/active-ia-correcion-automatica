# 05 - Arquitectura y Stack Tecnológico

---

## 1. Resumen del Stack

| Capa | Tecnología |
|------|------------|
| **Frontend** | React + TypeScript + Vite + Tailwind CSS |
| **Backend** | Python 3.11 + FastAPI |
| **Base de Datos** | PostgreSQL 15+ |
| **ORM** | SQLAlchemy 2.0 + Alembic |
| **Integración IA** | N8N + Google Gemini API |
| **PDFs** | ReportLab |
| **Contenedores** | Docker + Docker Compose |
| **Servidor Web** | Nginx |

---

## 2. Stack Frontend

### 2.1 Tecnologías

| Tecnología | Versión | Justificación |
|------------|---------|---------------|
| **React** | 18+ | Ecosistema maduro, componentes reutilizables, amplia comunidad, excelente documentación |
| **TypeScript** | 5+ | Tipado estático que previene errores, mejor autocompletado, código más mantenible |
| **Vite** | 5+ | Build tool moderno, HMR instantáneo, configuración simple, builds optimizados |
| **Tailwind CSS** | 3+ | Desarrollo ágil de UI, estilos consistentes, bundle optimizado con purge |
| **React Router** | 6+ | Navegación declarativa, lazy loading de rutas, nested routes |
| **Axios** | 1+ | Cliente HTTP con interceptores para manejo de auth y errores |

### 2.2 Librerías Adicionales

| Librería | Propósito |
|----------|-----------|
| **@tanstack/react-query** | Manejo de estado del servidor, caché, invalidación |
| **react-hook-form** | Manejo de formularios con validación |
| **zod** | Validación de esquemas TypeScript |
| **react-hot-toast** | Notificaciones toast |
| **lucide-react** | Iconos SVG |
| **date-fns** | Manipulación de fechas |

### 2.3 Estructura de Carpetas Frontend

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── components/          # Componentes reutilizables
│   │   ├── ui/              # Componentes base (Button, Input, Modal, etc.)
│   │   ├── layout/          # Header, Sidebar, Footer
│   │   └── features/        # Componentes específicos de features
│   ├── pages/               # Páginas/vistas
│   │   ├── auth/            # Login, cambio contraseña
│   │   ├── admin/           # Panel de administración
│   │   ├── tutor/           # Panel del tutor
│   │   └── perfil/          # Configuración de perfil
│   ├── hooks/               # Custom hooks
│   ├── services/            # Llamadas a API (axios)
│   ├── stores/              # Estado global (si se necesita)
│   ├── types/               # Tipos TypeScript
│   ├── utils/               # Utilidades y helpers
│   ├── styles/              # Estilos globales, configuración Tailwind
│   ├── App.tsx              # Componente raíz
│   ├── main.tsx             # Entry point
│   └── router.tsx           # Configuración de rutas
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── postcss.config.js
```

---

## 3. Stack Backend

### 3.1 Tecnologías

| Tecnología | Versión | Justificación |
|------------|---------|---------------|
| **Python** | 3.11 | Versión estable con buen rendimiento, soporte amplio de librerías |
| **FastAPI** | 0.100+ | Framework moderno, async nativo, validación automática, documentación OpenAPI |
| **SQLAlchemy** | 2.0+ | ORM maduro, flexible, soporte async, patrón Unit of Work |
| **Alembic** | 1.12+ | Migraciones de base de datos, versionado de esquema |
| **Pydantic** | 2.0+ | Validación de datos, serialización, integrado con FastAPI |
| **Uvicorn** | 0.24+ | Servidor ASGI de alto rendimiento |

### 3.2 Librerías Adicionales

| Librería | Propósito |
|----------|-----------|
| **python-jose[cryptography]** | Generación y validación de JWT |
| **passlib[bcrypt]** | Hash de contraseñas con bcrypt |
| **cryptography** | Encriptación AES-256 para API Keys |
| **python-multipart** | Manejo de uploads de archivos |
| **aiofiles** | Operaciones de archivo asíncronas |
| **httpx** | Cliente HTTP async para llamadas a N8N |
| **reportlab** | Generación de PDFs |
| **openpyxl** | Generación de archivos Excel |
| **python-dotenv** | Variables de entorno |

### 3.3 Arquitectura Clean Architecture

El backend implementa **Clean Architecture** con separación estricta de responsabilidades:

```
┌─────────────────────────────────────────────────────────────────┐
│                         ROUTERS                                  │
│  Capa de presentación: Request/Response + Validación Pydantic   │
│  ❌ Prohibida lógica de negocio                                  │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ Depends()
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SERVICES                                 │
│  Lógica de negocio pura. Orquestan el flujo de datos.          │
│  No conocen HTTP ni base de datos directamente.                 │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ Depends()
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       REPOSITORIES                               │
│  Capa de persistencia: Interactúan con BD usando SQLAlchemy    │
│  Abstraen las operaciones CRUD de la base de datos.            │
└─────────────────────────────────────────────────────────────────┘
```

| Capa | Responsabilidad | Prohibido |
|------|-----------------|-----------|
| **Routers** | Recibir requests, validar con Pydantic, retornar responses | Lógica de negocio, acceso a BD |
| **Services** | Lógica de negocio, orquestación, reglas de dominio | Acceso directo a BD, conocer HTTP |
| **Repositories** | CRUD, queries a BD, transacciones | Lógica de negocio, validaciones de dominio |

**Dependency Injection:** El acoplamiento entre capas se resuelve con `Depends()` de FastAPI.

### 3.4 Quality Gate (Innegociable)

| Regla | Límite | Acción |
|-------|--------|--------|
| **Líneas por archivo** | 500 LOC máximo | Refactorizar y modularizar |
| **Principios** | SOLID + Clean Code | Obligatorio |
| **God Classes** | Prohibidas | Dividir en clases especializadas |

Si un módulo se acerca a 500 LOC, es **obligatorio** refactorizar inmediatamente.

### 3.5 Estructura de Carpetas Backend

```
backend/
├── app/
│   ├── api/                     # CAPA: Routers (Presentación)
│   │   ├── v1/
│   │   │   ├── routers/
│   │   │   │   ├── auth_router.py
│   │   │   │   ├── user_router.py
│   │   │   │   ├── materia_router.py
│   │   │   │   ├── comision_router.py
│   │   │   │   ├── rubrica_router.py
│   │   │   │   ├── entrega_router.py
│   │   │   │   ├── correccion_router.py
│   │   │   │   └── documento_router.py
│   │   │   └── __init__.py      # Agrupa todos los routers
│   │   └── deps.py              # Dependencias compartidas (get_db, get_current_user)
│   │
│   ├── services/                # CAPA: Lógica de Negocio
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── materia_service.py
│   │   ├── comision_service.py
│   │   ├── rubrica_service.py
│   │   ├── entrega_service.py
│   │   ├── correccion_service.py
│   │   ├── consolidation_service.py
│   │   ├── pdf_generator_service.py
│   │   └── excel_export_service.py
│   │
│   ├── repositories/            # CAPA: Persistencia
│   │   ├── base_repository.py   # Clase base con CRUD genérico
│   │   ├── user_repository.py
│   │   ├── materia_repository.py
│   │   ├── comision_repository.py
│   │   ├── rubrica_repository.py
│   │   ├── entrega_repository.py
│   │   └── correccion_repository.py
│   │
│   ├── models/                  # Modelos SQLAlchemy (ORM)
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── materia.py
│   │   ├── comision.py
│   │   ├── rubrica.py
│   │   ├── entrega.py
│   │   └── correccion.py
│   │
│   ├── schemas/                 # Schemas Pydantic (DTOs)
│   │   ├── user_schema.py
│   │   ├── materia_schema.py
│   │   ├── comision_schema.py
│   │   ├── rubrica_schema.py
│   │   ├── entrega_schema.py
│   │   ├── correccion_schema.py
│   │   └── common_schema.py     # Schemas compartidos (paginación, respuestas)
│   │
│   ├── core/                    # Configuración central
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── security.py          # JWT, hashing, encriptación
│   │   ├── exceptions.py        # Excepciones personalizadas
│   │   ├── exception_handlers.py # Handler global de excepciones
│   │   └── logging.py           # Configuración de logs
│   │
│   ├── db/                      # Base de datos
│   │   ├── session.py           # Engine y SessionLocal
│   │   └── init_db.py           # Inicialización y seeds
│   │
│   ├── utils/                   # Utilidades puras
│   │   └── files.py
│   │
│   └── main.py                  # Entry point FastAPI
│
├── alembic/                     # Migraciones
│   ├── versions/
│   └── env.py
├── tests/                       # Tests
│   ├── unit/                    # Tests unitarios
│   │   ├── services/
│   │   └── repositories/
│   └── integration/             # Tests de integración
│       └── api/
├── alembic.ini
├── requirements.txt
├── pyproject.toml               # Configuración Ruff/Black
├── Dockerfile
└── .env.example
```

---

## 4. Base de Datos

### 4.1 PostgreSQL

| Aspecto | Especificación |
|---------|----------------|
| **Versión** | 15+ |
| **Encoding** | UTF-8 |
| **Collation** | es_ES.UTF-8 o en_US.UTF-8 |
| **Timezone** | UTC (conversión en aplicación) |

### 4.2 Justificación de PostgreSQL

| Ventaja | Descripción |
|---------|-------------|
| **Datos estructurados** | Ideal para relaciones claras (materias, comisiones, usuarios) |
| **JSONB** | Soporte nativo para JSON (criterios de rúbricas, correcciones) |
| **Transacciones ACID** | Garantía de integridad en operaciones críticas |
| **Escalabilidad** | Réplicas de lectura, particionado si crece |
| **Ecosistema** | Herramientas maduras, excelente soporte en cloud |

### 4.3 Configuración de Conexión

```python
# Formato de conexión
DATABASE_URL = "postgresql+asyncpg://user:password@host:port/database"

# Pool de conexiones
POOL_SIZE = 5
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30
```

---

## 5. Integración con IA

### 5.1 Arquitectura de Integración

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    Frontend     │       │    Backend      │       │      N8N        │
│    (React)      │       │   (FastAPI)     │       │   (Workflows)   │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │  POST /corregir         │                         │
         ├────────────────────────>│                         │
         │                         │                         │
         │                         │  POST /webhook/corregir │
         │                         ├────────────────────────>│
         │                         │                         │
         │                         │                         │  Gemini API
         │                         │                         ├──────────────>
         │                         │                         │<──────────────
         │                         │                         │
         │                         │    JSON response        │
         │                         │<────────────────────────┤
         │                         │                         │
         │   Corrección guardada   │                         │
         │<────────────────────────┤                         │
         │                         │                         │
```

### 5.2 N8N

| Aspecto | Especificación |
|---------|----------------|
| **Propósito** | Orquestación de llamadas a IA, permite modificar prompts sin código |
| **Versión** | Latest (self-hosted) |
| **Puerto** | 5678 |
| **Workflows** | Corrección de entregas, Generación de rúbricas desde PDF |

### 5.3 Workflows de N8N

#### Workflow: Corrección de Entrega

```
Trigger: Webhook POST /webhook/corregir
    │
    ▼
Recibe: {
  codigo: string,      # Código consolidado
  rubrica: object,     # Criterios de evaluación
  api_key: string      # API Key Gemini del tutor
}
    │
    ▼
Construir prompt estructurado
    │
    ▼
Llamar a Google Gemini API
    │
    ▼
Parsear respuesta JSON
    │
    ▼
Retornar: {
  nota: number,
  criterios: array,
  fortalezas: array,
  recomendaciones: array,
  comentario_general: string
}
```

#### Workflow: Generar Rúbrica desde PDF

```
Trigger: Webhook POST /webhook/generar-rubrica
    │
    ▼
Recibe: {
  pdf_base64: string,  # PDF codificado
  api_key: string      # API Key Gemini
}
    │
    ▼
Extraer texto del PDF
    │
    ▼
Llamar a Gemini para extraer criterios
    │
    ▼
Retornar: {
  criterios: array,
  puntaje_maximo: number
}
```

### 5.4 Google Gemini

| Aspecto | Especificación |
|---------|----------------|
| **Modelo** | gemini-2.0-flash (o versión disponible) |
| **API** | generativelanguage.googleapis.com |
| **Autenticación** | API Key por usuario (almacenada encriptada) |
| **Límites** | Según cuota del usuario |

---

## 6. Generación de Documentos

### 6.1 PDFs con ReportLab

| Aspecto | Especificación |
|---------|----------------|
| **Librería** | ReportLab 4.0+ |
| **Formato** | A4 (210 x 297 mm) |
| **Fuente** | Helvetica (incluida), soporte UTF-8 |

**Estructura del PDF de devolución:**

```python
# Pseudocódigo de estructura
def generar_pdf_devolucion(correccion):
    # Encabezado
    - Logo/Título "Active-IA"
    - Materia, Comisión, Año
    - Nombre del TP
    - Nombre del alumno
    - Fecha de corrección

    # Nota destacada
    - Calificación grande y centrada (ej: "85/100")

    # Tabla de criterios
    - Por cada criterio:
      - Nombre del criterio
      - Puntaje obtenido / máximo
      - Indicador visual (color según estado)
      - Feedback específico

    # Fortalezas (lista con bullets)

    # Recomendaciones (lista numerada)

    # Comentarios del evaluador

    # Pie de página
    - "Generado por Active-IA"
    - Fecha/hora de generación
```

### 6.2 Excel con openpyxl

| Aspecto | Especificación |
|---------|----------------|
| **Librería** | openpyxl 3.1+ |
| **Formato** | .xlsx |

**Estructura del Excel de notas:**

| Columna | Contenido |
|---------|-----------|
| A | Alumno |
| B | Nota |
| C | Estado |
| D | Fecha Corrección |
| E | Editado Manualmente |

---

## 7. Infraestructura

### 7.1 Docker Compose

```yaml
# docker-compose.yml (estructura)
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - N8N_WEBHOOK_URL=${N8N_WEBHOOK_URL}
    volumes:
      - ./uploads:/app/uploads
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - frontend
      - backend

volumes:
  postgres_data:
  n8n_data:
```

### 7.2 Servicios y Puertos

| Servicio | Puerto Interno | Puerto Expuesto | Descripción |
|----------|---------------|-----------------|-------------|
| **Nginx** | 80 | 80 | Proxy reverso, sirve frontend |
| **Frontend** | 80 | 3000 (dev) | App React compilada |
| **Backend** | 5000 | 5000 | API FastAPI |
| **PostgreSQL** | 5432 | 5432 | Base de datos |
| **N8N** | 5678 | 5678 | Workflows de IA |

### 7.3 Nginx como Proxy Reverso

```nginx
# nginx.conf (simplificado)
server {
    listen 80;
    server_name localhost;

    # Frontend (archivos estáticos)
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # API Backend
    location /api/ {
        proxy_pass http://backend:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Uploads (archivos estáticos)
    location /uploads/ {
        alias /app/uploads/;
    }
}
```

---

## 8. Modelo de Despliegue Híbrido

### 8.1 Modo Local (Tutor en su PC)

```
┌─────────────────────────────────────────────────────────────┐
│                     PC del Tutor                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Frontend   │  │   Backend   │  │    N8N      │          │
│  │   (React)   │  │  (FastAPI)  │  │ (Workflows) │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                  │
│         └────────────────┼────────────────┘                  │
│                          │                                   │
│                    ┌─────┴─────┐                             │
│                    │  Archivos │  ← Almacenamiento local     │
│                    │  (uploads)│                             │
│                    └───────────┘                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ Internet
                           ▼
              ┌─────────────────────────┐
              │   PostgreSQL (Cloud)    │  ← BD compartida
              │   (Railway, Supabase,   │
              │    Render, etc.)        │
              └─────────────────────────┘
```

**Características del modo local:**
- Cada tutor ejecuta la app completa en su PC
- Los archivos (entregas, PDFs) se almacenan localmente
- Solo la BD está en la nube (compartida)
- Requiere Docker instalado en PC del tutor

### 8.2 Modo Servidor Web (Centralizado)

```
┌─────────────────────────────────────────────────────────────┐
│                     Servidor Cloud                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                      Nginx                            │    │
│  │            (Proxy reverso + estáticos)               │    │
│  └──────────────────────┬───────────────────────────────┘    │
│                         │                                    │
│  ┌──────────┐  ┌────────┴───────┐  ┌──────────┐             │
│  │ Frontend │  │    Backend     │  │   N8N    │             │
│  │ (static) │  │   (FastAPI)    │  │          │             │
│  └──────────┘  └────────┬───────┘  └──────────┘             │
│                         │                                    │
│              ┌──────────┴──────────┐                        │
│              │     PostgreSQL      │                        │
│              └─────────────────────┘                        │
│                         │                                    │
│              ┌──────────┴──────────┐                        │
│              │   Storage (local    │                        │
│              │   o S3/GCS)         │                        │
│              └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ Internet (HTTPS)
                           │
              ┌─────────────────────────┐
              │   Navegador del Tutor   │
              └─────────────────────────┘
```

**Características del modo servidor:**
- App centralizada en servidor cloud
- Tutores acceden vía navegador (no instalan nada)
- Archivos en el servidor (opcionalmente S3/GCS)
- Más simple para usuarios, más costo de infraestructura

### 8.3 Configuración por Modo

| Aspecto | Modo Local | Modo Servidor |
|---------|------------|---------------|
| **Instalación** | Docker en PC | Nada (solo navegador) |
| **BD** | Cloud (compartida) | Cloud (misma instancia) |
| **Archivos** | Local en PC | Servidor o S3 |
| **N8N** | Local en PC | Centralizado |
| **Costo usuario** | PC con Docker | Solo internet |
| **Costo infra** | Solo BD cloud | Servidor completo |

---

## 9. Diagrama de Arquitectura General

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 INTERNET                                     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTPS
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAPA DE PRESENTACIÓN                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      FRONTEND (React + Nginx)                          │  │
│  │                                                                        │  │
│  │  • Aplicación SPA compilada estáticamente (Vite build)                │  │
│  │  • Servida por Nginx (Puerto 80/443)                                  │  │
│  │  • Proxy reverso hacia Backend API                                    │  │
│  │  • Rutas protegidas según rol (Admin/Coordinador/Tutor)              │  │
│  │  • Estado: React Query + localStorage para JWT                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP interno (Puerto 5000)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CAPA DE NEGOCIO                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       BACKEND (FastAPI)                                │  │
│  │                                                                        │  │
│  │  • API REST con autenticación JWT (python-jose)                       │  │
│  │  • Validación con Pydantic                                            │  │
│  │  • Endpoints: auth, users, materias, comisiones, rubricas,           │  │
│  │               entregas, correcciones, documentos                      │  │
│  │  • Servicios: Consolidación, Corrección IA, PDFs, Excel              │  │
│  │  • Middleware: Auth, CORS, Rate Limiting, Logging                    │  │
│  │  • Async con Uvicorn                                                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                              │                    │                          │
│              ┌───────────────┘                    └───────────────┐          │
│              │ HTTP (Puerto 5678)                                │          │
│              ▼                                                   │          │
│  ┌────────────────────────────┐                                 │          │
│  │     N8N (Workflows)        │                                 │          │
│  │                            │                                 │          │
│  │  • Workflow corrección     │                                 │          │
│  │  • Workflow gen. rúbricas  │                                 │          │
│  │  • Prompts editables       │                                 │          │
│  │  • Manejo de errores       │                                 │          │
│  └─────────────┬──────────────┘                                 │          │
│                │ HTTPS (API Externa)                            │          │
│                ▼                                                 │          │
│  ┌────────────────────────────┐                                 │          │
│  │   Google Gemini API        │                                 │          │
│  │   (Servicio Externo)       │                                 │          │
│  └────────────────────────────┘                                 │          │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ PostgreSQL (Puerto 5432)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             CAPA DE DATOS                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         PostgreSQL 15+                                 │  │
│  │                                                                        │  │
│  │  • Base de datos relacional principal                                 │  │
│  │  • Tablas: usuarios, materias, comisiones, rubricas, entregas,       │  │
│  │            correcciones, coordinador_materia, comision_tutor          │  │
│  │  • Campos JSONB para criterios y correcciones                        │  │
│  │  • Índices optimizados para consultas frecuentes                     │  │
│  │  • Migraciones con Alembic                                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Sistema de Archivos                                 │  │
│  │                                                                        │  │
│  │  uploads/                                                             │  │
│  │  ├── entregas/{comision_id}/{rubrica_id}/{alumno}/                   │  │
│  │  │   ├── original.zip          # Archivo original subido             │  │
│  │  │   └── consolidado.txt       # Código consolidado                  │  │
│  │  └── rubricas/{materia_id}/                                          │  │
│  │      └── consigna_original.pdf # PDF de consigna (si aplica)         │  │
│  │                                                                        │  │
│  │  • Local en modo PC                                                   │  │
│  │  • Servidor o S3/GCS en modo cloud                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Flujo de Comunicación

### 10.1 Flujo de Corrección Automática

```
1. Usuario hace clic en "Corregir" en Frontend
   │
   ▼
2. Frontend envía POST /api/v1/entregas/{id}/corregir
   │
   ▼
3. Backend valida:
   - Token JWT válido
   - Usuario tiene permiso sobre la entrega
   - Usuario tiene API Key Gemini configurada
   │
   ▼
4. Backend recupera:
   - Contenido consolidado de la entrega
   - Rúbrica con criterios
   - API Key Gemini del usuario (desencriptada)
   │
   ▼
5. Backend envía POST a N8N webhook con:
   {
     codigo: "...",
     rubrica: {...},
     api_key: "AIza..."
   }
   │
   ▼
6. N8N construye prompt y llama a Gemini API
   │
   ▼
7. Gemini procesa y retorna evaluación
   │
   ▼
8. N8N parsea respuesta y retorna JSON a Backend
   │
   ▼
9. Backend almacena corrección en PostgreSQL
   │
   ▼
10. Backend retorna confirmación a Frontend
    │
    ▼
11. Frontend actualiza UI mostrando resultado
```

### 10.2 Flujo de Autenticación

```
1. Usuario ingresa credenciales en /login
   │
   ▼
2. Frontend envía POST /api/v1/auth/login
   │
   ▼
3. Backend valida:
   - Username existe y está activo
   - Contraseña coincide (bcrypt verify)
   │
   ▼
4. Backend genera JWT con:
   - user_id
   - rol
   - exp (7 días)
   │
   ▼
5. Backend retorna:
   {
     access_token: "eyJ...",
     token_type: "bearer",
     user: { id, username, nombre, rol }
   }
   │
   ▼
6. Frontend almacena token en localStorage
   │
   ▼
7. Frontend redirige según rol:
   - Admin → /admin
   - Coordinador → /coordinador
   - Tutor → /tutor
```

---

## 11. Variables de Entorno

### 11.1 Backend (.env)

```bash
# Base de datos
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/activeai

# Seguridad
SECRET_KEY=tu-clave-secreta-de-256-bits-minimo
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=7
ENCRYPTION_KEY=clave-para-aes-256-encriptacion

# N8N
N8N_WEBHOOK_URL=http://n8n:5678/webhook

# Archivos
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE=104857600  # 100 MB

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:80

# Logging
LOG_LEVEL=INFO
```

### 11.2 Frontend (.env)

```bash
VITE_API_URL=http://localhost:5000/api/v1
VITE_APP_NAME=Active-IA
```

### 11.3 Docker Compose (.env)

```bash
# PostgreSQL
DB_USER=activeai
DB_PASSWORD=tu-password-seguro
DB_NAME=activeai

# N8N
N8N_USER=admin
N8N_PASSWORD=tu-password-n8n
```

---

## 12. Resumen de Decisiones

| Aspecto | Decisión | Justificación |
|---------|----------|---------------|
| **Frontend** | React + TypeScript + Vite + Tailwind | Ecosistema maduro, desarrollo rápido, tipado |
| **Backend** | Python 3.11 + FastAPI | Moderno, async, validación automática, buena DX |
| **ORM** | SQLAlchemy 2.0 + Alembic | Maduro, flexible, migraciones robustas |
| **Base de datos** | PostgreSQL 15+ | Relacional robusto, JSONB, escalable |
| **Autenticación** | JWT con python-jose | Estándar, stateless, flexible |
| **Integración IA** | N8N → Gemini | Prompts editables sin código |
| **PDFs** | ReportLab | Librería Python madura, control total |
| **Contenedores** | Docker Compose | Entorno reproducible, fácil despliegue |
| **Servidor web** | Nginx | Proxy reverso eficiente, sirve estáticos |
| **Despliegue** | Híbrido (local + servidor) | Flexibilidad según necesidades |

---

## 13. Próximos Pasos

Este documento define la arquitectura y stack tecnológico. Los siguientes documentos detallarán:

- **06-MODELO-DATOS.md**: Entidades detalladas, relaciones, estructuras JSON
- **07-DISENO-UI-UX.md**: Navegación, wireframes, flujos de pantallas

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
