## Context

El flujo de recorrección vive en `CorreccionService.corregir_individual` (`app/services/correccion_service.py`). El método:

1. Llama a la IA (Gemini/OpenRouter) y parsea la respuesta.
2. `existing = await self.correccion_repo.get_by_entrega_id(entrega_id)` (`:332`).
3. Si `existing`, `await self.correccion_repo.delete(existing)` — **hard delete físico, sin snapshot ni Actividad** (`:336-338`).
4. Construye y crea la nueva `Correccion` (`:412-413`).
5. Pone la entrega en `CORREGIDA` y limpia errores (`:416-418`).

`recorregir` (`:438`) simplemente delega en `corregir_individual` pasando el `corregido_por_id` del actor. `corregir_individual` corre PRIMERO la IA y DESPUÉS borra/crea, así que el snapshot debe intercalarse entre el paso 2 y el 3.

`Correccion` (`app/models/correccion.py`) es 1:1 con `Entrega` (`entrega_id unique=True`). Columnas relevantes: `nota Numeric(5,2)`, `criterios_json JSONB`, `fortalezas/recomendaciones/penalizaciones_aplicadas ARRAY(Text)`, `comentario_general Text`, `nota_antes_penalizaciones Numeric(5,2)`, `condicion_desaprobacion_aplicada Text`, `editado_manualmente Boolean`, `raw_response JSONB deferred=True`, `corregido_por_id FK usuarios nullable`, `created_at/updated_at` (TimestampMixin). NO tiene baja lógica.

Patrón de tabla-hija a imitar: `EntregaHistorial` (`app/models/entrega.py:174-233`) + `HistorialService` (`app/services/historial_service.py`) + `EntregaHistorialRepository`. `verificar_acceso_entrega` existe en `app/core/permissions.py:491` (post-SEC-002) y no filtra `deleted_at`. `ActividadService.registrar_actividad(tipo, descripcion, entidad_id, entidad_nombre, usuario_id=None, metadatos=None)` (`app/services/actividad_service.py:28`).

Dominio CRÍTICO (notas de alumnos / auditoría): este change entrega SOLO artefactos OpenSpec. El código se implementa después con aprobación humana línea por línea.

## Goals / Non-Goals

**Goals:**
- Preservar de forma auditable e inmutable cada corrección que una recorrección reemplaza, incluyendo `raw_response` y `editado_manualmente`.
- Auditar el evento de recorrección con una `Actividad` (`CORRECCION_RECORREGIDA`).
- Exponer lectura del historial por entrega, con el guard de pertenencia existente.
- Cero cambios de comportamiento en el flujo normal de la primera corrección.

**Non-Goals:**
- Atomicidad transaccional del bloque snapshot + delete + create (debilidad preexistente IA-003/004; otro change).
- UI de frontend del historial (follow-up).
- Versionar la corrección en la sobrescritura de la ENTREGA (ya cubierto parcialmente por `EntregaHistorial.correccion_json`).
- Migrar/backfill de correcciones ya borradas (no hay datos que recuperar).

## Decisions

### D1 — Tabla nueva dedicada `correccion_historial`, no soft delete de `Correccion`

Snapshot en una tabla NUEVA `correccion_historial`, en vez de agregar `deleted_at` a `Correccion`.

**Por qué:** `Correccion.entrega_id` es `unique=True` (1:1 rígido). Un soft delete dejaría filas "muertas" ocupando ese unique y obligaría a agregar `.where(deleted_at.is_(None))` a TODAS las queries existentes (`get_by_entrega_id`, `get_all`, exports, Moodle, PDF, estadísticas) — alto riesgo de regresión en un dominio crítico. Una tabla-hija separada mantiene `correcciones` como "la corrección vigente" y aísla el historial. Semánticamente también es lo correcto: es un log de versiones reemplazadas, append-only.

**Alternativa descartada:** reusar `EntregaHistorial`. Esa tabla modela la sobrescritura de un ARCHIVO de entrega (guarda `archivo_ruta`, `hash_sha256`, y sólo un `correccion_json` parcial). Mezclar la recorrección ahí confunde dos eventos distintos y perdería campos (raw_response, penalizaciones, autor original).

### D2 — Columnas del snapshot

`CorreccionHistorial` (imitando el estilo de `EntregaHistorial`, `Base` sin mixins de timestamp/soft-delete):

| Columna | Tipo | Nota |
|---|---|---|
| `id` | PK int | |
| `entrega_id` | FK entregas, **index=True** | se lista por entrega (D4) |
| `nota` | Numeric(5,2) | |
| `criterios_json` | JSONB | |
| `fortalezas` | ARRAY(Text) | |
| `recomendaciones` | ARRAY(Text) | |
| `comentario_general` | Text nullable | |
| `nota_antes_penalizaciones` | Numeric(5,2) nullable | |
| `condicion_desaprobacion_aplicada` | Text nullable | |
| `penalizaciones_aplicadas` | ARRAY(Text) | |
| `editado_manualmente` | Boolean | CRÍTICO preservar |
| `corregido_por_id` | FK usuarios nullable | autor de la corrección saliente |
| `raw_response` | JSONB **deferred=True** nullable | forense, no cargar en listados |
| `correccion_creada_en` | DateTime | el `created_at` ORIGINAL de la corrección saliente |
| `reemplazada_en` | DateTime | cuándo se recorrigió |
| `reemplazada_por_id` | FK usuarios | quién disparó la recorrección (= `corregido_por_id` del actor) |

`raw_response` es `deferred=True` igual que en `Correccion`, por la misma razón (PERF): el listado del historial no debe arrastrar el JSON crudo grande.

