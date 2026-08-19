## Context

El change `trabajos-practicos-y-external-ref` deja el modelo listo: `TrabajoPractico`, `Ejercicio`, `external_ref` en materia/TP/ejercicio, la rúbrica 1:1 por ejercicio, la resolución por identificador externo y la validación de `test_cases`. Este change expone eso por HTTP.

Restricciones del proyecto que gobiernan el diseño:

- Clean Architecture: los routers solo hacen HTTP + validación Pydantic; la lógica va al servicio; el acceso a datos, al repositorio.
- Permisos por rol verificados en cada endpoint, con `ContextoUniversidad` y universidad activa.
- Toda acción se audita (`Actividad`).
- Los DELETE son siempre soft.
- Errores: validación → 400/422, no encontrado → 404, prohibido → 403, error de proveedor IA → 502, interno → 500.

Comportamientos verificados del lado del cliente que este change tiene que respetar (§7 del pedido):

- Su timeout es de 90s, porque con 30 fallaba una de cada tres llamadas contra endpoints pesados de Active-IA.
- Ya toparon con `GET /entregas/{id}` devolviendo 500 y lo rodearon.

Governance: **MEDIA** — API pública nueva, con checkpoints.

## Goals / Non-Goals

**Goals**

- Que publicar un TP sea una sola llamada, siempre la misma, la primera vez y la enésima.
- Que el cliente sepa sin ambigüedad con qué rúbrica se corrige cada ejercicio.
- Que reenviar el mismo TP nunca duplique nada.
- Que un error de contrato falle fuerte y temprano, con el campo infractor nombrado.

**Non-Goals**

- No hay corrección en lote (el cliente lo excluyó explícitamente).
- No se escribe nada del lado del cliente. La integración es de una sola dirección.
- No se expone un endpoint de borrado de TP en este change.
- No se versionan los TPs: el upsert pisa, no acumula versiones.

## Decisions

### D1. `PUT .../by-ref/{ref}` es upsert, y es el camino principal

`POST /` existe y crea, pero **el camino que el cliente usa es el `PUT` por identificador externo**. Semántica:

- Si no existe un TP vigente con ese `external_ref` en la materia → lo crea. Responde `201`.
- Si existe → lo actualiza. Responde `200`.

Rationale: el cliente no tiene el id de Active-IA antes del primer push. Un `PUT /{id}` obligaría a dos caminos distintos y a mantener un mapeo de ids ajenos.

El `external_ref` del path es el del TP. `materia_external_ref` viaja en el body y se resuelve a la materia; si no resuelve, `404` con el identificador en el mensaje, nunca creación implícita de la materia.

### D2. La reconciliación empareja ejercicios por `external_ref`, nunca por orden ni por título

**Este es el punto donde una decisión floja rompe notas.** En un `PUT` sobre un TP existente:

| Situación | Acción |
|---|---|
| El `external_ref` del ejercicio ya existe en el TP | Se actualiza en su lugar, **conservando su `rubrica_id`** |
| El `external_ref` no existe | Se crea el ejercicio y su rúbrica |
| Un ejercicio vigente del TP no viene en el push | Se da de **baja lógica**, junto con su rúbrica |

Regla dura: **el `rubrica_id` de un ejercicio es estable para toda la vida del ejercicio.** Actualizar un ejercicio actualiza el contenido de su rúbrica (criterios, puntajes), nunca la reemplaza por otra.

Rationale: las `Entrega` y las `Correccion` cuelgan de `rubrica_id`. Si un push rotara el `rubrica_id`, las correcciones ya hechas quedarían asociadas a una rúbrica que el cliente ya no vincula a ese ejercicio, y el cliente pediría corregir contra la rúbrica nueva sin ver las correcciones viejas. Emparejar por orden o por título tiene el mismo defecto: reordenar los ejercicios en la plataforma del cliente rotaría las asociaciones en silencio.

**Baja de un ejercicio con correcciones**: la baja es lógica, así que las entregas y correcciones existentes se conservan y siguen siendo consultables. El ejercicio deja de aparecer en el TP y deja de aceptar correcciones nuevas.

### D3. La respuesta devuelve `external_ref` + `rubrica_id` por ejercicio

Es un requisito explícito del cliente. La respuesta del `POST`, del `PUT` y del `GET` incluye, por ejercicio, al menos: `external_ref`, `id` interno, `orden`, `titulo`, `peso` y `rubrica_id`.

