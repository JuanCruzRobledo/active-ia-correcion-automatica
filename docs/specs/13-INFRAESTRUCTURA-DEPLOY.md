# 13. Infraestructura y Deploy

> ⚠️ **Sección/spec parcialmente obsoleta:** la integración de IA ya NO usa N8N. La corrección es nativa en el backend (`backend/app/integrations/`: `ia_provider.py` rutea a `gemini_correction_client.py` / `openrouter_client.py`, llamada HTTP directa a Gemini Studio / OpenRouter). El servicio N8N, su Dockerfile, sus volúmenes (`n8n_data`), variables `N8N_*`, webhooks y healthcheck `/healthz` descritos a continuación son **históricos y ya no forman parte del despliegue actual**.

## Introducción

Este documento especifica la infraestructura, configuración de contenedores, ambientes de despliegue y procedimientos para el sistema de corrección automática.

### Principios de infraestructura

- **Containerización completa**: Todo el stack corre en Docker para portabilidad
- **Despliegue híbrido**: Soporte para modo local (PC del tutor) y modo servidor centralizado
- **Base de datos flexible**: PostgreSQL en la nube por defecto, opción local para desarrollo aislado
- **Simplicidad**: Configuración clara y mantenible, sin sobre-ingeniería

---

## Ambientes de Despliegue

### 1. Desarrollo (Development)

**Propósito**: Desarrollo local en la máquina del programador

**Características**:

- Base de datos: PostgreSQL en la nube (compartida con producción) o local (aislada)
- Hot reload activado en frontend y backend
- Logs detallados (nivel DEBUG)
- Sin optimizaciones de producción
- Volúmenes montados para desarrollo en tiempo real

**Acceso**:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:5000`
- N8N: `http://localhost:5678`
- PostgreSQL (si local): `localhost:5432`

### 2. Producción (Production)

**Propósito**: Servidor web centralizado o PC del tutor en uso real

**Características**:

- Base de datos: PostgreSQL en la nube (recomendado) o local
- Código compilado y optimizado
- Logs nivel INFO
- Health checks activos
- Backups automáticos de archivos

**Acceso**:

- Frontend: Puerto configurable (default 80)
- Backend: Puerto configurable (default 5000)
- N8N: Puerto configurable (default 5678, solo red interna)

---

## Arquitectura de Contenedores

### Diagrama de servicios

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Network                        │
│                     (correcion-network)                      │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │    │   Backend    │    │     N8N      │  │
│  │  (React +    │◄───┤  (FastAPI +  │◄───┤  (Workflows) │  │
│  │   Nginx)     │    │  SQLAlchemy) │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                              │
│         │                    │                              │
│         ▼                    ▼                              │
│  ┌──────────────────────────────────────┐                  │
│  │         Nginx (Proxy Reverso)        │                  │
│  │  - Sirve frontend estático           │                  │
│  │  - Proxy a /api → backend:80         │                  │
│  │  - Headers de seguridad              │                  │
│  │  - Compresión gzip                   │                  │
│  └──────────────────────────────────────┘                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │   PostgreSQL Database   │
              │  (Nube o Local Docker)  │
              └─────────────────────────┘
