# 🚀 Deployment: Backend en Easypanel + Frontend en Vercel

## 🗺️ Topología de deploy vigente

```
Navegador
   │
   ├── Frontend  → Vercel (build estático de Vite, SIN Docker)
   │                  └── llama al backend vía VITE_API_URL
   │
   └── Backend   → Easypanel, app service construido desde `backend/Dockerfile`
                      ├── PostgreSQL (vía DATABASE_URL)
                      └── IA: llamada DIRECTA a Gemini / OpenRouter
                             con la API key de cada usuario (cifrada AES-256)
```

Puntos clave:

- **Backend**: se despliega como **app service** de Easypanel, construido directo desde
  `backend/Dockerfile` (no se usa un compose para esto). El contenedor escucha en el
  puerto **80**, corre `alembic upgrade head` al arrancar y expone health en `/api/v1/health`.
- **Frontend**: se despliega en **Vercel**, sin Docker. La config vive en `frontend/vercel.json`
  (framework `vite`, build `npm run build`, output `dist`, SPA rewrite a `/index.html`).
- **IA**: **no hay orquestador externo ni servicio intermedio**. El backend llama directo al
  proveedor (Gemini/OpenRouter) usando la API key que cada usuario carga en su perfil, guardada
  cifrada con AES-256 (`ENCRYPTION_KEY`).
- **`docker-compose.prod.yml` / `docker-compose.easypanel.yml`**: quedan como **alternativa
  self-hosted** para levantar todo el stack en un VPS propio. No son el camino principal.
  Ver [DEPLOYMENT.md](./DEPLOYMENT.md).

---

## 🐍 Backend en Easypanel

### 1️⃣ Crear el app service

1. En Easypanel, creá un **App**
2. **Source: Git** → conectá el repositorio
3. **Build: Dockerfile** → path `backend/Dockerfile`, build context `backend/`
4. Configurá las variables de entorno (paso 2)
5. **Deploy**

El `CMD` del Dockerfile ya aplica las migraciones (`alembic upgrade head`) antes de levantar
uvicorn, así que no hace falta un paso manual de migración en cada deploy.

---

### 2️⃣ Variables de entorno del backend

En Easypanel: tu app → **Environment**.

#### **Variables OBLIGATORIAS:**

```env
# Base de datos (Postgres accesible desde el backend)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/active_ia_db

# Seguridad
SECRET_KEY=genera_con_openssl_rand_hex_32
ENCRYPTION_KEY=genera_con_python_fernet

# CORS: el dominio del frontend en Vercel
CORS_ORIGINS=["https://tu-app.vercel.app"]
```

> ⚠️ El backend **aborta el arranque** si en producción (`DEBUG=False`) `SECRET_KEY` o
> `ENCRYPTION_KEY` conservan los valores placeholder del repo. Generalos de verdad.
>
> ⚠️ `ENCRYPTION_KEY` cifra las API keys de IA de los usuarios: si la cambiás, las keys ya
> guardadas dejan de poder descifrarse.

#### **Generar claves de seguridad:**

```bash
# SECRET_KEY (Git Bash o WSL en Windows)
openssl rand -hex 32

# ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### **Opcionales** (tienen default en `backend/app/core/config.py`):

```env
GEMINI_MODEL=gemini-3.5-flash
OPENROUTER_MODEL=google/gemini-3.5-flash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
UPLOAD_DIR=/app/uploads
LOG_LEVEL=INFO
```

> La API key de IA **no es una variable de entorno**: la carga cada usuario desde su perfil.

---

### 3️⃣ Dominio del backend

1. En Easypanel → **Domains**, asignale un dominio a la app del backend
2. Easypanel genera el certificado SSL automáticamente
3. Ese dominio es el que va en `VITE_API_URL` del frontend

---

## ▲ Frontend en Vercel

### 4️⃣ Crear el proyecto

1. En Vercel, importá el repositorio
2. **Root Directory**: `frontend`
3. El resto lo toma de `frontend/vercel.json` (framework `vite`, `npm ci`, `npm run build`,
   output `dist`)

### 5️⃣ Variables de entorno del frontend

```env
VITE_API_URL=https://tu-backend.easypanel.host/api/v1
```

Es una variable de **build** de Vite: si la cambiás, hay que **redeploy** para que tome efecto.

Acordate de que ese dominio de Vercel tiene que estar en el `CORS_ORIGINS` del backend.

---

### 6️⃣ Verificar el deployment

**Backend (Easypanel):**
- Logs: tu app → **Logs**
- Health: `https://tu-backend.easypanel.host/api/v1/health` → 200 OK
- API Docs: `https://tu-backend.easypanel.host/api/v1/docs`