Rationale: sin el `rubrica_id` el cliente no puede saber con qué rúbrica se corrige cada ejercicio, y tendría que inferirlo por posición o por título. Es la misma clase de adivinanza que D2 elimina del lado del servidor.

### D4. Atomicidad: el TP entero, o nada

El alta y el upsert son **una sola transacción**. Si falla la validación del tercer ejercicio de cuatro, no queda ni el TP ni los dos primeros.

Rationale: un TP a medio publicar es peor que ninguno — el docente ve tres ejercicios de cuatro y no tiene forma de saber que falta uno. Y como el `PUT` es idempotente, reintentar tras corregir el error es gratis.

### D5. Los errores de contrato nombran el campo infractor

Un caso oculto con salida esperada, un tipo de caso desconocido, ids de caso duplicados, un `external_ref` de ejercicio repetido dentro del mismo push: todos responden `422` con el identificador del ejercicio y del caso en el detalle.

Rationale: el cliente publica desde una interfaz de docente. Un `422` genérico obliga a alguien a adivinar cuál de veinte ejercicios está mal.

**Sobre el rechazo del caso oculto con salida esperada** (regla del change anterior): se rechaza en vez de descartar en silencio. Falla en el momento barato — el docente publicando — y no con un alumno esperando. Y descartar en silencio dejaría al cliente creyendo que su contrato se respeta cuando se le está limpiando el payload.

### D6. Permisos: escritura para coordinador y administrador, más la cuenta de servicio

Hasta que exista `cuenta-de-servicio-integracion`, los tres endpoints exigen rol coordinador o administrador sobre la universidad activa, más pertenencia a la materia. El `GET` admite además rol tutor con acceso a la materia.

Rationale: escribir rúbricas es hoy una operación de coordinación (`require_coordinador_or_admin` en todo `app/routers/rubricas.py`), y este change no es el lugar para relajar eso. El change de cuenta de servicio agrega la identidad de máquina sin tocar esta regla.

### D7. Auditoría de cada escritura

Cada `POST` y cada `PUT` registran una `Actividad` con el actor, el `external_ref` del TP, la cantidad de ejercicios creados, actualizados y dados de baja.

Rationale: el proyecto audita toda acción, y en un upsert idempotente la auditoría es la única forma de reconstruir qué push dejó al TP como está.

## Risks / Trade-offs

- **El upsert pisa sin avisar.** Un push equivocado del cliente reescribe los criterios de una rúbrica que ya se usó para corregir. Mitigación: la auditoría de D7 deja el rastro, y las correcciones ya hechas conservan su propio `criterios_json` (la corrección no lee la rúbrica al mostrarse). Se anota como candidato a versionado de rúbrica, fuera de alcance.
- **La baja lógica de un ejercicio ausente es agresiva.** Si el cliente manda un push parcial por error, se dan de baja ejercicios vivos. Mitigación: es baja lógica y reenviar el push completo los restaura; la auditoría lo hace visible. Alternativa descartada: exigir un flag explícito de borrado, que complica el contrato y contradice la semántica de `PUT`.
- **Payloads grandes.** Un TP con muchos ejercicios y enunciados en Markdown puede ser pesado. El límite de upload del proyecto (`MAX_UPLOAD_SIZE`) aplica a archivos, no a JSON; conviene fijar un límite de tamaño de body y de cantidad de ejercicios por TP.

## Migration Plan

Sin migración: el modelo lo crea el change anterior. Se registra el router nuevo y se documenta el contrato.

Se recomienda entregarle al cliente el contrato antes del deploy, para que apague su mock contra un entorno de staging y no directamente contra producción.

## Open Questions

- ¿Cuál es el límite razonable de ejercicios por TP y de tamaño de body? La propuesta sugiere fijarlo explícitamente en vez de dejarlo abierto, pero el número lo tiene que dar el uso real del cliente.
- ¿Hace falta `DELETE /trabajos-practicos/by-ref/{ref}`? El cliente no lo pidió. Se deja fuera hasta que aparezca la necesidad.
- ¿El `PUT` debería rechazar un push que daría de baja ejercicios que ya tienen correcciones, exigiendo confirmación? Es la mitigación fuerte del segundo riesgo, a costa de complicar el contrato. Decisión pendiente con el cliente.