```

### Servicios Docker

#### 1. **backend** (FastAPI)

**Imagen base**: `python:3.11-slim`

**Responsabilidades**:

- API REST para el frontend
- Lógica de negocio
- Comunicación con PostgreSQL
- Corrección nativa: llamada HTTP directa al proveedor de IA (Gemini Studio / OpenRouter) vía `app/integrations/`
- Generación de PDFs y Excel
- Gestión de archivos (uploads)

**Puertos**:

- Interno: `80`
- Externo: Configurable (default `5000`)

**Volúmenes**:

- `backend_uploads:/app/uploads` - Archivos subidos (entregas)
- `backend_backups:/app/backups` - Backups de entregas y correcciones

**Variables de entorno clave**:

- `DATABASE_URL` - Conexión a PostgreSQL
- `JWT_SECRET` - Secreto para tokens
- `ENCRYPTION_KEY` - Clave Fernet para encriptar API keys (44 chars base64 url-safe)
- `GEMINI_MODEL` / `OPENROUTER_MODEL` / `OPENROUTER_BASE_URL` - Config de los proveedores de IA
- ~~`N8N_WEBHOOK_BASE_URL`~~ - *(histórico, ya no se usa)*

**Health check**:

- Endpoint: `GET /health`
- Verifica: Conexión a BD, espacio en disco

#### 2. **frontend** (React + Nginx)

**Imagen base**: Multi-stage

- Build: `node:20-alpine`
- Runtime: `nginx:alpine`

**Responsabilidades**:

- Interfaz de usuario (SPA)
- Servir archivos estáticos compilados
- Routing del lado del cliente

**Puertos**:

- Interno: `80`
- Externo: Configurable (default `3000`)

**Build args**:

- `VITE_API_URL` - URL del backend

**Health check**:

- Endpoint: `GET /health`
- Respuesta: `200 OK`

#### 3. **n8n** (Workflows de IA)

**Imagen base**: Custom basada en `n8nio/n8n:latest`

**Responsabilidades**:

- Workflow de corrección automática (Gemini AI)
- Workflow de generación de rúbricas desde PDF
- Webhooks para integración con backend

**Puertos**:

- Interno: `5678`
- Externo: Configurable (default `5678`, solo en desarrollo)

**Volúmenes**:

- `n8n_data:/home/node/.n8n` - Workflows y configuración (solo si no usa imagen preconfigurada)

**Variables de entorno clave**:

- `N8N_BASIC_AUTH_ACTIVE` - Activar autenticación
- `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD`
- `WEBHOOK_URL` - URL base para webhooks

**Health check**:

- Endpoint: `GET /healthz`

#### 4. **postgres** (Base de datos - SOLO en modo local)

**Imagen base**: `postgres:15-alpine`

**Responsabilidades**:

- Almacenamiento de datos

**Puertos**:

- Interno: `5432`
- Externo: `5432` (solo en desarrollo)

**Volúmenes**:

- `postgres_data:/var/lib/postgresql/data` - Datos de la BD

**Variables de entorno**:

- `POSTGRES_DB` - Nombre de la base de datos
- `POSTGRES_USER` - Usuario
- `POSTGRES_PASSWORD` - Contraseña

**Health check**:

- Comando: `pg_isready -U postgres`

---

## Configuración de Docker Compose

### docker-compose.yml (Producción - BD en la nube)

**Uso**: Despliegue en servidor o PC del tutor con BD en la nube

**Servicios incluidos**:

- `backend`
- `frontend`
- `n8n`

**Características**:

- PostgreSQL externo (variable `DATABASE_URL` apunta a la nube)
- Todos los servicios en red `correcion-network`
- Volúmenes persistentes para uploads, backups y n8n
- Health checks en todos los servicios
- Restart policy: `unless-stopped`

**Comando de inicio**:

```bash
docker-compose up -d
```

### docker-compose.local.yml (Desarrollo - BD local)

**Uso**: Desarrollo aislado con BD local en Docker

**Servicios incluidos**:

- `backend`
- `frontend`
- `n8n`
- `postgres` (adicional)

**Características**:

- PostgreSQL en contenedor Docker
- Volúmenes montados para desarrollo (hot reload)
- Logs detallados
- Puertos expuestos para debugging

**Comando de inicio**:

```bash
docker-compose -f docker-compose.local.yml up -d
```

---

## Variables de Entorno

### Archivo .env.example

**Propósito**: Plantilla documentada de todas las variables necesarias

**Estructura**:

```bash
# ===========================================
# AMBIENTE
# ===========================================
NODE_ENV=production  # development | production

# ===========================================
# BASE DE DATOS
# ===========================================
# Para BD en la nube (producción):
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Para BD local (desarrollo):
# DATABASE_URL=postgresql://postgres:postgres@postgres:5432/correcion_db