**Frontend (Vercel):**
- `https://tu-app.vercel.app/` carga la SPA
- En el navegador (DevTools → Network) las llamadas salen contra `VITE_API_URL` y no dan CORS

---

## ⚠️ Troubleshooting

### Error: Variables no seteadas
```
The "SECRET_KEY" variable is not set
```
**Solución:** Configurar todas las variables OBLIGATORIAS en Environment

### Error: el backend no arranca por secretos placeholder
```
Arranque abortado: hay secretos con valor placeholder en produccion
```
**Solución:** Generar `SECRET_KEY` y `ENCRYPTION_KEY` reales (ver paso 2)

### Error: Build failed
**Solución:**
1. Verificar que el repositorio esté actualizado
2. Verificar que el build apunte a `backend/Dockerfile` con context `backend/`
3. Ver logs de build en Easypanel

### Error: Backend no conecta con PostgreSQL
**Solución:**
1. Verificar `DATABASE_URL` (host, puerto, credenciales, nombre de la BD)
2. Verificar que el backend tenga alcance de red hacia esa BD
3. Ver los logs de arranque: si falla `alembic upgrade head`, es conexión

### Error: Frontend muestra página en blanco / no llega al backend
**Solución:**
1. Verificar `VITE_API_URL` en Vercel (y **redeploy**: es variable de build)
2. Verificar que el dominio de Vercel esté en `CORS_ORIGINS` del backend
3. Verificar que el backend responda en `/api/v1/health`

### Error: falla la corrección con IA
**Solución:**
1. Verificar que el usuario tenga cargada su API key en el perfil
2. Verificar que `ENCRYPTION_KEY` no haya cambiado desde que se guardó esa key
3. Ver los logs del backend: la llamada a Gemini/OpenRouter sale desde ahí

---

## 🔄 Actualizar la aplicación

Para actualizar después de hacer cambios:

1. Hacer push a tu repositorio Git
2. **Backend** → en Easypanel: **Redeploy** o **Rebuild** (pull del código, rebuild de la imagen,
   `alembic upgrade head` en el arranque, restart)
3. **Frontend** → Vercel redeploya solo con el push a la rama conectada

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

### Base de datos

```bash
# Dump del Postgres al que apunta DATABASE_URL
pg_dump "$DATABASE_URL" > backup.sql
```

### Archivos subidos (entregas)

El backend guarda los uploads en `UPLOAD_DIR` (default `/app/uploads` dentro del contenedor).
Ese directorio necesita un **volumen persistente** en Easypanel para sobrevivir a los redeploys.

El frontend en Vercel no tiene estado: no requiere backup.

---

## ✅ Checklist de Deployment

**Backend (Easypanel):**
- [ ] App creada desde `backend/Dockerfile` (context `backend/`)
- [ ] `DATABASE_URL` apuntando a un Postgres alcanzable
- [ ] `SECRET_KEY` y `ENCRYPTION_KEY` generados (no placeholders)
- [ ] `CORS_ORIGINS` con el dominio de Vercel
- [ ] Volumen persistente montado en `UPLOAD_DIR`
- [ ] `/api/v1/health` responde 200 OK
- [ ] `/api/v1/docs` accesible

**Frontend (Vercel):**
- [ ] Root Directory = `frontend`
- [ ] `VITE_API_URL` apuntando al backend
- [ ] Build exitoso y SPA cargando
- [ ] Login funcionando (sin errores de CORS en la consola)

---

## 🆘 Soporte

Si tienes problemas:
1. Revisa los **logs** en Easypanel (backend) y en Vercel (build del frontend)
2. Verifica los **health checks** (deben estar en verde)
3. Revisa las **variables de entorno** (no deben estar vacías)

**Logs importantes:**
- Backend → `/api/v1/health` debe responder 200 OK
- Backend → `alembic upgrade head` debe completar sin error en el arranque
- Postgres → "database system is ready to accept connections"
