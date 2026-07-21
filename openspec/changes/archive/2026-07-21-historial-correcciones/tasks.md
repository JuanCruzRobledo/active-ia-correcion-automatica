## 0. Safety net y baseline

- [x] 0.1 Correr la suite backend con `pytest --continue-on-collection-errors -q` y capturar el baseline. Conocido y NO se arregla acá: 1 fallo preexistente (`test_pendientes` JSONB/SQLite) + 3 errores de colección fósiles. Cualquier fallo NUEVO fuera de esos = regresión.
- [x] 0.2 Correr los tests que tocan `correccion_service` / `correccion_repository` y anotar cuántos pasan (baseline verde de lo que se va a modificar).

## 1. Modelo + migración + enum (RED → GREEN)

- [x] 1.1 RED: test unitario de mapeo del modelo `CorreccionHistorial` (columnas esperadas, `entrega_id` indexado, `raw_response` deferred) contra el shim SQLite (`@compiles` JSONB/ARRAY, ver `tests/unit/repositories/test_perf002_entrega_count.py`). Debe fallar por inexistencia del modelo.
- [x] 1.2 GREEN: crear `CorreccionHistorial` en `app/models/correccion.py` con las columnas de D2 (id, entrega_id index, nota, criterios_json, fortalezas, recomendaciones, comentario_general, nota_antes_penalizaciones, condicion_desaprobacion_aplicada, penalizaciones_aplicadas, editado_manualmente, corregido_por_id, raw_response deferred, correccion_creada_en, reemplazada_en, reemplazada_por_id) + relationships. Registrar el modelo donde corresponda para que Alembic lo vea.
- [x] 1.3 Agregar `CORRECCION_RECORREGIDA` a `TipoActividadEnum` (`app/models/enums.py`).
- [x] 1.4 Generar la migración Alembic (`down_revision = 'c1a2b3d4e5f6'`): `create_table correccion_historial` con índice en `entrega_id`. Verificar el autogenerate.
- [x] 1.5 Editar la migración A MANO: agregar `op.execute("ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS 'CORRECCION_RECORREGIDA'")` (autogenerate NO lo detecta; patrón de `c1a2b3d4e5f6`). `downgrade` dropea la tabla; el valor de enum queda huérfano (documentar, inocuo).
- [x] 1.6 TRIANGULATE: aplicar `alembic upgrade head` y `alembic downgrade -1` contra Postgres real; confirmar create/drop de la tabla y que el enum acepta el valor nuevo.

## 2. Repositorio del historial (RED → GREEN → TRIANGULATE)

- [x] 2.1 RED: test de `CorreccionHistorialRepository.create` (persiste el snapshot) — falla por inexistencia.
- [x] 2.2 GREEN: crear `app/repositories/correccion_historial_repository.py` con `create(historial)` (imita `EntregaHistorialRepository`).
- [x] 2.3 RED: test de `list_by_entrega` (o `get_by_entrega`) que devuelve las versiones ordenadas por `reemplazada_en DESC` y SIN cargar `raw_response` (deferred).
- [x] 2.4 GREEN: implementar `list_by_entrega` con `selectinload` de autor/reemplazado_por y sin `undefer(raw_response)`.
- [x] 2.5 TRIANGULATE: test con 0 versiones (lista vacía) y con 2 versiones (orden correcto). Verificar que `raw_response` NO viene en el listado.
- [x] 2.6 (Si se opta por getter con undefer para el snapshot) RED+GREEN: método del repo que trae la `Correccion` vigente con `undefer(Correccion.raw_response)` para poder snapshotear el crudo antes del delete (D3).

## 3. Servicio: snapshot en corregir_individual + Actividad (RED → GREEN → TRIANGULATE)

- [x] 3.1 SAFETY NET: correr los tests existentes de `corregir_individual` / `recorregir`; confirmar verdes antes de tocar el service.
- [x] 3.2 RED: test de `corregir_individual` sobre una entrega CON corrección existente → debe crear 1 fila en `correccion_historial` con la nota anterior, ANTES de borrar. Falla (aún no hay snapshot).
- [x] 3.3 GREEN: en `corregir_individual`, entre `get_by_entrega_id` y `delete` (`correccion_service.py:332-338`), construir el snapshot y persistirlo. `reemplazada_por_id = corregido_por_id`, `correccion_creada_en = existing.created_at`, `reemplazada_en = utcnow()`.
- [x] 3.4 RED: test que verifica que `editado_manualmente=True` y `raw_response` de la corrección saliente quedan preservados en el snapshot. Cubrir el gotcha del deferred: leer `raw_response` ANTES del delete (D3), evitar DetachedInstanceError.
- [x] 3.5 GREEN: asegurar la carga de `raw_response` (getter con undefer o acceso lazy antes del delete) y su copia al snapshot.
- [x] 3.6 RED: test de que se registra `Actividad` `CORRECCION_RECORREGIDA` con `entidad_id`=entrega y `usuario_id`=actor de la recorrección.
- [x] 3.7 GREEN: llamar `ActividadService.registrar_actividad(CORRECCION_RECORREGIDA, ...)` en el mismo bloque.
- [x] 3.8 TRIANGULATE (crítico): test de PRIMERA corrección (sin corrección previa) → NO crea fila en `correccion_historial` NI Actividad `CORRECCION_RECORREGIDA`; la entrega queda CORREGIDA. Confirma que el snapshot sólo corre en recorrecciones.

## 4. Router GET + schema de respuesta (RED → GREEN → TRIANGULATE)

- [x] 4.1 RED: test del schema de respuesta del historial (imita `HistorialResponse`/`HistorialItem`): `entrega_id`, `total_versiones`, `versiones[]` con id, nota, editado_manualmente, autor, correccion_creada_en, reemplazada_en, reemplazada_por_nombre; SIN `raw_response`.
- [x] 4.2 GREEN: crear el schema en `app/schemas/correccion.py`.
- [x] 4.3 RED: test del endpoint `GET` de historial por entrega (feliz: devuelve las versiones ordenadas) — falla por inexistencia de la ruta.
- [x] 4.4 GREEN: agregar el endpoint en `app/routers/correcciones.py` con `await verificar_acceso_entrega(db, current_user, entrega_id)` antes de servir; delegar en un método de servicio que use el repo del historial.
- [x] 4.5 TRIANGULATE: test de 403 para usuario sin acceso a la entrega; test de lista vacía (entrega sin recorrecciones, total 0, no error).
- [x] 4.6 Test de que el historial de una entrega con soft delete (`deleted_at` no nulo) sigue siendo consultable (el guard no filtra `deleted_at`).

## 5. Verificación e2e y refactor final

- [x] 5.1 REFACTOR: revisar nombres, duplicación, docstrings (estilo `EntregaHistorial`/`HistorialService`); tests verdes tras cada cambio. Respetar el límite de 500 LOC por archivo.
- [x] 5.2 (e2e Postgres real 5/5 OK, no destructivo) E2E contra Postgres REAL: correr una recorrección completa (entrega ya corregida → recorregir) y verificar en DB: 1 fila en `correccion_historial`, 1 Actividad `CORRECCION_RECORREGIDA`, 1 sola corrección vigente. Esto ejercita el `ALTER TYPE` (no cubierto por SQLite).
- [x] 5.3 Correr la suite completa y confirmar que el baseline de 0.1 no empeoró (sólo los fallos/errores fósiles conocidos).
- [x] 5.4 `openspec validate historial-correcciones --strict` y `alembic upgrade head` limpios.
