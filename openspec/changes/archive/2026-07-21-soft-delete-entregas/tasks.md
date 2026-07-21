> **Gobernanza: CRÍTICA** — borrado de datos de alumnos / auditoría. Cada tarea de código requiere aprobación humana antes de escribir. TDD estricto con `pytest`.
> **Baseline conocido de la suite**: correr con `--continue-on-collection-errors`. Hay 1 fallo preexistente (`test_pendientes`, JSONB/SQLite) y 3 errores de colección fósiles (`test_entrega_service`, `test_consolidacion_service`, `test_rubrica_service`) del commit inicial. NO arreglarlos: son deuda aparte.

## 0. Safety net y baseline

- [x] 0.1 Correr `pytest --continue-on-collection-errors -q` y capturar el baseline (nº passing + los fallos/errores fósiles ya conocidos), para probar que el change no rompe lo que andaba.
- [x] 0.2 Correr los tests existentes de entregas (repo/service/router) y registrar cuántos pasan como red de seguridad de los archivos a tocar.
- [x] 0.3 Confirmar `alembic current` == `b9c4d1e5f3a6` y `alembic heads` sin múltiples heads.

## 1. Modelo, migración y tipo de auditoría

- [x] 1.1 RED: test de modelo que verifica que `Entrega` expone `deleted_at` (default `None`) y la property `is_deleted`.
- [x] 1.2 GREEN: hacer que `Entrega` (`app/models/entrega.py`) herede `SoftDeleteMixin` además de `TimestampMixin`.
- [x] 1.3 Agregar `ENTREGA_ELIMINADA` y `ENTREGA_RESTAURADA` a `TipoActividadEnum` (`app/models/enums.py`).
- [x] 1.4 Generar migración Alembic (`alembic revision --autogenerate -m "add deleted_at to entregas"`) con `down_revision = "b9c4d1e5f3a6"`; verificar que el upgrade sea solo `add_column("entregas", "deleted_at", DateTime, nullable=True)` y el downgrade `drop_column`. SIN índice (ver design §6).
- [x] 1.5 Aplicar `alembic upgrade head` en la DB de dev y verificar que la columna existe y que `alembic downgrade -1` / `upgrade head` es reversible limpio.

## 2. Repositorio: soft_delete / restore / hard + filtros de lectura

- [x] 2.1 RED: tests de repo para `soft_delete(entrega)` (setea `deleted_at`), `restore(entrega)` (lo pone `None`) y `soft_delete_by_ids(ids)`.
- [x] 2.2 GREEN: implementar `soft_delete`, `restore`, `soft_delete_by_ids` en `EntregaRepository`; dejar el borrado físico actual como brazo `hard_delete`/`hard_delete_by_ids` explícito.
- [x] 2.3 RED: tests que verifican que `get_all` excluye entregas con `deleted_at` seteado y que el `total`/count coincide con las filas devueltas (aislamiento del total, SEC-002).
- [x] 2.4 GREEN: agregar `Entrega.deleted_at.is_(None)` a la lista `conditions` compartida de `get_all` (datos + count).
- [x] 2.5 RED+GREEN: `get_by_id` excluye borradas por defecto y acepta `include_deleted=True` para el restore; `get_all_for_export` excluye borradas. TRIANGULAR con caso borrada + caso no borrada + caso `include_deleted`.
- [x] 2.6 RED+GREEN: verificar ortogonalidad `archivado` vs `deleted_at` (entrega archivada-no-borrada sigue rigiéndose por el filtro de archivado; borrada se excluye siempre).

## 3. Service: bifurcación por ALLOW_HARD_DELETE + auditoría

- [x] 3.1 RED: test de `eliminar_entrega` con `ALLOW_HARD_DELETE=False` → setea `deleted_at`, NO borra la `Correccion`, registra `Actividad` `ENTREGA_ELIMINADA`.
- [x] 3.2 RED: test de `eliminar_entrega` con `ALLOW_HARD_DELETE=True` → borra físico con cascada (comportamiento previo) y registra `Actividad`.
- [x] 3.3 RED: test de doble borrado lógico → `400` "ya está eliminada" sin pisar el `deleted_at` original; e id inexistente → `404`.
- [x] 3.4 GREEN: implementar la bifurcación en `eliminar_entrega` calcada de `MateriaService.eliminar_materia`, instanciando `ActividadService(self.db)` y registrando la actividad (con `usuario_id` del actor).
- [x] 3.5 RED+GREEN: `eliminar_entregas_masivo` — bifurca por flag, borra lógico solo las permitidas (partición SEC-002 vía `filtrar_entregas_accesibles`), registra una `Actividad` por entrega procesada, devuelve procesadas/omitidas.
- [x] 3.6 RED+GREEN: `restaurar_entrega(entrega_id, usuario)` — lee con `include_deleted=True`, `404` si no existe, `400` si no está borrada, setea `deleted_at=None`, registra `ENTREGA_RESTAURADA`.
- [x] 3.7 TRIANGULAR + REFACTOR: cubrir happy path + edge cases de cada método y limpiar duplicación entre borrado individual/masivo sin cambiar comportamiento (tests verdes en cada paso).

## 4. Router: DELETE existente + endpoint restore

- [x] 4.1 RED: test de router del `POST /entregas/{id}/restore` — happy path (con pertenencia), `403` sin pertenencia, `404` id inexistente, `400` entrega no borrada.
- [x] 4.2 GREEN: agregar `POST /{id}/restore` en `app/routers/entregas.py` reutilizando `verificar_acceso_entrega` (que ya ve entregas borradas) y delegando en `EntregaService.restaurar_entrega`. Definir en apply si el guard se endurece a solo-admin (open question del design).
- [x] 4.3 Verificar que el contrato HTTP del DELETE (individual y masivo) no cambia: mismos códigos y forma de respuesta (`EntregaAccionMasivaResponse`), ahora con efecto de baja lógica.

## 5. Frontend (mínimo viable)

- [x] 5.1 Verificar que el flujo de "eliminar" del frontend sigue funcionando sin cambios (la entrega desaparece del listado igual).
- [x] 5.2 Documentar como follow-up (no implementar acá) la UI de papelera/restore; dejar anotado que el restore ya existe por API.

## 6. Verificación end-to-end

- [x] 6.1 Correr `pytest --continue-on-collection-errors -q` completo y comparar contra el baseline de 0.1 (sin regresiones nuevas; los fósiles siguen igual).
- [x] 6.2 (verificado contra Postgres real via service, 9/9 OK) Prueba manual e2e: borrar una entrega (con corrección) → desaparece del listado y del export, la fila y la corrección siguen en DB, hay `Actividad` `ENTREGA_ELIMINADA`; restaurar → reaparece con su nota, hay `Actividad` `ENTREGA_RESTAURADA`.
- [x] 6.3 (cubierto por unit tests; NO se corre e2e destructivo sobre datos reales) Prueba con `ALLOW_HARD_DELETE=True`: el borrado vuelve a ser físico con cascada y también registra `Actividad`.
- [x] 6.4 `openspec validate soft-delete-entregas --strict` en verde.
