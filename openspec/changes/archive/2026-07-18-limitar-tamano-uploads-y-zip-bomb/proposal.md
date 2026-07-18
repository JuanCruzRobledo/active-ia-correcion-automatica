## Why

El backend define `MAX_UPLOAD_SIZE = 104857600` (100 MB) en `backend/app/core/config.py:93` pero **nunca lo usa**: un grep del símbolo no arroja resultados fuera de la propia declaración. Los endpoints de subida leen el archivo completo a RAM sin ningún chequeo de tamaño (`await archivo.read()` en subida individual y `await archivo_zip.read()` en carga masiva), y al descomprimir ZIPs se lee cada entrada con `zf.read(info)` sin mirar su tamaño descomprimido ni acotar la cantidad de entradas. Esto habilita dos abusos triviales sobre el boundary de entrada del sistema:

- **PERF-008 (alto):** un archivo grande legítimo o malicioso se materializa entero en memoria del proceso, pudiendo agotar la RAM y tumbar el backend (DoS por memoria).
- **SEC-005 (alto):** una "ZIP-bomb" clásica — un ZIP de ~100 KB que se expande a varios GB — se descomprime sin límite al consolidar el código, con el mismo efecto de agotamiento de memoria.

El límite ya está configurado; solo hace falta aplicarlo. Es un quick win de seguridad/robustez sin cambios de modelo de datos ni de contratos de API (salvo agregar un código de rechazo `413`).

## What Changes

- **Aplicar `settings.MAX_UPLOAD_SIZE` en subida individual** (`entrega_service.py`, endpoint `crear_entrega`): rechazar con `413 Request Entity Too Large` cuando el archivo supere el límite. Chequear el `Content-Length` del header como primera barrera barata y validar el tamaño real de los bytes leídos como barrera definitiva.
- **Aplicar el mismo límite en carga masiva** (`entrega_service.py`, endpoint de carga masiva por ZIP): rechazar el ZIP contenedor con `413` si supera `MAX_UPLOAD_SIZE`.
- **Protección anti ZIP-bomb en la consolidación** (`consolidacion_service.py`, `_consolidar_desde_zipfile` / `_scan_zip`): al iterar los `ZipInfo`, acumular `info.file_size` (tamaño **descomprimido**) y abortar con error controlado si el acumulado supera un tope; además, limitar la **cantidad total de entradas** del ZIP. El corte debe ocurrir ANTES de materializar todo el contenido en memoria.
- **Misma protección anti ZIP-bomb en el loop de carga masiva** (`entrega_service.py`, iteración de carpetas de alumnos dentro del ZIP): acumular tamaño descomprimido y cantidad de entradas, abortando de forma controlada.
- **Mensajes de error claros y accionables** (qué límite se superó y cuál es el tope), sin filtrar internals.
- **NO BREAKING** para clientes legítimos: los archivos por debajo del límite (el caso real: entregas de alumnos, típicamente pocos MB) siguen funcionando idénticamente.

**Fuera de scope (mencionado como mejora complementaria en design.md, no bloqueante):** fijar `client_max_body_size` en `nginx/nginx.conf` como segunda barrera de red. Se evalúa NO tocarlo aquí para no colisionar con el change `limpiar-n8n-deploy`, que ya edita `nginx.conf` (gobernanza ALTA sobre deploy compartido).

## Capabilities

### New Capabilities
- `upload-size-limits`: valida el tamaño de los archivos subidos contra `MAX_UPLOAD_SIZE` en ambos endpoints de subida (individual y masiva) y protege el pipeline de descompresión/consolidación de ZIPs contra ZIP-bombs (tope de tamaño descomprimido acumulado y de cantidad de entradas), abortando de forma controlada sin materializar contenido excesivo en memoria.

### Modified Capabilities
<!-- Ninguna spec existente cambia sus requisitos. La única spec vigente es `docker-local-env`, ajena a este change. -->

## Impact

- **Código (gobernanza MEDIA — validación de input en el boundary + pipeline de consolidación):**
  - `backend/app/services/entrega_service.py` — subida individual (~L136-137) y carga masiva (~L732 y loop L738-820).
  - `backend/app/services/consolidacion_service.py` — `_consolidar_desde_zipfile` (~L256-288) y `_scan_zip` (~L587-618).
  - `backend/app/core/config.py` — se reutiliza `MAX_UPLOAD_SIZE`; se puede agregar una constante para el tope de cantidad de entradas del ZIP (p. ej. `MAX_ZIP_ENTRIES`).
- **API:** nuevo código de respuesta `413` (o `400`) en los endpoints de subida; sin cambios en payloads de éxito.
- **Sin impacto en modelo de datos, migraciones ni frontend** (más allá de manejar el nuevo error, ya cubierto por el manejo de errores existente).
- **Esfuerzo estimado: S/M** — el más grande de los 7 quick wins de la auditoría: toca 2 servicios y 2 endpoints, más tests de subida y de ZIP-bomb.
- **Riesgo mitigado:** DoS por memoria vía archivo gigante (PERF-008) y vía ZIP-bomb (SEC-005), ambos clasificados **altos**.
