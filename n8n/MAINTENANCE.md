# Guía de Mantenimiento de Imagen N8N

Este documento detalla cómo actualizar workflows, modificar configuración o realizar mantenimiento en la imagen preconfigurada de N8N.

---

## 🧠 Antes de empezar: cómo está armada esta imagen

Dos cosas que tenés que entender o vas a perder tiempo (nosotros lo perdimos):

1. **La fuente de verdad es la data baked DENTRO de la propia imagen** (`/home/node/.n8n`), NO la carpeta `workflows/`. Los `.json` de `workflows/` son exports de referencia y pueden estar desactualizados respecto a lo que corre en producción.
2. **Toda la corrección vive en UN solo workflow** ("Correcion Automatica") que contiene los 4 webhooks adentro: `/webhook/corregir`, `/webhook/corregir-pdf`, `/webhook/generar-rubrica`, `/webhook/health`. No son 4 workflows separados.

> ### 🪟 CRÍTICO en Windows — NO uses bind-mount de `data/`
> El flujo viejo de esta guía montaba `-v ./data:/home/node/.n8n`. **Eso está ROTO en Windows + Docker Desktop.** SQLite en modo WAL sobre el filesystem de Windows (capa 9p/virtiofs) **rompe el registro de los webhooks de producción**: el workflow figura como activo pero los webhooks devuelven **404**.
> Comprobado con la misma data y versión: con bind-mount → 404; con la data baked (sin mount) → 200.
> **En Windows: editá con almacenamiento INTERNO del contenedor y extraé la data con `docker cp`** (FASE 1 abajo).

---

## 🔄 Flujo de Trabajo para Actualizar Workflows

```
┌─────────────────────────────────────────────────────────────┐
│  FASE 1: Edición Local (Windows-safe, SIN bind-mount)       │
│  1. Levantar N8N desde TU imagen actual (storage interno)   │
│  2. Editar el workflow en http://localhost:5678 + Guardar   │
│  3. Extraer la data: docker cp -> ./data                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 2: Build & Push                                       │
│  4. (opcional) Backup local de la imagen actual             │
│  5. docker build -f Dockerfile.preconfigured                │
│  6. Probar la imagen NUEVA (webhooks 200) y pushear         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 3: Despliegue                                         │
│  7. docker-compose pull n8n (o "force pull" en EasyPanel)   │
│  8. docker-compose up -d --force-recreate n8n               │
└─────────────────────────────────────────────────────────────┘
```

> **Git Bash en Windows:** corré `export MSYS_NO_PATHCONV=1` al inicio para que no convierta las rutas de contenedor (`/home/node/...`, `/tmp/...`) al pasarlas a `docker cp`/`docker exec`.

---

## FASE 1: Edición Local (Windows-safe)

### 1. Levantar N8N desde TU imagen actual (storage interno)

Para **actualizar** hay que partir de la imagen que YA tiene tus workflows, no de la imagen vacía. Sin bind-mount: el contenedor usa su almacenamiento interno (donde todo funciona bien).

```bash
# Asegurate de no tener una instancia previa
docker rm -f n8n-edit

# Levantar TU imagen actual (no n8nio/n8n vacío) — storage interno, sin -v
docker run -d \
  --name n8n-edit \
  -p 5678:5678 \
  -e N8N_USER_MANAGEMENT_DISABLED=true \
  -e N8N_BASIC_AUTH_ACTIVE=false \
  -e N8N_SECURE_COOKIE=false \
  juancruzrobledo/n8n-active-ia:latest
```

> `N8N_USER_MANAGEMENT_DISABLED=true` evita la pantalla de "creá tu cuenta de owner" que la imagen base n8n 2.x muestra por defecto.

### 2. Realizar Cambios

Accede a: http://localhost:5678 → vas a ver tu workflow **"Correcion Automatica"** ya cargado y activo.

**Cambios típicos:**
- Editar nodos del workflow existente
- Ajustar timeouts
- Modificar prompts de Gemini
- Cambiar configuración de webhooks

**Por cada cambio:** **Save** (esperá el "Saved") y dejá el workflow **ACTIVO** (toggle verde). Si lo dejás inactivo, sus webhooks no se registran.

### 3. Extraer la data y finalizar

Detené el contenedor (n8n hace checkpoint del WAL al apagar) y extraé la data al host con `docker cp`:

```bash
# Frenar para un checkpoint limpio de SQLite
docker stop n8n-edit

# Extraer la data baked -> ./data (lo que el Dockerfile va a copiar)
rm -rf data && mkdir -p data
docker cp n8n-edit:/home/node/.n8n/. ./data/
```

Ahora `./data` tiene tus cambios y está lista para el build.

---