# ===========================================
# BACKEND
# ===========================================
BACKEND_PORT=5000
JWT_SECRET=tu-secreto-jwt-super-seguro-cambiar-en-produccion
JWT_EXPIRES_IN=7d
ENCRYPTION_KEY=tu-clave-encriptacion-32-caracteres-fernet

# ===========================================
# FRONTEND
# ===========================================
FRONTEND_PORT=3000
VITE_API_URL=http://localhost:5000

# ===========================================
# N8N
# ===========================================
N8N_PORT=5678
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=cambiar-en-produccion
WEBHOOK_URL=http://localhost:5678
TIMEZONE=America/Argentina/Buenos_Aires

# URLs internas (entre contenedores Docker)
N8N_WEBHOOK_BASE_URL=http://n8n:5678
N8N_CORRECTION_WEBHOOK=/webhook/corregir-individual
N8N_RUBRIC_WEBHOOK=/webhook/rubrica

# ===========================================
# ARCHIVOS
# ===========================================
UPLOAD_MAX_SIZE=104857600  # 100MB en bytes
UPLOAD_PATH=/app/uploads
BACKUP_PATH=/app/backups

# ===========================================
# CORS
# ===========================================
CORS_ORIGIN=http://localhost:3000  # Cambiar en producción

# ===========================================
# LOGGING
# ===========================================
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR

# ===========================================
# POSTGRES (solo para docker-compose.local.yml)
# ===========================================
POSTGRES_DB=correcion_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

### Separación por ambiente

#### .env.development

Variables específicas para desarrollo:

- `NODE_ENV=development`
- `LOG_LEVEL=DEBUG`
- `DATABASE_URL` apuntando a BD local o de desarrollo
- `CORS_ORIGIN=http://localhost:3000`
- Puertos estándar (3000, 5000, 5678)

#### .env.production

Variables específicas para producción:

- `NODE_ENV=production`
- `LOG_LEVEL=INFO`
- `DATABASE_URL` apuntando a BD en la nube
- `CORS_ORIGIN` con dominio real
- Secretos fuertes y únicos
- Puertos configurables según servidor

---

## Dockerfiles

### Backend Dockerfile

**Ubicación**: `backend/Dockerfile`

**Estrategia**: Single-stage con Python 3.11

**Características**:

- Instalación de dependencias con `pip` (requirements.txt)
- Copia de código fuente
- Ejecución de migraciones automáticas al iniciar
- Health check integrado
- Usuario no-root para seguridad

**Estructura**:

```dockerfile
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/uploads /app/backups

# Usuario no-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Exponer puerto
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:80/health')"

# Script de inicio (ejecuta migraciones + inicia servidor)
CMD ["./start.sh"]
```

**Script start.sh**:

```bash
#!/bin/bash
set -e

# Ejecutar migraciones automáticamente
echo "Running database migrations..."
alembic upgrade head

# Iniciar servidor
echo "Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port 80
```

### Frontend Dockerfile

**Ubicación**: `frontend/Dockerfile`

**Estrategia**: Multi-stage (build + runtime)

**Características**:

- Stage 1: Build con Node.js (compilar React + Vite)
- Stage 2: Runtime con Nginx (servir estáticos)
- Configuración personalizada de Nginx
- Compresión gzip
- Cache de assets estáticos

**Estructura**:

```dockerfile
# ============================================
# Stage 1: Build
# ============================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar dependencias
RUN npm ci

# Copiar código fuente
COPY . .

# Build args para variables de entorno
ARG VITE_API_URL=http://localhost:5000
ENV VITE_API_URL=$VITE_API_URL

# Compilar aplicación
RUN npm run build

# ============================================
# Stage 2: Production (Nginx)
# ============================================
FROM nginx:alpine

# Copiar archivos compilados
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuración de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer puerto
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

# Nginx en foreground
CMD ["nginx", "-g", "daemon off;"]
```

### N8N Dockerfile (Preconfigurado)

**Ubicación**: `n8n/Dockerfile.preconfigured`

