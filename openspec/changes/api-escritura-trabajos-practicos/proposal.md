## Why

Verificado contra la API en vivo el 2026-08-17:

```
GET  /rubricas/?materia_id=N     funciona con rol tutor
GET  /rubricas/{id}              403 — "Se requiere rol de coordinador o administrador"
POST /rubricas/                  no existe para un cliente externo
```

Las rúbricas de los ejercicios de AI-Native ya están escritas del lado de ellos, criterio por criterio con su puntaje. Sin endpoints de escritura hay que volver a cargarlas a mano en Active-IA, ejercicio por ejercicio, y **eso es lo que hoy bloquea el piloto**. El cliente HTTP del otro lado ya está implementado y probado contra este contrato (`evaluation-service/services/activeia_client.py`); corre contra un mock explícito hasta que estos endpoints existan.

El change `trabajos-practicos-y-external-ref` construye el modelo. Este lo expone.

**Por qué `PUT .../by-ref/{ref}` y no `PUT /{id}`**: el cliente no guarda el id de Active-IA hasta después del primer push. Con `PUT /{id}`, la primera sincronización y todas las siguientes serían dos caminos distintos, y el cliente tendría que mantener un mapeo de ids ajenos. Con `by-ref` es siempre la misma llamada. Sin idempotencia, cada publicación crearía un TP nuevo y el docente terminaría eligiendo entre diez copias — y elegir mal no da una nota floja: **corrige otra cosa**.

**Por qué `materia_external_ref` y no `materia_id`**: mismo criterio. Un id numérico de Active-IA obliga al cliente a mantener un mapeo de ids ajenos que vencen sin avisar, que es justo el problema que el identificador externo viene a resolver.

## What Changes

- **`POST /api/v1/trabajos-practicos/`** — crea un TP con sus ejercicios anidados y la rúbrica de cada uno, en una sola transacción. Resuelve la materia por `materia_external_ref`.
- **`PUT /api/v1/trabajos-practicos/by-ref/{external_ref}`** — crea o actualiza por identificador externo. **Idempotente**: reenviar el mismo TP actualiza en lugar de duplicar.
- **`GET /api/v1/trabajos-practicos/by-ref/{external_ref}`** — lo busca por identificador externo.
- **La respuesta devuelve, por ejercicio, su `external_ref` y su `rubrica_id`.** Es lo que le permite al cliente saber con qué rúbrica se corrige cada uno. Emparejar por orden o por título sería adivinar.
- **Reconciliación en el `PUT`**: los ejercicios se emparejan por `external_ref`. Los que ya existen se actualizan conservando su `rubrica_id`; los nuevos se crean; los que dejaron de venir se dan de baja lógica. **Un ejercicio nunca cambia de `rubrica_id` entre pushes** — si lo hiciera, las correcciones ya hechas quedarían colgando de una rúbrica que el cliente ya no asocia a ese ejercicio.
- **Rechazo explícito de casos ocultos con salida esperada** (regla del change anterior), con el id del caso infractor en el error.
- **Sin corrección en lote**: el cliente lo pidió explícitamente. Estos endpoints escriben la estructura; la corrección se dispara de a un ejercicio en el change siguiente.

## Capabilities

### New Capabilities

- `api-trabajos-practicos-escritura`: endpoints de alta, upsert idempotente por identificador externo y consulta por identificador externo de trabajos prácticos con sus ejercicios y rúbricas anidados.
- `trabajo-practico-reconciliacion`: reglas de emparejamiento de ejercicios entre pushes sucesivos — actualización por identificador externo, alta de los nuevos, baja lógica de los que desaparecen, y estabilidad del vínculo ejercicio-rúbrica.

### Modified Capabilities

- `permisos-universidad-activa`: los endpoints nuevos se incorporan al esquema de permisos por rol y universidad activa.

## Impact

**Backend**
- `app/routers/trabajos_practicos.py` — nuevo router con los tres endpoints.
- `app/main.py` — registro del router.
- `app/services/trabajo_practico_service.py` — lógica de upsert y reconciliación (el servicio se crea en el change anterior; acá gana el upsert).
- `app/schemas/trabajo_practico.py` — DTOs de request y response, incluyendo `materia_external_ref` y la respuesta con `rubrica_id` por ejercicio.
- `app/services/actividad_service.py` — auditoría de las escrituras (el proyecto audita toda acción).

**Depende de**: `trabajos-practicos-y-external-ref` (modelo, validación y resolución).

**Relacionado con**: `cuenta-de-servicio-integracion` — estos endpoints necesitan una identidad con permiso de escritura sobre la materia. Hasta que ese change esté, se operan con rol coordinador o administrador.