## FASE 2: Build & Push

### Opción A: Script Automático (Recomendado)

Abre una terminal de Git Bash o cualquier shell con bash.

Navega a la carpeta `n8n/`:
```bash
cd n8n/
```

Ejecuta el script:
```bash
./build-image.sh
```

Sigue las instrucciones del script:
1. Ingresa el nombre de la imagen (ej: `tuusuario/n8n-active-ia`)
2. Tag (ej: `v1.1` para versión actualizada, o `latest`)
3. Cuando pregunte si pushear, selecciona **Sí/Yes**

Esto actualizará la imagen en Docker Hub.

### Opción B: Comandos Manuales (recomendado en Windows)

```bash
export MSYS_NO_PATHCONV=1   # Git Bash en Windows

# 0) Backup local de la imagen actual (red de seguridad para rollback)
docker tag juancruzrobledo/n8n-active-ia:latest juancruzrobledo/n8n-active-ia:backup-pre-update

# 1) Build (la data viene de FASE 1, ya está en ./data)
docker build -t juancruzrobledo/n8n-active-ia:latest -f Dockerfile.preconfigured .

# 2) PROBAR la imagen NUEVA antes de pushear (data baked, SIN mount)
docker rm -f n8n-test 2>/dev/null
docker run -d --name n8n-test -p 5680:5678 \
  -e N8N_USER_MANAGEMENT_DISABLED=true -e N8N_BASIC_AUTH_ACTIVE=false -e N8N_SECURE_COOKIE=false \
  juancruzrobledo/n8n-active-ia:latest
# esperá ~15s y verificá que los 4 webhooks den 200:
for p in corregir corregir-pdf generar-rubrica health; do
  curl -s -o /dev/null -w "/webhook/$p -> %{http_code}\n" -X POST http://localhost:5680/webhook/$p -H "Content-Type: application/json" -d '{}'
done
docker rm -f n8n-test

# 3) Recién si dieron 200, pushear
docker push juancruzrobledo/n8n-active-ia:latest
```

> **Rollback:** si la nueva falla, `docker tag juancruzrobledo/n8n-active-ia:backup-pre-update juancruzrobledo/n8n-active-ia:latest && docker push juancruzrobledo/n8n-active-ia:latest`.

> **Nota sobre `build-image.sh`:** la Opción A sirve, pero su flujo asume que vos poblaste `./data` con bind-mount (FASE 1 vieja). En Windows usá la Opción B, que parte de la `./data` extraída con `docker cp`.

---

## FASE 3: Despliegue

> **⚠️ `:latest` es un tag MUTABLE.** El destino (`:latest`) es correcto, pero el deploy tiene que **bajar** la imagen nueva, no usar la cacheada. Forzá el pull (`docker-compose pull`, o en **EasyPanel**: "Force rebuild" / "Pull latest image", o pull policy `always`).
>
> **Confirmar que corre la nueva** comparando digests:
> ```bash
> docker inspect juancruzrobledo/n8n-active-ia:latest --format '{{index .RepoDigests 0}}'
> ```
> El digest tiene que coincidir con el que reportó tu último `docker push`.

### En Desarrollo Local

Si tienes el proyecto corriendo localmente:

```powershell
# 1. Descargar la versión más reciente (forzado)
docker-compose pull n8n

# 2. Recrear el contenedor con la nueva imagen
docker-compose up -d --force-recreate n8n

# 3. Verificar que levantó correctamente
docker-compose logs -f n8n
```

### En Producción

Si tienes el proyecto en un servidor:

```bash
# SSH al servidor
ssh usuario@servidor

# Navegar al proyecto
cd /path/to/active-ia

# Actualizar imagen
docker-compose pull n8n

# Recrear contenedor (sin downtime si usas replicas)
docker-compose up -d n8n

# Verificar logs
docker-compose logs -f n8n
```

---

## 🛠️ Casos de Uso Comunes

### Caso 1: Ajustar Timeout de Corrección

**Problema:** Las correcciones de código largo están tardando más de 90 segundos.

**Solución:**
1. Levantar N8N en modo config
2. Abrir workflow "Corrección Automática"
3. Seleccionar nodo "HTTP Request" (Gemini)
4. Cambiar timeout de `90000` a `120000`
5. Guardar workflow
6. Detener N8N, rebuild imagen, deploy

### Caso 2: Modificar Prompt de Gemini

**Problema:** El feedback de Gemini es muy genérico.

**Solución:**
1. Levantar N8N en modo config
2. Abrir workflow "Corrección Automática"
3. Editar nodo "Code (Preparar Prompt)"
4. Ajustar el texto del prompt:
   ```javascript
   const prompt = `Eres un evaluador de código...

   IMPORTANTE: Sé específico en el feedback, menciona líneas de código concretas.
   ...`;
   ```