### D3 — Orden exacto en `corregir_individual` y captura del `raw_response` deferred

Intercalar el snapshot entre `get_by_entrega_id` y `delete`:

```
existing = await correccion_repo.get_by_entrega_id(entrega_id)
if existing:
    # 1. cargar raw_response (deferred) ANTES del delete
    # 2. crear snapshot en correccion_historial (reemplazada_por_id = corregido_por_id del actor)
    # 3. registrar Actividad CORRECCION_RECORREGIDA
    await correccion_repo.delete(existing)   # ya existente
# ... create nueva corrección (ya existente)
```

**Gotcha del deferred:** `get_by_entrega_id` hace `select(Correccion)` sin `undefer`, así que `existing.raw_response` NO está cargado. Acceder a él tras el `delete` fallaría (instancia borrada / DetachedInstanceError). El snapshot debe leer `raw_response` mientras la instancia sigue viva en la sesión — opciones: cargar con `undefer(Correccion.raw_response)` en un getter dedicado del repo, o acceder al atributo (dispara la carga lazy) antes de construir el snapshot. La decisión fina (getter con undefer vs. acceso lazy) se resuelve en apply; el spec sólo exige que el snapshot preserve el `raw_response`.

`correccion_creada_en` = `existing.created_at`. `reemplazada_en` = `datetime.utcnow()`. `reemplazada_por_id` = `corregido_por_id` (el parámetro del actor que ya recibe `corregir_individual`).

### D4 — Índice en `correccion_historial.entrega_id`

`index=True` en `entrega_id`. El único patrón de lectura es "todas las versiones de una entrega" (`WHERE entrega_id = ? ORDER BY reemplazada_en DESC`); mismo criterio que `EntregaHistorial.entrega_actual_id` (que ya es `index=True`).

### D5 — Enum `CORRECCION_RECORREGIDA` con `ALTER TYPE` a mano

`TipoActividadEnum` (`app/models/enums.py:57`) mapea a un ENUM NATIVO de Postgres (`Actividad.tipo` usa `SQLEnum(create_type=False)`). `autogenerate` NO detecta valores nuevos de enum. La migración DEBE incluir a mano:

```
op.execute("ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS 'CORRECCION_RECORREGIDA'")
```

Mismo patrón ya usado en `c1a2b3d4e5f6` (CRUD-001, que agregó ENTREGA_ELIMINADA/ENTREGA_RESTAURADA). `IF NOT EXISTS` = idempotente. El `downgrade` sólo dropea la tabla; Postgres no soporta `DROP VALUE`, el valor de enum queda huérfano (inocuo). La migración nueva tiene `down_revision = 'c1a2b3d4e5f6'` (head actual).

### D6 — Endpoint de lectura y guard

`GET` que resuelve entrega → historial, protegido con `await verificar_acceso_entrega(db, current_user, entrega_id)` antes de servir. `verificar_acceso_entrega` NO filtra `deleted_at`, lo cual es deseable: consultar el historial de una entrega borrada (soft delete) debe seguir funcionando. El schema de respuesta imita `HistorialResponse`/`HistorialItem` (`app/schemas/entrega.py`): `entrega_id`, `total_versiones`, `versiones[]` sin `raw_response`.

## Risks / Trade-offs

- **[No atomicidad snapshot+delete+create]** → Si el proceso falla entre el snapshot y el create de la nueva corrección, puede quedar un snapshot sin corrección vigente. Aceptado como fuera de alcance (IA-003/004): es preferible a la pérdida total actual, y el snapshot de más es inocuo/auditable. Documentado como non-goal.
- **[`raw_response` deferred no cargado tras delete]** → DetachedInstanceError si se accede después del `delete`. Mitigación: capturar el valor ANTES del delete (D3); cubierto por un escenario del spec.
- **[Crecimiento de tabla]** → cada recorrección agrega una fila con un `raw_response` grande. Mitigación: `deferred=True` evita el costo en listados; volumen esperado bajo (recorrecciones son excepcionales). Sin política de retención por ahora.
- **[Enum add en Postgres]** → `ALTER TYPE ADD VALUE` debe ir a mano o el insert de la Actividad falla en runtime. Mitigación: test e2e contra Postgres real (fase 5 de tasks) que ejercita la recorrección completa, no sólo SQLite.
- **[SQLite en tests]** → JSONB/ARRAY se compilan a JSON vía `@compiles` (ver `tests/unit/repositories/test_perf002_entrega_count.py`); el enum nativo no existe en SQLite. Los tests unitarios del repo/service usan ese shim; la verificación del `ALTER TYPE` y del valor de enum requiere Postgres real.

## Migration Plan

1. Crear migración Alembic (`down_revision = c1a2b3d4e5f6`): `create_table correccion_historial` (con índice en `entrega_id`) + `ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS 'CORRECCION_RECORREGIDA'`.
2. `alembic upgrade head`.
3. Deploy del código (modelo, repo, service, router, schema).
4. **Rollback:** `alembic downgrade -1` dropea `correccion_historial`; el valor de enum queda huérfano (inocuo, patrón estándar). Sin pérdida de datos vigentes (la tabla `correcciones` no se toca).

## Open Questions

- ¿Getter con `undefer(Correccion.raw_response)` en el repo vs. acceso lazy al atributo antes del delete? Se decide en apply; ambos satisfacen el spec.
- ¿Repo propio `CorreccionHistorialRepository` vs. métodos nuevos en `CorreccionRepository`? Preferencia: repo propio (imita `EntregaHistorialRepository`), pero es una decisión de estilo sin impacto en el spec.
