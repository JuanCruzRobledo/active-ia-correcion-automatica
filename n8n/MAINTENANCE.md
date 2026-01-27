# Guía de Mantenimiento de Imagen N8N

Este documento detalla cómo actualizar workflows, modificar configuración o realizar mantenimiento en la imagen preconfigurada de N8N.

---

## 🔄 Flujo de Trabajo para Actualizar Workflows

```
┌─────────────────────────────────────────────────────────────┐
│  FASE 1: Edición Local                                      │
│  1. Preparar permisos (Windows)                             │
│  2. Levantar N8N en modo config                             │
│  3. Editar workflows en http://localhost:5678               │
│  4. Detener N8N (cambios guardados en data/)                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 2: Build & Push                                       │
│  5. Ejecutar ./build-image.sh                               │
│  6. Pushear a Docker Hub                                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 3: Despliegue                                         │
│  7. docker-compose pull n8n                                 │
│  8. docker-compose up -d n8n                                │
└─────────────────────────────────────────────────────────────┘
```

---

## FASE 1: Edición Local

### 1. Preparar Permisos (Solo Windows)

**Contexto:** En Windows, al detener contenedores, los archivos de base de datos a veces quedan bloqueados o con permisos de _root_, lo que impide que N8N arranque de nuevo.

**Solución:** Ejecuta este comando en PowerShell (estando en la carpeta `n8n/`) para asignar los permisos correctos al usuario `node` (ID 1000).

```powershell
docker run --rm -v "${PWD}/data:/data" alpine chown -R 1000:1000 /data
```

### 2. Levantar N8N en Modo Configuración

Ejecuta el contenedor N8N montando tu carpeta local `data/`.

```powershell
# Asegúrate de no tener una instancia previa
docker rm -f n8n-config

# Iniciar contenedor sin autenticación para editar
docker run -d `
  --name n8n-config `
  -p 5678:5678 `
  -e N8N_BASIC_AUTH_ACTIVE=false `
  -v "${PWD}/data:/home/node/.n8n" `
  n8nio/n8n:latest
```

### 3. Realizar Cambios

Accede a: http://localhost:5678

**Cambios típicos:**
- Editar nodos de workflows existentes
- Ajustar timeouts
- Modificar prompts de Gemini
- Agregar nuevos workflows
- Cambiar configuración de webhooks

**⚠️ Importante:** Todo lo que hagas se está guardando en tu carpeta local `data/`.

### 4. Finalizar Edición

Una vez terminados los cambios, detén y elimina el contenedor para liberar la base de datos y permitir que la imagen se construya correctamente.

```powershell
docker stop n8n-config
docker rm n8n-config
```

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

### Opción B: Comandos Manuales

Si prefieres construir manualmente:

```bash
# Build
docker build -t tuusuario/n8n-active-ia:v1.1 -f Dockerfile.preconfigured .

# Push
docker push tuusuario/n8n-active-ia:v1.1

# También actualizar tag 'latest'
docker tag tuusuario/n8n-active-ia:v1.1 tuusuario/n8n-active-ia:latest
docker push tuusuario/n8n-active-ia:latest
```

---

## FASE 3: Despliegue

### En Desarrollo Local

Si tienes el proyecto corriendo localmente:

```powershell
# 1. Descargar la versión más reciente
docker-compose pull n8n

# 2. Recrear el contenedor con la nueva imagen
docker-compose up -d n8n

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

### Webhooks no responden después de actualizar

**Causa:** Workflows desactivados o cambio en paths.

**Solución:**
1. Acceder a http://localhost:5678 (en dev)
2. Verificar que workflows tengan toggle verde (activados)
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