5. Guardar, detener, rebuild, deploy

### Caso 3: Agregar Nuevo Workflow

**Problema:** Necesitas un nuevo endpoint para validar código antes de corregir.

**Solución:**
1. Levantar N8N en modo config
2. Crear nuevo workflow "Validación de Código"
3. Agregar nodo Webhook con path `/webhook/validar`
4. Agregar lógica de validación
5. Activar workflow
6. Detener, rebuild, deploy

---

## 📊 Versionado de Imágenes

### Estrategia Recomendada

- `latest`: Última versión estable (siempre actualizada)
- `v1.0`, `v1.1`, etc.: Versiones específicas para rollback

**Ejemplo:**
```bash
# Build versión nueva
docker build -t tuusuario/n8n-active-ia:v1.2 -f Dockerfile.preconfigured .

# Tag como latest también
docker tag tuusuario/n8n-active-ia:v1.2 tuusuario/n8n-active-ia:latest

# Push ambos tags
docker push tuusuario/n8n-active-ia:v1.2
docker push tuusuario/n8n-active-ia:latest
```

### Rollback a Versión Anterior

Si una actualización falla, volver a versión anterior:

```yaml
# docker-compose.yml
services:
  n8n:
    image: tuusuario/n8n-active-ia:v1.1  # Versión anterior que funcionaba
```

```bash
docker-compose up -d n8n
```

---

## 🐛 Troubleshooting

### Error: "Permission denied" al levantar N8N

**Causa:** Permisos incorrectos en `data/`.

**Solución:**
```powershell
docker run --rm -v "${PWD}/data:/data" alpine chown -R 1000:1000 /data
```

### Error: "data/ is empty" al buildear

**Causa:** No se configuró N8N antes de buildear.

**Solución:** Seguir FASE 1 completa antes de buildear.

### Workflows no aparecen después de actualizar imagen

**Causa:** La imagen no se actualizó correctamente o el volumen local sobrescribe la imagen.

**Solución:**
```bash
# NO montar volumen en producción
# Quitar esta línea de docker-compose.yml:
# volumes:
#   - ./n8n/data:/home/node/.n8n

# Recrear contenedor
docker-compose up -d --force-recreate n8n
```

### Webhooks dan 404 aunque el workflow figura "Activated" (Windows)

**Causa:** Estás corriendo n8n con **bind-mount de `data/`** en Windows. SQLite (modo WAL) sobre el filesystem de Windows rompe el registro de webhooks de producción. El log dice "Activated workflow" pero igual responde 404.

**Solución:** No uses bind-mount en Windows. Seguí la **FASE 1 (Windows-safe)**: storage interno + `docker cp`. La imagen baked (sin mount) registra los webhooks bien.

### Webhooks no responden después de actualizar

**Causa:** Workflows desactivados, cambio en paths, o el deploy levantó la imagen vieja cacheada (`:latest` mutable).

**Solución:**
1. Acceder a http://localhost:5678 (en dev) y verificar toggle verde (activado)
2. Confirmar que el deploy bajó la imagen nueva (comparar digest, ver FASE 3)
3. Revisar logs: `docker-compose logs -f n8n`

---

## 📝 Checklist de Actualización

- [ ] Código backup de `data/` antes de editar (opcional)
- [ ] Permisos arreglados (Windows)
- [ ] N8N levantado en modo config
- [ ] Cambios realizados y probados con curl
- [ ] Workflows activados (toggle verde)
- [ ] N8N detenido correctamente
- [ ] Imagen buildeada con nuevo tag
- [ ] Imagen pusheada a Docker Hub
- [ ] Tag `latest` actualizado
- [ ] `docker-compose.yml` actualizado (si cambió tag)
- [ ] Deploy ejecutado (`docker-compose pull && up -d`)
- [ ] Logs verificados (sin errores)
- [ ] Webhooks probados desde backend

---

## 🔗 Recursos

- **README principal:** Ver `README.md` en esta carpeta
- **Documentación N8N:** https://docs.n8n.io/
- **Especificación de integraciones:** `docs/specs/10-INTEGRACIONES.md`
- **Docker Hub:** https://hub.docker.com/ (donde se publica la imagen)

---

## 💡 Mejores Prácticas

1. **Siempre probar cambios localmente** antes de pushear imagen
2. **Usar tags versionados** para poder hacer rollback
3. **Documentar cambios** en commits/changelog
4. **No exponer puerto 5678** en producción (solo red interna)
5. **Backup de `data/`** antes de actualizaciones importantes
6. **Probar webhooks** con curl después de cada actualización