**Estrategia**: Imagen custom basada en n8n oficial con workflows incluidos

**Características**:

- Workflows preconfigurados copiados en la imagen
- Credenciales de ejemplo (se configuran con variables de entorno)
- Configuración de zona horaria

**Estructura**:

```dockerfile
FROM n8nio/n8n:latest

# Copiar workflows preconfigurados
COPY --chown=node:node ./data /home/node/.n8n

# Variables de entorno por defecto
ENV N8N_BASIC_AUTH_ACTIVE=true
ENV N8N_BASIC_AUTH_USER=admin
ENV N8N_BASIC_AUTH_PASSWORD=admin123
ENV N8N_HOST=0.0.0.0
ENV N8N_PORT=5678
ENV WEBHOOK_URL=http://localhost:5678
ENV GENERIC_TIMEZONE=America/Argentina/Buenos_Aires

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=5 \
  CMD wget --quiet --tries=1 --spider http://localhost:5678/healthz || exit 1

# Exponer puerto
EXPOSE 5678

# Comando por defecto (heredado de imagen base)
CMD ["n8n"]
```

---

## Configuración de Nginx

### nginx.conf (Frontend)

**Ubicación**: `frontend/nginx.conf`

**Responsabilidades**:

- Servir SPA de React
- Routing del lado del cliente (todas las rutas → index.html)
- Cache de assets estáticos
- Compresión gzip
- Headers de seguridad

**Configuración**:

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Compresión gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript
               application/javascript application/xml+rss application/json;

    # Cache de assets estáticos (JS, CSS, imágenes, fuentes)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA Routing: Todas las rutas devuelven index.html
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "OK";
        add_header Content-Type text/plain;
    }

    # Manejo de errores
    error_page 404 /index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

### nginx.conf (Proxy Reverso - Opcional)

**Ubicación**: `nginx/nginx.conf`

**Uso**: Si se desea un Nginx centralizado que haga proxy al backend

**Configuración**:

```nginx
upstream backend {
    server backend:80;
}

server {
    listen 80;
    server_name localhost;

    # Logs
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Proxy a backend para /api
    location /api {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts para correcciones largas
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }

    # Servir frontend estático
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

---

## Volúmenes Persistentes

### Volúmenes definidos

| Nombre            | Propósito                  | Contenido                               | Backup            |
| ----------------- | -------------------------- | --------------------------------------- | ----------------- |
| `backend_uploads` | Archivos subidos           | ZIPs de entregas, archivos consolidados | Sí                |
| `backend_backups` | Backups de archivos        | Copias de entregas y correcciones       | No (es el backup) |
| `n8n_data`        | Configuración N8N          | Workflows, credenciales, ejecuciones    | Opcional          |
| `postgres_data`   | Base de datos (solo local) | Datos de PostgreSQL                     | Sí (dump SQL)     |

### Estrategia de backups

#### 1. Backups de archivos (entregas y correcciones)

**Objetivo**: Resguardar archivos subidos y correcciones generadas

**Implementación**:

- Script en el backend que copia archivos críticos a `/app/backups`
- Se ejecuta automáticamente después de cada corrección masiva
- Estructura de carpetas: `backups/YYYY-MM-DD/`

**Contenido respaldado**:

- Archivos ZIP de entregas originales
- PDFs de correcciones generadas
- Archivos consolidados

**Retención**: Indefinida (no se borran automáticamente)

**Acceso**: Volumen `backend_backups` montado en el host

#### 2. Backups de base de datos (solo si PostgreSQL local)

**Objetivo**: Resguardar datos de la BD

**Implementación**:

- Script manual o cron job que ejecuta `pg_dump`
- Guarda dump SQL en `backups/db/`

**Comando**:

```bash
docker exec postgres pg_dump -U postgres correcion_db > backup_$(date +%Y%m%d).sql
```

**Retención**: Manual (usuario decide cuándo borrar)

---

## Red Docker

### correcion-network

**Tipo**: Bridge

**Propósito**: Comunicación interna entre servicios

**Servicios conectados**:

- `backend`
- `frontend`
- `n8n`
- `postgres` (solo en modo local)

**Características**:

- Resolución de nombres por nombre de servicio (ej: `http://backend:80`)
- Aislamiento de la red del host
- Comunicación interna sin exponer puertos innecesarios

