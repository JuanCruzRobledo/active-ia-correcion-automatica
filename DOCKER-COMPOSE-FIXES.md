# Docker Compose - Cambios Realizados

## 📋 Resumen

Los archivos `docker-compose.yml` y `docker-compose.local.yml` tenían configuraciones incorrectas que impedirían que el sistema funcionara con los nuevos workflows de N8N. **Todos los problemas han sido corregidos**.

---

## ❌ Problemas Encontrados y Solucionados

### 1. **Variables de entorno con nombres incorrectos**

#### Antes (❌ INCORRECTO):
```yaml
# docker-compose.yml y docker-compose.local.yml
environment:
  N8N_WEBHOOK_BASE_URL: http://n8n:5678              # ❌ nombre diferente al backend
  N8N_CORRECTION_WEBHOOK: /webhook/corregir-individual  # ❌ endpoint antiguo
  N8N_RUBRIC_WEBHOOK: /webhook/rubrica                  # ❌ endpoint antiguo
```

#### Después (✅ CORRECTO):
```yaml
environment:
  N8N_BASE_URL: http://n8n:5678                          # ✅ coincide con backend
  N8N_WEBHOOK_CORRECCION: http://n8n:5678/webhook/corregir        # ✅ endpoint nuevo
  N8N_WEBHOOK_RUBRICA: http://n8n:5678/webhook/generar-rubrica   # ✅ endpoint nuevo
  N8N_WEBHOOK_HEALTH: http://n8n:5678/webhook/health              # ✅ agregado
  N8N_TIMEOUT_SECONDS: 90                                # ✅ agregado
```

**Razón:** El backend en `config.py` espera `N8N_BASE_URL` y los workflows nuevos usan `/webhook/corregir` y `/webhook/generar-rubrica`.

---

### 2. **Health check del backend apuntaba a ruta incorrecta**

#### Antes (❌ INCORRECTO):
```yaml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:80/health"]  # ❌
```

#### Después (✅ CORRECTO):
```yaml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:80/api/v1/health"]  # ✅
```

**Razón:** El backend define el health endpoint en `main.py` línea 78 como `/api/v1/health`.

---

### 3. **Faltaba montar workflows en N8N**

#### Antes (❌ FALTANTE):
```yaml
n8n:
  volumes:
    - n8n_data:/home/node/.n8n
    # ❌ Sin montaje de workflows
```

#### Después (✅ CORRECTO):
```yaml
n8n:
  volumes:
    - n8n_data:/home/node/.n8n
    # Montar workflows para fácil importación (read-only)
    - ./n8n/workflows:/workflows:ro  # ✅ agregado
```

**Razón:** Facilita la importación manual de workflows. Los archivos estarán disponibles en `/workflows` dentro del container de N8N.

---

### 4. **Agregada persistencia de ejecuciones exitosas**

#### Antes (❌ INCOMPLETO):
```yaml
n8n:
  environment:
    EXECUTIONS_DATA_PRUNE: true
    EXECUTIONS_DATA_MAX_AGE: 168
    # ❌ Sin configuración de guardado
```

#### Después (✅ CORRECTO):
```yaml
n8n:
  environment:
    EXECUTIONS_DATA_PRUNE: true
    EXECUTIONS_DATA_MAX_AGE: 168
    EXECUTIONS_DATA_SAVE_ON_SUCCESS: all  # ✅ agregado
```

**Razón:** Permite revisar historial de correcciones para debugging y auditoría.

---

### 5. **Variables adicionales agregadas al backend**

Se agregaron al `environment` del servicio `backend`:

```yaml
# Seguridad (actualizadas a nombres correctos)
SECRET_KEY: ${SECRET_KEY}                      # antes: JWT_SECRET
ALGORITHM: HS256                               # agregado
ACCESS_TOKEN_EXPIRE_DAYS: ${...:-7}           # antes: JWT_EXPIRES_IN

# CORS (actualizado)
CORS_ORIGINS: ${CORS_ORIGINS:-["http://..."]} # antes: CORS_ORIGIN (singular)

# Archivos (actualizados)
UPLOAD_DIR: /app/uploads                       # antes: UPLOAD_PATH
ALLOWED_EXTENSIONS: ${...:-[".zip",".txt"]}   # agregado

# Logging
DEBUG: ${DEBUG:-false}                         # agregado
```

**Razón:** Coinciden con los nombres que el backend espera en `config.py`.

---

## ✅ Archivos Actualizados

### 1. `docker-compose.yml`
- ✅ Corregidas variables de N8N
- ✅ Corregido health check del backend
- ✅ Agregado montaje de workflows
- ✅ Agregadas variables faltantes

### 2. `docker-compose.local.yml`
- ✅ Corregidas variables de N8N
- ✅ Corregido health check del backend
- ✅ Agregado montaje de workflows
- ✅ Agregadas variables faltantes
- ✅ Actualizada DATABASE_URL para PostgreSQL local

### 3. `.env.example`
- ✅ Actualizados nombres de variables de N8N
- ✅ Agregada variable `N8N_WEBHOOK_HEALTH`
- ✅ Agregada variable `N8N_TIMEOUT_SECONDS`
- ✅ Cambiado `N8N_WEBHOOK_BASE_URL` → `N8N_BASE_URL`

---

## 🚀 Cómo Usar

### Desarrollo Local (con PostgreSQL local)

