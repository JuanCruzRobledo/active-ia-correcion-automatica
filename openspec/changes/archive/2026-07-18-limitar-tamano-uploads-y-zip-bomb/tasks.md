# Tasks — limitar-tamano-uploads-y-zip-bomb

> Gobernanza **MEDIA**: implementar con checkpoints. Antes de escribir producción,
> confirmar con el usuario las decisiones abiertas (D1, D4, D5 + valores de topes).
> TDD: escribir el test RED antes de cada bloque de producción.

## 0. Checkpoint de decisiones (antes de codear)

- [x] 0.1 Confirmar con el usuario el valor del tope de expansión descomprimida (propuesta: `MAX_UPLOAD_SIZE`) y de `MAX_ZIP_ENTRIES` (propuesta: a definir, p. ej. 2000)
- [x] 0.2 Confirmar código de rechazo: `413` (propuesto) vs `400` homogéneo con las validaciones actuales de archivo
- [x] 0.3 Confirmar si se adopta lectura por chunks para cortar el archivo gigante antes de materializarlo (D1), o alcanza `Content-Length` + `len()`
- [x] 0.4 Confirmar que nginx (`client_max_body_size`) queda FUERA de este change (D4)

## 1. Configuración

- [x] 1.1 (si aplica) Agregar constante `MAX_ZIP_ENTRIES` (y, si se decide, `MAX_ZIP_EXPANDED_SIZE`) en `backend/app/core/config.py`, reutilizando `MAX_UPLOAD_SIZE` donde corresponda

## 2. Tests RED — límite de tamaño en subida (escribir primero)

- [x] 2.1 En `backend/tests/unit/services/` (o `backend/tests/integration/api/`): test que sube una entrega **individual** con tamaño > `MAX_UPLOAD_SIZE` y espera rechazo `413`/`400`, verificando que NO se crea/corrige la entrega
- [x] 2.2 Test que sube un ZIP de **carga masiva** con tamaño > `MAX_UPLOAD_SIZE` y espera rechazo `413`/`400`, sin procesar carpetas de alumnos
- [x] 2.3 Test happy-path: archivo individual y ZIP masivo **dentro** del límite se procesan sin bloqueo por tamaño (triangulación)
- [x] 2.4 Ejecutar la suite y confirmar que 2.1–2.3 fallan (RED) por falta de la validación

## 3. Implementación — límite de tamaño en los endpoints

- [x] 3.1 En subida individual (`entrega_service.py` ~L136): validar `Content-Length` como barrera temprana y `len(contenido_bytes)` contra `MAX_UPLOAD_SIZE`; rechazar con el código acordado antes de `_procesar_contenido`
- [x] 3.2 En carga masiva (`entrega_service.py` ~L732): validar el tamaño del ZIP contenedor contra `MAX_UPLOAD_SIZE` antes de abrir el `ZipFile`
- [ ] 3.3 (si se aprobó D1) Implementar lectura por chunks con corte incremental en los uploads directos
- [x] 3.4 Correr 2.1–2.3 → GREEN

## 4. Tests RED — anti ZIP-bomb (escribir primero)

- [x] 4.1 Test que fabrica en memoria un ZIP cuyo **tamaño descomprimido acumulado** (`ZipInfo.file_size`) supera el tope y espera aborto controlado (mensaje claro) en la consolidación, verificando que NO se materializa el contenido completo en memoria
- [x] 4.2 Test que fabrica un ZIP con **cantidad de entradas** > `MAX_ZIP_ENTRIES` y espera aborto controlado con mensaje claro
- [x] 4.3 Test equivalente para el loop de **carga masiva** (ZIP de carpetas de alumnos con expansión / entradas excesivas → aborto controlado)
- [x] 4.4 Test happy-path: ZIP legítimo con expansión y cantidad de entradas dentro de los topes se consolida normalmente (triangulación)
- [x] 4.5 Ejecutar la suite y confirmar RED

## 5. Implementación — protección anti ZIP-bomb

- [x] 5.1 En `consolidacion_service._scan_zip` / `_consolidar_desde_zipfile`: acumular `info.file_size` recorriendo `zf.filelist` y abortar ANTES de `zf.read(info)` si supera el tope de expansión; limitar la cantidad de entradas
- [x] 5.2 En el loop de carga masiva (`entrega_service.py` ~L738-820): acumular tamaño descomprimido y contar entradas al iterar carpetas de alumnos, abortando de forma controlada
- [ ] 5.3 (refuerzo opcional D2) Verificar que los bytes reales leídos no excedan lo declarado por `file_size`
- [x] 5.4 Correr 4.1–4.4 → GREEN

## 6. Mensajes y manejo de errores

- [x] 6.1 Verificar que todos los mensajes de rechazo nombran la causa (tamaño/expansión/entradas) y el tope, sin filtrar stack traces ni paths internos
- [x] 6.2 Confirmar que el frontend maneja el nuevo `413`/`400` con el flujo de error existente (sin cambios de UI salvo el texto)

## 7. Cierre

- [x] 7.1 Ejecutar la suite completa (`pytest`) y verificar que las entregas legítimas siguen pasando
- [x] 7.2 REFACTOR: extraer helper de validación de tamaño / de guardas anti-ZIP-bomb si hay duplicación entre los dos servicios; tests siguen verdes
- [ ] 7.3 Actualizar `openspec/specs/` vía archive cuando el change se cierre (fase archive)