---

## Health Checks

### Backend (/health)

**Endpoint**: `GET /health`

**Verificaciones**:

- ✅ Servidor FastAPI respondiendo
- ✅ Conexión a PostgreSQL activa
- ✅ Espacio en disco suficiente (>1GB libre)

**Respuesta exitosa** (200):

```json
{
  "status": "healthy",
  "database": "connected",
  "disk_space_gb": 15.3,
  "timestamp": "2026-01-24T11:30:00Z"
}
```

**Respuesta fallida** (503):

```json
{
  "status": "unhealthy",
  "database": "disconnected",
  "error": "Could not connect to PostgreSQL"
}
```

### Frontend (/health)

**Endpoint**: `GET /health`

**Verificación**:

- ✅ Nginx respondiendo

**Respuesta**: `200 OK` (texto plano)

### N8N (/healthz) *(histórico — el servicio N8N ya no forma parte del despliegue)*

**Endpoint**: `GET /healthz`

**Verificación**:

- ✅ N8N activo y respondiendo

**Respuesta**: `200 OK`

---

## Migraciones de Base de Datos

### Alembic (SQLAlchemy)

**Propósito**: Gestionar cambios en el esquema de la BD

**Ubicación**: `backend/alembic/`

**Flujo de trabajo**:

1. **Crear migración inicial** (primera vez):

   ```bash
   alembic revision --autogenerate -m "Initial schema"
   ```

2. **Aplicar migraciones** (automático al iniciar backend):

   ```bash
   alembic upgrade head
   ```

3. **Crear nuevas migraciones** (cuando cambia el modelo):
   ```bash
   alembic revision --autogenerate -m "Add campo_nuevo to tabla_x"
   ```

### Ejecución automática

**Comportamiento**: Al iniciar el contenedor `backend`, el script `start.sh` ejecuta:

```bash
alembic upgrade head
```

Esto asegura que:

- En el primer inicio, se crean todas las tablas
- En inicios posteriores, se aplican migraciones pendientes
- No requiere intervención manual

---

## Logging

### Estrategia simple

**Implementación**: Logs a stdout/stderr capturados por Docker

**Acceso**:

```bash
# Ver logs de un servicio
docker logs correcion-backend

# Seguir logs en tiempo real
docker logs -f correcion-backend

# Ver últimas 100 líneas
docker logs --tail 100 correcion-backend
```

### Niveles de log

| Ambiente   | Nivel | Detalle                                  |
| ---------- | ----- | ---------------------------------------- |
| Desarrollo | DEBUG | Todos los eventos, queries SQL, requests |
| Producción | INFO  | Eventos importantes, errores, warnings   |

### Eventos registrados

Según `11-SEGURIDAD.md`, se registran:

- ✅ Logins exitosos y fallidos
- ✅ Cambios de contraseña
- ✅ Creación/edición/eliminación de usuarios
- ✅ Correcciones automáticas (inicio, fin, errores)
- ✅ Ediciones manuales de correcciones
- ✅ Descargas de PDFs y Excel
- ✅ Subida de entregas

### Formato de log

**Estructura** (JSON para facilitar parsing):

```json
{
  "timestamp": "2026-01-24T11:30:00Z",
  "level": "INFO",
  "service": "backend",
  "event": "user_login",
  "user_id": 123,
  "username": "tutor01",
  "ip": "192.168.1.100",
  "success": true
}
```

---

## Imagen Preconfigurada de N8N

### Propósito

Facilitar el despliegue con workflows ya configurados, evitando configuración manual.

### Estructura de carpeta n8n/

