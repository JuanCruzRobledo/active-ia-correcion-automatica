## Why

Al recorregir una entrega, la corrección anterior se borra con hard delete sin dejar ningún rastro (`correccion_service.py:336-338`). Se pierden la nota anterior, los criterios evaluados, el `raw_response` de la IA y —lo más grave— las ediciones manuales del tutor. Ante un reclamo académico ("me habían puesto un 8 y ahora un 4") no hay forma de reconstruir qué pasó ni quién lo hizo. Esto es el hallazgo **CRUD-003** (🟠 Alta, `docs/auditoria/02-cruds.md`) y contradice la regla dura del proyecto de soft delete / trazabilidad para auditoría.

## What Changes

- Antes de borrar la corrección saliente en una recorrección, se guarda un **snapshot completo** en una tabla nueva dedicada `correccion_historial` (nota, criterios, feedback, penalizaciones, `editado_manualmente`, `raw_response`, autor original y fecha original de corrección).
- Se registra una `Actividad` de tipo nuevo `CORRECCION_RECORREGIDA` con el actor que disparó la recorrección, para que el borrado quede auditado (hoy no lo está).
- Se expone un endpoint de **solo lectura** para consultar el historial de correcciones de una entrega, protegido por el guard de pertenencia `verificar_acceso_entrega`.
- La corrección "vigente" sigue viviendo en la tabla `correcciones` (relación 1:1 intacta): el snapshot NO cambia el modelo de `Correccion` ni su `unique(entrega_id)`.
- La primera corrección de una entrega no genera snapshot (no hay corrección previa que preservar): sólo las recorrecciones.

## Capabilities

### New Capabilities
- `historial-correcciones`: preservación auditable de cada corrección reemplazada por una recorrección (snapshot inmutable + registro de actividad), y lectura del historial de versiones de una entrega.

### Modified Capabilities
<!-- No existen specs OpenSpec previas para el flujo de corrección; no hay requisitos de otra capability que cambien a nivel spec. -->

## Impact

- **Modelo/DB**: nueva tabla `correccion_historial` + migración Alembic (down_revision `c1a2b3d4e5f6`). Nuevo valor `CORRECCION_RECORREGIDA` en el ENUM nativo `tipoactividadenum` (requiere `ALTER TYPE ... ADD VALUE` a mano en la migración).
- **Repositorios**: nuevo `CorreccionHistorialRepository` (crear snapshot, listar por entrega).
- **Servicios**: `CorreccionService.corregir_individual` intercala el snapshot entre `get_by_entrega_id` y `delete`, y registra la `Actividad`.
- **API**: nuevo endpoint `GET` de historial de correcciones por entrega + schema de respuesta.
- **Gobernanza**: dominio CRÍTICO (notas de alumnos / auditoría). Este change entrega SOLO los artefactos OpenSpec; el código se implementa después con aprobación humana línea por línea.

### Fuera de alcance (explícito)
- Atomicidad transaccional del bloque snapshot + delete + create (debilidad preexistente IA-003/004; otro change).
- UI de frontend para visualizar el historial (follow-up).
- Versionar la corrección en la sobrescritura de la ENTREGA (ese flujo ya usa `EntregaHistorial.correccion_json`; no es CRUD-003).
