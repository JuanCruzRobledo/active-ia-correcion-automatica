# Guía de Despliegue - Active-IA

## Topología vigente (producción)

El despliegue real del proyecto **no usa Docker Compose**:

- **Backend**: app service de **EasyPanel**, construido directo desde `backend/Dockerfile`.
- **Frontend**: **Vercel**, sin Docker (config en `frontend/vercel.json`).
- **IA**: el backend llama **directo** a Gemini/OpenRouter con la API key de cada usuario,
  guardada cifrada con AES-256. No hay orquestador ni servicio intermedio.

Los pasos de esta guía son la **alternativa self-hosted** (todo el stack con Docker Compose en
una máquina propia), útil para desarrollo local o para un VPS. Ver `EASYPANEL_DEPLOY.md` para el
camino principal.

---

## Despliegue self-hosted con Docker Compose

Dos modos:

1. **Modo HÍBRIDO** (default): Base de datos en la nube
2. **Modo LOCAL COMPLETO**: Todos los servicios locales incluyendo PostgreSQL

---

## Requisitos Previos

### Software necesario

- Docker Engine 20.10+ ([Descargar](https://docs.docker.com/get-docker/))
- Docker Compose 2.0+ (incluido con Docker Desktop)
- Git (para clonar el repositorio)

### Verificar instalación

```bash
docker --version          # Docker version 20.10+
docker-compose --version  # Docker Compose version 2.0+
```

---

## Modo 1: HÍBRIDO (Producción - BD en la Nube) 🌐

**Usar cuando:**
- Despliegas en un servidor web
- Despliegas en la PC del tutor con internet estable
- Quieres compartir datos entre múltiples instancias

**Servicios incluidos:** backend, frontend
**Base de datos:** PostgreSQL en la nube (externa)

### Paso 1: Clonar repositorio

```bash
git clone <url-del-repositorio>
cd active-ia
```

### Paso 2: Configurar variables de entorno

```bash
# Copiar template
cp .env.example .env

# Editar archivo .env
nano .env  # o usar tu editor preferido
```

**Variables OBLIGATORIAS a configurar:**

```bash
# Base de datos en la nube (ej: Supabase, Railway, Render)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Seguridad (generar valores fuertes)
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# CORS (usar dominio real en producción)
CORS_ORIGINS=http://tu-dominio.com

# URLs del frontend (cambiar si usas dominio)
VITE_API_URL=http://tu-dominio.com:5000
```

### Paso 3: Iniciar servicios

```bash
# Construir imágenes y levantar servicios
docker-compose up -d

# Ver logs en tiempo real
docker-compose logs -f
```

### Paso 4: Verificar salud de servicios

```bash
# Ver estado de contenedores
docker-compose ps

# Verificar health checks
curl http://localhost:5000/health  # Backend
curl http://localhost:3000/health  # Frontend

# Ver logs individuales
docker logs active-ia-backend
docker logs active-ia-frontend
```

### Paso 5: Crear usuario administrador inicial

```bash
# Ejecutar script de creación de admin (si existe)
docker exec -it active-ia-backend python scripts/create_admin.py

# O crear manualmente desde la UI después del primer inicio
```

### Paso 6: Configurar la IA

No hay nada que configurar a nivel de infraestructura: el backend llama directo a
Gemini/OpenRouter. Cada usuario carga su propia API key desde su perfil en la app, y se guarda
cifrada con AES-256 usando `ENCRYPTION_KEY`.

### Paso 7: Acceder a la aplicación

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000

---

## Modo 2: LOCAL COMPLETO (Desarrollo) 💻

**Usar cuando:**
- Desarrollas sin conexión a internet
- Quieres una instancia completamente aislada
- Estás en fase de desarrollo/testing

**Servicios incluidos:** backend, frontend, postgres
**Base de datos:** PostgreSQL en Docker (local)

### Paso 1: Clonar repositorio

```bash
git clone <url-del-repositorio>
cd active-ia
```

### Paso 2: Configurar variables de entorno

```bash
# Copiar template
cp .env.example .env

# Editar archivo .env
nano .env
```

**Variables para modo local:**

```bash
# Base de datos local (ya configurada por defecto)
POSTGRES_DB=active_ia_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Seguridad (usar valores de desarrollo)
SECRET_KEY=dev-secret-change-in-production
ENCRYPTION_KEY=dev-encryption-key-32-chars!!

# CORS
CORS_ORIGINS=http://localhost:3000

# URLs
VITE_API_URL=http://localhost:5000
```

### Paso 3: Iniciar servicios

```bash
# Construir imágenes y levantar servicios (incluyendo PostgreSQL)
docker-compose -f docker-compose.local.yml up -d

# Ver logs en tiempo real
docker-compose -f docker-compose.local.yml logs -f
```

### Paso 4: Verificar servicios

```bash
# Ver estado
docker-compose -f docker-compose.local.yml ps

# Verificar PostgreSQL
docker exec -it active-ia-postgres psql -U postgres -c "\l"

# Verificar health checks
curl http://localhost:5000/health
curl http://localhost:3000/health
```

### Paso 5: Acceder a la aplicación

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **PostgreSQL**: localhost:5432 (con cliente psql)

---

## Comandos Útiles

### Gestión de servicios

```bash
# Detener servicios
docker-compose down

# Detener y eliminar volúmenes (CUIDADO: borra datos)
docker-compose down -v

# Reconstruir imágenes
docker-compose build

# Reconstruir y reiniciar
docker-compose up -d --build

# Ver logs
docker-compose logs -f [servicio]

# Reiniciar un servicio específico
docker-compose restart backend
```

### Acceso a contenedores

```bash
# Acceder a shell del backend
docker exec -it active-ia-backend bash

# Acceder a PostgreSQL (modo local)
docker exec -it active-ia-postgres psql -U postgres active_ia_db
```

### Backups

#### Backup de archivos (entregas)

```bash
# Backup de uploads
docker run --rm \
  -v active-ia_backend_uploads:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/uploads_backup_$(date +%Y%m%d).tar.gz -C /data .

# Backup de backups (redundancia)
docker run --rm \
  -v active-ia_backend_backups:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/backups_backup_$(date +%Y%m%d).tar.gz -C /data .
```

#### Backup de base de datos (solo modo local)

```bash
# Dump SQL
docker exec active-ia-postgres \
  pg_dump -U postgres active_ia_db > backup_db_$(date +%Y%m%d).sql

# Backup con compresión
docker exec active-ia-postgres \
  pg_dump -U postgres active_ia_db | gzip > backup_db_$(date +%Y%m%d).sql.gz
```

### Restauración de backups

#### Restaurar archivos

```bash
docker run --rm \
  -v active-ia_backend_uploads:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/uploads_backup_20260202.tar.gz -C /data
```

#### Restaurar base de datos (modo local)

```bash
# Desde archivo SQL
docker exec -i active-ia-postgres \
  psql -U postgres active_ia_db < backup_db_20260202.sql

# Desde archivo comprimido
gunzip -c backup_db_20260202.sql.gz | \
  docker exec -i active-ia-postgres \
  psql -U postgres active_ia_db
```

---

## Actualización de la Aplicación

### Actualizar código

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
docker-compose logs -f
```

### Actualizar solo backend

```bash
docker-compose build backend
docker-compose up -d --no-deps backend
```

### Actualizar solo frontend

```bash
docker-compose build frontend
docker-compose up -d --no-deps frontend
```

---

## Migraciones de Base de Datos

Las migraciones se ejecutan **automáticamente** al iniciar el contenedor backend.

### Ver estado de migraciones

```bash
docker exec -it active-ia-backend alembic current
```

### Ver historial de migraciones

```bash
docker exec -it active-ia-backend alembic history
```

### Aplicar migraciones manualmente (si falla el auto)

```bash
docker exec -it active-ia-backend alembic upgrade head
```

### Rollback de migración

```bash
# Rollback una migración
docker exec -it active-ia-backend alembic downgrade -1

# Rollback a versión específica
docker exec -it active-ia-backend alembic downgrade <revision_id>
```

---

## Troubleshooting

### Backend no conecta a PostgreSQL

**Síntoma**: Error "could not connect to server"

**Solución**:

```bash
# Verificar DATABASE_URL en .env
cat .env | grep DATABASE_URL

# Verificar que PostgreSQL esté accesible (modo local)
docker exec -it active-ia-postgres pg_isready

# Ver logs del backend
docker logs active-ia-backend
```

### Falla la corrección con IA

**Síntoma**: Timeout o error en correcciones

**Solución**:

```bash
# La llamada a Gemini/OpenRouter sale desde el backend: revisar sus logs
docker logs active-ia-backend
```

Verificar además:

- Que el usuario tenga cargada su API key en el perfil.
- Que `ENCRYPTION_KEY` no haya cambiado desde que se guardó esa key (si cambia, no se puede
  descifrar).
- Que el host tenga salida a internet hacia el proveedor de IA.

### Frontend muestra página en blanco

**Síntoma**: Pantalla blanca en navegador

**Solución**:

```bash
# Verificar VITE_API_URL en build
docker inspect active-ia-frontend | grep VITE_API_URL

# Reconstruir frontend
docker-compose build frontend
docker-compose up -d frontend

# Ver logs de Nginx
docker logs active-ia-frontend
```

### Espacio en disco lleno

**Síntoma**: Error al subir archivos

**Solución**:

```bash
# Ver uso de disco
df -h

# Limpiar imágenes Docker viejas
docker system prune -a

# Limpiar volúmenes no usados
docker volume prune

# Mover backups antiguos
mv uploads_backup_*.tar.gz ~/backups_antiguos/
```

### Contenedor no inicia (crashloop)

**Síntoma**: Contenedor se reinicia constantemente

**Solución**:

```bash
# Ver logs completos
docker logs active-ia-backend --tail 100

# Ver eventos del contenedor
docker events --filter container=active-ia-backend

# Acceder y debuggear (si el contenedor está vivo)
docker exec -it active-ia-backend bash

# Iniciar sin health check
docker-compose up --no-healthcheck
```

---

## Seguridad en Producción

### Checklist de seguridad

- [ ] Cambiar `SECRET_KEY` por valor fuerte (32+ caracteres)
- [ ] Cambiar `ENCRYPTION_KEY` (usar comando de generación)
- [ ] Configurar `CORS_ORIGINS` solo con dominio permitido
- [ ] Usar HTTPS en producción (certificado SSL/TLS)
- [ ] No exponer puerto de PostgreSQL (5432) al exterior
- [ ] Configurar firewall: permitir solo puertos 80/443
- [ ] Verificar que `.env` esté en `.gitignore`
- [ ] Backups automáticos configurados
- [ ] Monitoreo de logs activo

### Generar valores seguros

```bash
# SECRET_KEY (32 bytes = 64 caracteres hex)
openssl rand -hex 32

# ENCRYPTION_KEY (Fernet compatible)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Password seguro
openssl rand -base64 24
```

---

## Monitoreo

### Ver uso de recursos

```bash
# Ver CPU, memoria, red de todos los contenedores
docker stats

# Ver uso de un contenedor específico
docker stats active-ia-backend

# Ver espacio usado por volúmenes
docker system df -v
```

### Ver logs en producción

```bash
# Logs de todos los servicios (últimas 100 líneas)
docker-compose logs --tail 100

# Seguir logs en tiempo real
docker-compose logs -f

# Logs solo de errores
docker-compose logs | grep -i error

# Logs de un servicio con timestamp
docker-compose logs -f -t backend
```

---

## Desinstalación

### Eliminar todo (CUIDADO: datos se perderán)

```bash
# Detener servicios y eliminar contenedores
docker-compose down

# Eliminar también volúmenes (BORRA DATOS)
docker-compose down -v

# Eliminar imágenes
docker-compose down --rmi all

# Limpiar sistema completo
docker system prune -a --volumes
```

### Eliminar solo contenedores (mantener datos)

```bash
# Detener y eliminar contenedores
docker-compose down

# Los volúmenes persisten, al hacer up de nuevo tendrás los datos
docker-compose up -d
```

---

## Soporte

### Reportar problemas

Si encuentras problemas:

1. Revisar esta guía de troubleshooting
2. Revisar logs: `docker-compose logs`
3. Verificar configuración: `cat .env`
4. Crear issue en el repositorio con:
   - Descripción del problema
   - Logs relevantes
   - Pasos para reproducir
   - Versión de Docker

### Documentación adicional

- [Docker Compose reference](https://docs.docker.com/compose/)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- `EASYPANEL_DEPLOY.md` — deploy vigente (backend en EasyPanel + frontend en Vercel)

---

**¡Listo! Active-IA está desplegado y funcionando.** 🚀

Para acceder:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000/docs (Swagger)