```
n8n/
├── Dockerfile.preconfigured       # Dockerfile para imagen custom
├── README.md                      # Guía de uso y configuración
├── scripts/
│   ├── export-workflows.sh        # Exportar workflows desde N8N
│   ├── build-image.sh             # Construir imagen preconfigurada
│   └── push-image.sh              # Subir imagen a Docker Hub
├── workflows/                     # Workflows en JSON (referencia)
│   ├── correccion-individual.json
│   └── generacion-rubrica.json
└── data/                          # Datos preconfigurados (se copian a la imagen)
    ├── database.sqlite            # BD de N8N con workflows
    └── .n8n/
        └── config                 # Configuración de N8N
```

### Proceso de creación

#### 1. Configurar N8N manualmente (primera vez)

```bash
# Iniciar N8N con volumen temporal
docker run -d --name n8n-temp \
  -p 5678:5678 \
  -v n8n_temp:/home/node/.n8n \
  n8nio/n8n:latest

# Acceder a http://localhost:5678
# Crear workflows manualmente
# Configurar credenciales de ejemplo
```

#### 2. Exportar configuración

```bash
# Ejecutar script de exportación
cd n8n/
./scripts/export-workflows.sh

# Esto copia /home/node/.n8n del contenedor a ./data/
```

#### 3. Construir imagen preconfigurada

```bash
# Ejecutar script de build
./scripts/build-image.sh

# Esto ejecuta:
# docker build -f Dockerfile.preconfigured -t usuario/n8n-correcion:latest .
```

#### 4. Subir imagen a Docker Hub (opcional)

```bash
# Ejecutar script de push
./scripts/push-image.sh

# Esto ejecuta:
# docker push usuario/n8n-correcion:latest
```

### Scripts incluidos

#### export-workflows.sh

```bash
#!/bin/bash
set -e

echo "Exportando workflows de N8N..."

# Copiar datos de N8N del contenedor al host
docker cp n8n-temp:/home/node/.n8n ./data/

echo "Workflows exportados a ./data/"
echo "Revisa y limpia credenciales sensibles antes de commitear"
```

#### build-image.sh

```bash
#!/bin/bash
set -e

IMAGE_NAME=${1:-"usuario/n8n-correcion"}
IMAGE_TAG=${2:-"latest"}

echo "Construyendo imagen $IMAGE_NAME:$IMAGE_TAG..."

docker build -f Dockerfile.preconfigured \
  -t $IMAGE_NAME:$IMAGE_TAG \
  .

echo "Imagen construida exitosamente"
echo "Para usarla, actualiza docker-compose.yml con: image: $IMAGE_NAME:$IMAGE_TAG"
```

#### push-image.sh

```bash
#!/bin/bash
set -e

IMAGE_NAME=${1:-"usuario/n8n-correcion"}
IMAGE_TAG=${2:-"latest"}

echo "Subiendo imagen $IMAGE_NAME:$IMAGE_TAG a Docker Hub..."

docker push $IMAGE_NAME:$IMAGE_TAG

echo "Imagen subida exitosamente"
```

### README.md de n8n/

Debe incluir:

- Instrucciones paso a paso para crear la imagen preconfigurada
- Cómo actualizar workflows en la imagen
- Cómo configurar credenciales de Gemini
- Troubleshooting común

---

## Procedimientos de Despliegue

### Primera vez - Desarrollo local con BD local

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd proyecto-correccion

# 2. Copiar variables de entorno
cp .env.example .env.development
# Editar .env.development con valores locales

# 3. Iniciar servicios
docker-compose -f docker-compose.local.yml up -d

# 4. Verificar salud de servicios
docker ps
docker logs correcion-backend
docker logs correcion-frontend
docker logs correcion-n8n

