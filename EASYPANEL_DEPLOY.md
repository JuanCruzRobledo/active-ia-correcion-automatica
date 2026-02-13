# 🚀 Deployment en Easypanel

## Pasos para desplegar Active-IA en Easypanel

### 1️⃣ Configurar Variables de Entorno

En Easypanel, ve a tu proyecto → **Environment** y agrega estas variables:

#### **Variables OBLIGATORIAS:**

```env
# PostgreSQL
POSTGRES_DB=active_ia_db
POSTGRES_USER=active_ia_user
POSTGRES_PASSWORD=tu_password_seguro_123

# Backend Security
SECRET_KEY=genera_con_openssl_rand_hex_32
ENCRYPTION_KEY=genera_con_python_fernet

# N8N
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=tu_password_n8n_seguro

# CORS (tu dominio de Easypanel)
CORS_ORIGINS=["https://tu-proyecto.easypanel.host","https://*.easypanel.host"]

# Frontend API URL (relativa)
VITE_API_URL=/api/v1

# Webhook URL (tu dominio de Easypanel)
WEBHOOK_URL=https://tu-proyecto.easypanel.host/n8n
```

#### **Generar claves de seguridad:**

**En tu terminal local (Windows):**

```bash
# Para SECRET_KEY (usar Git Bash o WSL)
openssl rand -hex 32

# Para ENCRYPTION_KEY (si tienes Python)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Si no tienes OpenSSL, genera SECRET_KEY online:**
- https://generate-secret.vercel.app/32

---

### 2️⃣ Archivo Docker Compose

En Easypanel, usa el archivo: **`docker-compose.easypanel.yml`**

Este archivo ya está optimizado:
- ✅ Sin `container_name` (Easypanel lo gestiona)
- ✅ Sin `ports` en nginx (Traefik lo maneja)
- ✅ Sin `version` (obsoleto)
- ✅ Labels de Traefik configurados
- ✅ Validación de variables requeridas

---

### 3️⃣ Configuración de Rutas en Easypanel

Easypanel usa **Traefik** para el routing. El archivo ya incluye las labels necesarias:

- **Frontend**: `PathPrefix(/)`  → Todo el tráfico raíz
- **Backend**: `PathPrefix(/api)` → APIs
- **N8N**: `PathPrefix(/n8n)` → Workflows

**No necesitas configurar nada extra**, Traefik lo detectará automáticamente.

---

### 4️⃣ Deploy desde Git

1. En Easypanel, crea un nuevo **App** o **Service**
2. Selecciona **Source: Git**
3. Conecta tu repositorio
4. Selecciona el archivo: `docker-compose.easypanel.yml`
5. Configura las variables de entorno (paso 1)
6. Haz **Deploy**

---

### 5️⃣ Verificar Deployment

Después del deploy, verifica:

```bash
# 1. Ver logs del backend
# En Easypanel: Services → backend → Logs

# 2. Verificar health checks
# Todos los servicios deben mostrar "healthy"

# 3. Acceder a la aplicación
# https://tu-proyecto.easypanel.host/
```

**Endpoints para verificar:**
- Frontend: `https://tu-proyecto.easypanel.host/`
- API Docs: `https://tu-proyecto.easypanel.host/api/v1/docs`
- N8N: `https://tu-proyecto.easypanel.host/n8n/`

---

### 6️⃣ Configurar Dominio Personalizado (Opcional)

Si quieres usar tu propio dominio:

1. En Easypanel → **Domains**
2. Agrega tu dominio: `app.tudominio.com`
3. Easypanel generará certificado SSL automáticamente
4. Actualiza las variables de entorno:
   ```env
   CORS_ORIGINS=["https://app.tudominio.com"]
   WEBHOOK_URL=https://app.tudominio.com/n8n
   ```

---

## ⚠️ Troubleshooting

### Error: Variables no seteadas
```
The "SECRET_KEY" variable is not set
```
**Solución:** Configurar todas las variables OBLIGATORIAS en Environment

### Error: container_name conflicts
```
container_name is used in backend. It might cause conflicts
```
**Solución:** Usar `docker-compose.easypanel.yml` (no tiene container_name)

### Error: Build failed
**Solución:**
1. Verificar que el repositorio esté actualizado
2. Verificar que los Dockerfiles existan en `backend/` y `frontend/`
3. Ver logs de build en Easypanel

### Error: Backend no conecta con PostgreSQL
**Solución:**
1. Verificar que `POSTGRES_PASSWORD` esté configurado
2. Verificar logs de postgres: `Services → postgres → Logs`
3. Verificar que el servicio postgres esté "healthy"

### Error: Frontend muestra página en blanco
**Solución:**
1. Verificar que `VITE_API_URL=/api/v1` esté configurado
2. Ver logs del frontend
3. Verificar que el backend esté respondiendo en `/api/v1/health`

---

## 🔄 Actualizar la aplicación

Para actualizar después de hacer cambios:

1. Hacer push a tu repositorio Git
2. En Easypanel: **Redeploy** o **Rebuild**
3. Easypanel automáticamente:
   - Hace pull del código nuevo
   - Reconstruye las imágenes
   - Reinicia los servicios

---

## 📊 Monitoreo

Easypanel incluye:
- ✅ Logs en tiempo real
- ✅ Métricas de uso (CPU, RAM, Disco)
- ✅ Health checks automáticos
- ✅ Alertas de servicios caídos

Accede desde: **Dashboard → Tu Proyecto → Metrics**

---

## 🔐 Backups

### Backup de PostgreSQL en Easypanel:

**Opción 1: Backup manual**
```bash
# Conectar al contenedor de postgres
docker exec -it <postgres-container-id> pg_dump -U active_ia_user active_ia_db > backup.sql
```

**Opción 2: Usar volumen persistente**

Easypanel automáticamente crea volúmenes persistentes para:
- `postgres_data` → Base de datos
- `backend_uploads` → Archivos subidos
- `n8n_data` → Workflows de N8N

Estos volúmenes sobreviven a los redeploys.

---

## ✅ Checklist de Deployment

- [ ] Variables de entorno configuradas (SECRET_KEY, ENCRYPTION_KEY, etc.)
- [ ] Repositorio Git conectado a Easypanel
- [ ] Archivo `docker-compose.easypanel.yml` seleccionado
- [ ] Deploy exitoso (todos los servicios "healthy")
- [ ] Frontend accesible desde el navegador
- [ ] Backend API respondiendo en `/api/v1/docs`
- [ ] N8N accesible en `/n8n/`
- [ ] CORS configurado con tu dominio

---

## 🆘 Soporte

Si tienes problemas:
1. Revisa los **logs** en Easypanel (cada servicio tiene su pestaña de logs)
2. Verifica los **health checks** (deben estar en verde)
3. Revisa las **variables de entorno** (no deben estar vacías)

**Logs importantes:**
- Backend → `/api/v1/health` debe responder 200 OK
- Postgres → "database system is ready to accept connections"
- N8N → "Editor is now accessible"
