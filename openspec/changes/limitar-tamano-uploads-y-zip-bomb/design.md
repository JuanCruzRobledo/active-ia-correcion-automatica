## Context

`backend/app/core/config.py:93` define `MAX_UPLOAD_SIZE: int = 104857600` (100 MB) pero un grep del símbolo confirma que **no se usa en ningún lado** salvo su propia declaración. Los dos endpoints de subida leen el archivo completo a RAM sin chequear tamaño:

- Subida individual — `entrega_service.py:136-137`: `contenido_bytes = await archivo.read()` y luego `_procesar_contenido(...)`.
- Carga masiva — `entrega_service.py:732`: `contenido_bytes = await archivo_zip.read()`, seguido de `zipfile.ZipFile(io.BytesIO(contenido_bytes))` y el loop de carpetas de alumnos (L738-820) que hace `zip_file.read(...)` por entrada.

La consolidación de código descomprime sin cota: `consolidacion_service.py._scan_zip` (L587-618) itera `zf.filelist` filtrando por extensión y devuelve `(ZipInfo, path)`; `_consolidar_desde_zipfile` (L256-288) hace `zf.read(info)` por cada uno (L281). En ningún punto se mira `info.file_size` (tamaño descomprimido) ni se acota la cantidad de entradas. `backend/app/main.py` solo registra `CORSMiddleware`; no hay middleware de límite de request.

Esto expone dos vectores de agotamiento de memoria: archivo gigante materializado entero (PERF-008, alto) y ZIP-bomb clásica ~100 KB → varios GB al descomprimir (SEC-005, alto).

## Gobernanza — MEDIA (validación de input en el boundary + pipeline de consolidación)

Nivel **MEDIO** (JR Stack): "Implement with checkpoints; surface decisions to the user."

- La fase de `apply` se implementa **en pasos con checkpoints**, siguiendo TDD (RED antes de escribir producción).
- Decisiones no obvias (elección del tope de expansión, código HTTP `413` vs `400`, si tocar nginx) se **exponen al usuario** para revisión, no se resuelven silenciosamente.
- No es CRÍTICA: no toca auth, cifrado ni datos persistidos; es endurecimiento de entrada. No requiere aprobación línea por línea, pero sí surfacing de las decisiones abiertas.
- **Esfuerzo estimado: S/M** — el más grande de los 7 quick wins: 2 servicios, 2 endpoints, tests de subida + tests de ZIP-bomb.

## Goals / Non-Goals

**Goals:**
- Aplicar `MAX_UPLOAD_SIZE` en ambos endpoints de subida (individual y masiva), rechazando con `413`/`400` antes de consolidar.
- Cortar ZIP-bombs en el pipeline de descompresión: tope de tamaño descomprimido acumulado (`ZipInfo.file_size`) y tope de cantidad de entradas, abortando ANTES de materializar todo el contenido en memoria.
- Mensajes de error claros y accionables, sin fuga de internals.
- Preservar 100% el comportamiento para entregas legítimas (pocos MB).

**Non-Goals:**
- No implementar streaming a disco de los uploads (el patrón actual es en memoria; solo se le pone un techo). El streaming por chunks a disco puede ser un change futuro.
- No modificar el modelo de datos, migraciones ni contratos de éxito de la API.
- No validar contenido/antivirus del archivo; solo tamaño y forma del ZIP.
- No tocar `nginx/nginx.conf` en este change (ver Decisions D4).

## Decisions

### D1: Chequeo de tamaño con doble barrera (Content-Length + tamaño real)
Como primera barrera barata, leer el header `Content-Length` del `UploadFile`/request y rechazar temprano si ya declara superar `MAX_UPLOAD_SIZE`. Como barrera definitiva (el header es falsificable/ausente), validar el tamaño real: en el patrón actual `contenido_bytes = await archivo.read()` ya trae el largo en `len(contenido_bytes)` (subida individual incluso computa `archivo_tamanio = len(contenido_bytes)` en L137) — comparar ese largo contra el tope y rechazar. La comprobación de `len(...)` post-lectura es O(1) y no cambia el patrón en memoria existente; el objetivo del change es poner el techo, no rediseñar el I/O.
- **Alternativa considerada:** lectura por chunks con corte incremental (`while chunk := await archivo.read(N)` acumulando y abortando al pasar el tope) para no materializar el archivo gigante completo. Es estrictamente mejor contra PERF-008 y se **recomienda** para los uploads directos; se deja como decisión a confirmar en apply por su costo de reescritura del flujo. Como mínimo aceptable, el chequeo `Content-Length` + `len()` cubre el caso realista. **Surface al usuario en el checkpoint de apply.**