# 5. Acceder a la aplicación
# Frontend: http://localhost:3000
# Backend: http://localhost:5000
# N8N: http://localhost:5678
```

### Primera vez - Producción con BD en la nube

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd proyecto-correccion

# 2. Configurar variables de entorno
cp .env.example .env.production
# Editar .env.production:
#   - DATABASE_URL con URL de PostgreSQL en la nube
#   - JWT_SECRET con valor fuerte
#   - ENCRYPTION_KEY con valor fuerte
#   - CORS_ORIGIN con dominio real
#   - N8N_BASIC_AUTH_PASSWORD con contraseña segura

# 3. Construir imágenes
docker-compose build

# 4. Iniciar servicios
docker-compose up -d

# 5. Verificar salud
docker ps
curl http://localhost:5000/health

# 6. Crear usuario admin inicial (ejecutar en backend)
docker exec -it correcion-backend python scripts/create_admin.py
```

### Actualización de código

```bash
# 1. Detener servicios
docker-compose down

# 2. Actualizar código
git pull origin main

# 3. Reconstruir imágenes
docker-compose build

# 4. Reiniciar servicios
docker-compose up -d

# 5. Verificar logs
docker logs -f correcion-backend
```

### Backup manual

```bash
# Backup de archivos (entregas)
docker run --rm -v correcion_backend_uploads:/data -v $(pwd):/backup \
  alpine tar czf /backup/uploads_backup_$(date +%Y%m%d).tar.gz /data

# Backup de base de datos (si PostgreSQL local)
docker exec postgres pg_dump -U postgres correcion_db > \
  backup_db_$(date +%Y%m%d).sql

# Backup de N8N (workflows)
docker run --rm -v correcion_n8n_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/n8n_backup_$(date +%Y%m%d).tar.gz /data
```

### Restauración de backup

```bash
# Restaurar archivos
docker run --rm -v correcion_backend_uploads:/data -v $(pwd):/backup \
  alpine tar xzf /backup/uploads_backup_20260124.tar.gz -C /

# Restaurar base de datos (si PostgreSQL local)
docker exec -i postgres psql -U postgres correcion_db < backup_db_20260124.sql

# Restaurar N8N
docker run --rm -v correcion_n8n_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/n8n_backup_20260124.tar.gz -C /
```

---

## Seguridad en Producción

### Checklist de seguridad

- [ ] Cambiar `JWT_SECRET` por valor fuerte y único
- [ ] Cambiar `ENCRYPTION_KEY` por valor de 32 caracteres
- [ ] Cambiar `N8N_BASIC_AUTH_PASSWORD` por contraseña segura
- [ ] Configurar `CORS_ORIGIN` solo con dominios permitidos
- [ ] Usar HTTPS en producción (certificado SSL)
- [ ] No exponer puerto de N8N al exterior (solo red interna)
- [ ] No exponer puerto de PostgreSQL al exterior
- [ ] Configurar firewall para permitir solo puertos 80/443
- [ ] Revisar que `.env` esté en `.gitignore`
- [ ] Usar usuario no-root en contenedores
- [ ] Mantener imágenes Docker actualizadas

### Variables sensibles

**NUNCA commitear**:

- `JWT_SECRET`
- `ENCRYPTION_KEY`
- `DATABASE_URL` (con credenciales)
- `N8N_BASIC_AUTH_PASSWORD`
- API Keys de Gemini (están en BD encriptadas)

**Usar**:

- Variables de entorno (`.env`)
- Secretos de Docker (opcional, para producción avanzada)
- Gestores de secretos (AWS Secrets Manager, HashiCorp Vault) en despliegues enterprise

---

## Monitoreo y Troubleshooting

### Comandos útiles

```bash
# Ver estado de servicios
docker-compose ps

# Ver logs de todos los servicios
docker-compose logs

# Ver logs de un servicio específico
docker-compose logs backend

# Seguir logs en tiempo real
docker-compose logs -f backend

# Reiniciar un servicio
docker-compose restart backend

# Acceder a shell de un contenedor
docker exec -it correcion-backend bash

# Ver uso de recursos
docker stats

# Ver volúmenes
docker volume ls

# Inspeccionar volumen
docker volume inspect correcion_backend_uploads
```

### Problemas comunes

#### Backend no conecta a PostgreSQL

**Síntoma**: Error "could not connect to server"