```bash
# 1. Copiar .env.example a .env
cp .env.example .env

# 2. Editar .env con valores reales (especialmente SECRET_KEY y ENCRYPTION_KEY)

# 3. Levantar servicios
docker-compose -f docker-compose.local.yml up -d

# 4. Ver logs
docker-compose -f docker-compose.local.yml logs -f

# 5. Acceder a:
# - Backend: http://localhost:5000
# - Frontend: http://localhost:3000
# - N8N: http://localhost:5678 (usuario: admin)
```

### Producción/Híbrido (con BD en la nube)

```bash
# 1. Copiar .env.example a .env
cp .env.example .env

# 2. Configurar DATABASE_URL con tu base de datos en la nube

# 3. Levantar servicios
docker-compose up -d

# 4. Ver logs
docker-compose logs -f
```

---

## 📝 Tareas Post-Deploy

### 1. Importar Workflows en N8N

**Opción A: Vía UI (primera vez)**
1. Acceder a http://localhost:5678
2. Login con usuario configurado en `.env`
3. Ir a **Workflows** → **Import from File**
4. Importar cada archivo:
   - `/workflows/correccion-workflow.json`
   - `/workflows/health-check-workflow.json`
   - `/workflows/generar-rubrica-workflow.json`
5. **Activar cada workflow**

**Opción B: Vía CLI (automático)**
```bash
# Copiar workflows al container
docker exec -it active-ia-n8n sh -c "cp /workflows/*.json /home/node/.n8n/"

# Reiniciar N8N para que los detecte
docker-compose restart n8n
```

### 2. Generar Claves de Seguridad

```bash
# SECRET_KEY (JWT)
openssl rand -hex 32

# ENCRYPTION_KEY (Fernet para API Keys de Gemini)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Actualizar estos valores en `.env`.

### 3. Configurar Usuario Admin en Backend

```bash
# Entrar al container del backend
docker exec -it active-ia-backend bash

# Crear usuario admin (si existe script de creación)
python -m app.scripts.create_admin

# O usar la API
curl -X POST http://localhost:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@activeai.com",
    "password": "admin123",
    "nombre": "Admin",
    "apellido": "Sistema",
    "rol": "ADMIN"
  }'
```

### 4. Verificar Conectividad

```bash
# Health check del backend
curl http://localhost:5000/api/v1/health

# Health check de N8N (requiere API key de Gemini configurada)
curl -X POST http://localhost:5000/api/v1/correcciones/health \
  -H "Authorization: Bearer <tu-token-jwt>"
```

---

## 🔍 Validación de Servicios

### Backend
```bash
# Verificar que está corriendo
docker ps | grep backend

# Ver logs
docker logs active-ia-backend -f

# Entrar al container
docker exec -it active-ia-backend bash
```

### N8N
```bash
# Verificar que está corriendo
docker ps | grep n8n

# Ver logs
docker logs active-ia-n8n -f

# Listar workflows importados (dentro del container)
docker exec -it active-ia-n8n ls -la /home/node/.n8n/
```

### PostgreSQL (solo en modo local)
```bash
# Conectarse a la base de datos
docker exec -it active-ia-postgres psql -U postgres -d active_ia_db

# Ver tablas
\dt

# Salir
\q
```

---

## 🛑 Troubleshooting

### Error: "N8N no responde"

**Síntoma:** Backend muestra `N8NTimeoutError`

**Solución:**
```bash
# Verificar que N8N está corriendo
docker ps | grep n8n

# Ver logs de N8N
docker logs active-ia-n8n

# Verificar health de N8N
curl http://localhost:5678/healthz

# Reiniciar N8N
docker-compose restart n8n
```

### Error: "Backend health check fails"

**Síntoma:** Container backend no pasa el healthcheck

**Solución:**
```bash
# Ver logs del backend
docker logs active-ia-backend

# Verificar que responde en /api/v1/health
docker exec -it active-ia-backend curl http://localhost:80/api/v1/health

# Si falla, verificar variables de entorno
docker exec -it active-ia-backend env | grep -E "DATABASE_URL|N8N"
```

### Error: "No se pueden importar workflows"

**Síntoma:** N8N no muestra los workflows montados

**Solución:**
```bash
# Verificar que el volumen está montado
docker inspect active-ia-n8n | grep -A 10 Mounts

# Verificar que los archivos existen en el host
ls -la ./n8n/workflows/

# Copiar manualmente al container
docker cp ./n8n/workflows/correccion-workflow.json active-ia-n8n:/home/node/.n8n/
```

---

## 📊 Comparación con Proyecto Antiguo

| Aspecto | Proyecto Antiguo | Proyecto Nuevo |
|---------|------------------|----------------|
| **Base de datos** | MongoDB Atlas | PostgreSQL (local o nube) |
| **Backend** | Node.js/Express | FastAPI (Python) |
| **Workflow corrección** | `/webhook/corregir-individual` | `/webhook/corregir` |
| **Workflow rúbricas** | `/webhook/rubrica` | `/webhook/generar-rubrica` |
| **API Keys Gemini** | Backend descargaba archivo | Backend envía código directo |
| **Input corrección** | `{submission_id, ...}` | `{codigo, rubrica, ...}` |
| **Health check** | ❌ No existía | ✅ `/webhook/health` |

---

## ✅ Resumen Final

**Estado actual:** ✅ **LISTO PARA USAR**

- ✅ Variables de entorno corregidas
- ✅ Endpoints de N8N actualizados
- ✅ Health checks arreglados
- ✅ Workflows montados en N8N
- ✅ Documentación actualizada

**Próximo paso:** Levantar los servicios con `docker-compose up -d` e importar los workflows en N8N.

---

**Última actualización:** 2026-02-06
**Autor:** Claude Sonnet 4.5