### D2: Anti ZIP-bomb por `ZipInfo.file_size` acumulado (no por lectura real)
`zipfile` expone `info.file_size` = tamaño descomprimido declarado en el header central del ZIP, **sin descomprimir**. Se acumula ese valor recorriendo `zf.filelist` (o dentro de `_scan_zip`, que ya itera `zf.filelist`) y se aborta apenas el acumulado supere el tope de expansión, ANTES del `zf.read(info)`. Así una ZIP-bomb nunca se materializa. El tope de expansión se propone en `MAX_UPLOAD_SIZE` (mismo 100 MB) o un múltiplo razonable; el valor exacto se decide en apply.
- **Nota de robustez:** `file_size` es un valor declarado; un ZIP malicioso podría mentirlo hacia abajo. Como refuerzo opcional, al leer cada entrada se puede verificar que los bytes reales no excedan lo declarado. Se documenta como refuerzo, no bloqueante para el quick win.
- **Alternativa considerada:** descomprimir con límite por streaming (`open(info).read(N)`) — mayor complejidad; el chequeo por `file_size` corta el 99% de las bombas clásicas con costo casi nulo.

### D3: Anti ZIP-bomb por cantidad de entradas
Limitar la cantidad total de entradas del ZIP a un tope (p. ej. una nueva constante `MAX_ZIP_ENTRIES` en `config.py`, valor a definir en apply). `len(zf.filelist)` / `len(zip_file.namelist())` es O(1)-ish y permite abortar sin recorrer todo. Cubre bombas de "muchos archivos diminutos" (agotan CPU/inodos/estructuras) que el tope de tamaño no atrapa bien.

### D4: NO tocar nginx en este change
`nginx/nginx.conf` fijar `client_max_body_size` sería una segunda barrera de red útil, pero `nginx.conf` es dominio de **gobernanza ALTA (deploy compartido)** y ya está siendo editado por el change `limpiar-n8n-deploy`. Tocarlo aquí arriesga colisión de merge y mezcla dominios. Se documenta como **mejora complementaria recomendada** para un change de infra posterior (o para incorporarse a `limpiar-n8n-deploy` si el usuario lo prefiere), no como parte de este quick win.
- **Alternativa considerada:** middleware de límite de request en `main.py` (Starlette) como barrera de app previa a los endpoints. Es viable y self-contained en el backend; se menciona como opción pero se prioriza validar en los servicios donde vive la lógica y el `MAX_UPLOAD_SIZE`. **Surface al usuario.**

### D5: Código HTTP de rechazo
Se propone `413 Request Entity Too Large` para el exceso de tamaño (semánticamente correcto) y para el aborto por ZIP-bomb, dado que el resto del código de subida usa `HTTPException`. Si se prefiere homogeneizar con los `400` ya usados en validación de archivo (`entrega_service.py:124-133`), se usa `400`. Decisión menor a confirmar; los tests aceptan `413` o `400`.

## Risks / Trade-offs

- **El chequeo `len()` post-lectura no evita materializar el archivo gigante en memoria** (solo lo rechaza después de leerlo) → mitigar priorizando el chequeo `Content-Length` como corte temprano y, si el usuario lo aprueba, la lectura por chunks (D1). El anti-ZIP-bomb (D2/D3) sí corta antes de leer.
- **`ZipInfo.file_size` es un valor declarado, potencialmente falseable** → mitigar con el refuerzo de verificar bytes reales al leer (D2). Aun así, el tope declarado ya frena las bombas por deflate estándar.
- **Elegir un tope de expansión demasiado bajo rompería entregas legítimas grandes** → el caso real son entregas de pocos MB; se propone alinear el tope a `MAX_UPLOAD_SIZE` y surfacear el valor al usuario.
- **Tests DB-backed con JSONB no corren en el harness SQLite in-memory** (limitación conocida del proyecto) → preferir tests unitarios de servicio que ejerciten la validación de tamaño / ZIP-bomb sin persistencia, o mockear el repositorio; ver tasks.

## Migration Plan

1. (apply, TDD) Escribir tests RED: subida individual y masiva > `MAX_UPLOAD_SIZE` → rechazo; ZIP-bomb (file_size descomprimido excesivo) → aborto; ZIP con demasiadas entradas → aborto.
2. (apply, checkpoint) Confirmar con el usuario: valor del tope de expansión, `MAX_ZIP_ENTRIES`, `413` vs `400`, y si se adopta lectura por chunks (D1).
3. Implementar la validación de tamaño en los dos endpoints de `entrega_service.py`.
4. Implementar el corte anti ZIP-bomb en `consolidacion_service._scan_zip`/`_consolidar_desde_zipfile` y en el loop de carga masiva.
5. Correr la suite completa; verificar que las entregas legítimas siguen pasando.

**Rollback:** revertir el commit restablece el comportamiento anterior; cambio puramente de validación de entrada, sin migración de schema ni de datos.

## Open Questions

- ¿Valor exacto del tope de expansión descomprimida y de `MAX_ZIP_ENTRIES`? (propuesta: expansión = `MAX_UPLOAD_SIZE`; entradas = a definir, p. ej. 2000).
- ¿Se adopta la lectura por chunks para cortar el archivo gigante ANTES de materializarlo, o alcanza con `Content-Length` + `len()` para este quick win?
- ¿`client_max_body_size` en nginx se incorpora al change `limpiar-n8n-deploy` o queda para un change de infra posterior?