**Solución**:

1. Verificar `DATABASE_URL` en `.env`
2. Verificar que PostgreSQL esté accesible
3. Revisar logs: `docker logs correcion-backend`

#### N8N no responde

**Síntoma**: Timeout en webhooks

**Solución**:

1. Verificar health check: `docker exec correcion-n8n wget -O- http://localhost:5678/healthz`
2. Revisar logs: `docker logs correcion-n8n`
3. Verificar que workflows estén activos en N8N UI

#### Frontend muestra página en blanco

**Síntoma**: Pantalla blanca, error en consola

**Solución**:

1. Verificar `VITE_API_URL` en build
2. Reconstruir imagen: `docker-compose build frontend`
3. Revisar logs de Nginx: `docker logs correcion-frontend`

#### Espacio en disco lleno

**Síntoma**: Errores al subir archivos

**Solución**:

1. Verificar espacio: `df -h`
2. Limpiar imágenes viejas: `docker system prune -a`
3. Mover backups antiguos fuera del servidor

---

## Escalabilidad Futura

### Consideraciones para crecimiento

Si el sistema necesita escalar más allá de TUD:

#### 1. Base de datos

- Migrar a PostgreSQL gestionado (AWS RDS, Google Cloud SQL)
- Configurar réplicas de lectura para reportes
- Implementar connection pooling (PgBouncer)

#### 2. Almacenamiento de archivos

- Migrar de filesystem local a S3/Cloud Storage
- Implementar CDN para servir PDFs generados

#### 3. Backend

- Escalar horizontalmente con múltiples instancias
- Usar load balancer (Nginx, HAProxy)
- Implementar cache con Redis

#### 4. N8N

- Usar N8N en modo queue (con Redis)
- Escalar workers de N8N

#### 5. Infraestructura

- Migrar a Kubernetes para orquestación
- Implementar CI/CD con GitHub Actions
- Monitoreo con Prometheus + Grafana

---

## Resumen de Archivos de Configuración

| Archivo                        | Ubicación           | Propósito                                 |
| ------------------------------ | ------------------- | ----------------------------------------- |
| `docker-compose.yml`           | Raíz                | Compose para producción (BD nube)         |
| `docker-compose.local.yml`     | Raíz                | Compose para desarrollo (BD local)        |
| `.env.example`                 | Raíz                | Plantilla de variables de entorno         |
| `.env.development`             | Raíz (no commitear) | Variables para desarrollo                 |
| `.env.production`              | Raíz (no commitear) | Variables para producción                 |
| `backend/Dockerfile`           | backend/            | Imagen de backend (FastAPI)               |
| `backend/start.sh`             | backend/            | Script de inicio (migraciones + servidor) |
| `frontend/Dockerfile`          | frontend/           | Imagen de frontend (React + Nginx)        |
| `frontend/nginx.conf`          | frontend/           | Configuración de Nginx para SPA           |
| `n8n/Dockerfile.preconfigured` | n8n/                | Imagen custom de N8N                      |
| `n8n/README.md`                | n8n/                | Guía de configuración de N8N              |
| `n8n/scripts/*.sh`             | n8n/scripts/        | Scripts para gestionar imagen N8N         |
| `.gitignore`                   | Raíz                | Excluir .env, node_modules, etc.          |
| `.dockerignore`                | backend/, frontend/ | Excluir archivos del build                |

---

## Conclusión

Esta especificación de infraestructura proporciona:

✅ **Flexibilidad**: Soporte para desarrollo local y producción en servidor  
✅ **Simplicidad**: Configuración clara sin sobre-ingeniería  
✅ **Portabilidad**: Todo containerizado con Docker  
✅ **Seguridad**: Health checks, logs, backups, variables de entorno  
✅ **Mantenibilidad**: Documentación completa de procedimientos

El sistema está diseñado para ser desplegado fácilmente tanto en la PC de un tutor como en un servidor centralizado, con la base de datos en la nube para mantener sincronización de datos entre múltiples instancias.
