## 1. Preparación y red de seguridad (GATE inicial)

- [x] 1.1 Correr la suite completa y capturar baseline verde ("N passed, M pre-existing failures") antes de tocar nada. Documentar failures preexistentes para no atribuirlos a esta fase.
- [x] 1.2 Escribir un test de precondición que verifique que NO existen filas con `universidad_id IS NULL` en las 9 entidades scopeadas (materias, comisiones, entregas, correcciones, unidades, rubricas, examenes_materia, cierre_cursada_runs, avance_snapshots). Sostiene la Decisión D7-(A) estricto. Si falla, escalar antes de continuar.
- [x] 1.3 Crear helpers/fixtures de test de aislamiento: factory para crear una segunda universidad (UniB) con su árbol de datos (materia → comisión → entrega → corrección, + rúbrica/unidad/examen/cierre/avance), y usuarios de UniA y UniB, más un superadmin. Base de TODOS los tests de aislamiento posteriores.

## 2. Check de pertenencia por id (404) en permissions.py

- [x] 2.1 RED: test unitario de `verificar_pertenencia_universidad(recurso, ctx)` — recurso de otra universidad ⇒ 404; recurso None ⇒ 404; recurso de la universidad activa ⇒ pasa; `ctx.universidad_id is None` (superadmin) ⇒ pasa siempre.
- [x] 2.2 GREEN: implementar `verificar_pertenencia_universidad` en `permissions.py` (semántica 404). NO tocar `verificar_materia_universidad_activa` (409, Fase 3, sigue vivo para sync Moodle).
- [x] 2.3 TRIANGULATE: cubrir NULL en `recurso.universidad_id` (dato legado) y superadmin con universidad elegida (filtra). REFACTOR sin cambiar comportamiento. (Refactor adicional: firma final toma `universidad_id_activa: int | None` en vez de `ctx` completo, consistente con `verificar_materia_universidad_activa` y con D4.)

## 3. Scoping de repositorio: Materia

- [x] 3.1 RED: test de aislamiento — usuario de UniA lista materias y NO ve materias de UniB; get materia de UniB por id ⇒ 404; superadmin sin universidad ve ambas.
- [x] 3.2 GREEN: sumar `universidad_id: int | None = None` (keyword-only) a `get_all`, `get_by_codigo`, `get_con_moodle`, `get_by_cuatrimestre`, `get_by_cuatrimestres`, `get_configuradas_dashboard`, `get_by_coordinador`, `contar_por_materias` en `materia_repository.py`; aplicar el filtro a la lista `conditions` compartida datos+count.
- [x] 3.3 Propagar en `materia_service.py` y `materias.py` (montar `ctx` donde falte, pasar `ctx.universidad_id`); aplicar check de pertenencia 404 en accesos por id.
- [x] 3.4 TRIANGULATE + verificar invariante mono-tenant (mismos resultados con 1 universidad). REFACTOR.

## 4. Scoping de repositorio: Comisión (incluye deuda comisiones.py)

- [x] 4.1 RED: red de caracterización de `listar_comisiones`, `obtener_comision`, `actualizar_moodle_comision` (comportamiento actual con rol inline) + test de aislamiento UniA/UniB.
- [x] 4.2 GREEN repo: sumar `universidad_id` a `get_all`, `contar_tutores_entregas`, `contar_comisiones_activas_por_materia`, `get_by_materia`, `get_by_materia_con_tutores`, `get_by_tutor`, `get_moodle_habilitadas_de_tutor`, `get_by_materia_nombre_anio` en `comision_repository.py`.
- [x] 4.3 DEUDA (D6): migrar `listar_comisiones` de `current_user.rol` a `ctx.rol` (+ bypass `_acceso_total`), montar `ctx`, pasar `ctx.universidad_id`.
- [x] 4.4 DEUDA (D6): migrar `obtener_comision` — reemplazar chequeo inline `current_user.rol == TUTOR` por guard de pertenencia (`verificar_acceso_comision_o_materia`) + check pertenencia universidad 404.
- [x] 4.5 DEUDA (D6): migrar `actualizar_moodle_comision` — reemplazar `current_user.rol` inline por `ctx` (`_acceso_total`/guard) + scoping por universidad.
- [x] 4.6 Propagar en `comision_service.py`. TRIANGULATE + invariante. REFACTOR. Confirmar que los endpoints ya migrados en Fase 2 (crear/actualizar/eliminar/restaurar/asignar_tutores) heredan `universidad_id` correctamente.

## 5. Scoping de repositorio: Entrega

- [x] 5.1 RED: test de aislamiento (list, export, conteos) UniA/UniB + get por id ⇒ 404 cross-tenant.
- [x] 5.2 GREEN: sumar `universidad_id` a `get_all`, `get_all_for_export`, `get_by_rubrica_alumno`, `get_subidas_ids_by_tutor`, `contar_errores_by_tutor`, `contar_estados_by_tutor` en `entrega_repository.py` (calcar el patrón existente `comisiones_visibles`).
- [x] 5.3 Propagar en `entrega_service.py` y routers de entregas; check 404 en accesos por id.
- [x] 5.4 TRIANGULATE + invariante. REFACTOR.

## 6. Scoping de repositorio: Corrección

- [x] 6.1 RED: test de aislamiento (list, export, estadísticas, pendientes Moodle) + get por id ⇒ 404.
- [x] 6.2 GREEN: sumar `universidad_id` a `get_all`, `get_all_for_export`, `get_statistics_by_rubrica`, `get_pendientes_subida_moodle`, `contar_no_vinculadas_moodle`, `get_by_entrega_ids_corregidas` en `correccion_repository.py`.
- [x] 6.3 Propagar en `correccion_service.py` y routers; check 404 por id.
- [x] 6.4 TRIANGULATE + invariante. REFACTOR.

## 7. Scoping de repositorio: Rúbrica, Unidad, Examen

- [x] 7.1 RED: tests de aislamiento por entidad (rúbrica, unidad, examen) UniA/UniB + 404 por id.
- [x] 7.2 GREEN Rúbrica: `universidad_id` en `get_all`, `get_by_materia`, `get_by_materia_tipo_numero`, `get_moodle_habilitadas_por_materias` (`rubrica_repository.py`); propagar en `rubrica_service.py`/routers; check 404.
- [x] 7.3 GREEN Unidad: `universidad_id` en `get_by_materia` (`unidad_repository.py`); propagar en `unidad_service.py`/router; check 404. Confirmar que `verificar_acceso_unidad` sigue coherente.
- [x] 7.4 GREEN Examen: `universidad_id` en `get_by_materia` (`examen_repository.py`); propagar en `examen_service.py`/router; check 404.
- [x] 7.5 TRIANGULATE + invariante para las tres. REFACTOR.

## 8. Scoping de repositorio: CierreCursada y Avance

- [x] 8.1 RED: test de aislamiento — runs de cierre y snapshots de avance de UniB no visibles para UniA; get por id ⇒ 404.
- [x] 8.2 GREEN Cierre: `universidad_id` en `listar_runs` (`cierre_cursada_repository.py`); propagar en `cierre_cursada_service.py`/router; check 404 en `get_run`.
- [x] 8.3 GREEN Avance: `universidad_id` en `get_ultimo_snapshot`, `get_ultimos_snapshots`, `contar_por_estado` (`avance_repository.py`); propagar en `dashboard_lectura_service.py`/router; check de "no visible" para el snapshot (no hay `obtener_run` por id suelto para avance, se accede siempre vía materia_id ya scopeado).
- [x] 8.4 TRIANGULATE + invariante. REFACTOR.

## 9. Scoping de agregaciones: Dashboard

- [x] 9.1 RED: test de aislamiento de dashboard — métricas de un miembro de UniA cuentan solo UniA; superadmin sin universidad agrega ambas.
- [x] 9.2 GREEN: sumar `universidad_id` a `get_admin_counts`, `contar_comisiones_activas_en_materias`, `contar_rubricas_activas_en_materias`, `contar_pendientes_en_materias`, `get_progreso_por_comision_de_materias`, `contar_pendientes_en_comisiones`, `contar_corregidas_en_comisiones`, `get_detalle_comisiones` (`dashboard_repository.py`). `get_admin_counts` además scopea `usuarios` vía membresía activa en `UsuarioUniversidad` (Usuario no tiene `universidad_id` propio).
- [x] 9.3 Propagar en `dashboard_service.py`/`dashboard_lectura_service.py` y `dashboard.py`/`dashboard_gestores.py`. Confirmado que ninguna métrica queda global salvo el superadmin sin universidad.
- [x] 9.4 TRIANGULATE + invariante. REFACTOR.

## 10. Barrido anti-fuga (queries ad-hoc) — OQ5

- [x] 10.1 Grepear `select(` fuera de `app/repositories/` (posibles violaciones ARCH-001 preexistentes que crucen entidades scopeadas sin `universidad_id`). Listar hallazgos. **Resultado: CERO hallazgos** — todo `select()`/`.execute()` de SQLAlchemy vive en `app/repositories/` (ARCH-001 se cumple sin excepciones) más `app/core/permissions.py` (capa transversal de autorización, ya cubierta/extendida en el grupo 2). Los 2 matches en `app/models/` son comentarios, no código.
- [x] 10.2 Para cada query ad-hoc riesgosa: mover el filtro al repository o justificar por qué es segura. Documentar decisión por caso. **N/A — no se encontraron queries ad-hoc.** Sí se encontró y cerró un hallazgo relacionado no anticipado: ningún service de creación (`crear_comision`, `crear_entrega`×3, `crear_correccion`, `crear_unidad`/`sincronizar`, `crear_rubrica`×2, `crear_examen`, `generar` cierre/avance) seteaba `universidad_id` al construir la fila — invisible mientras el modelo era `Mapped[int | None]`, pero hubiera roto en Postgres real (NOT NULL desde R7). Se cerró propagando `universidad_id` desde el padre ya cargado en cada service (ver design.md, hallazgo adicional bajo OQ4).

## 11. Suite de aislamiento 2-universidades (GATE final)

- [x] 11.1 Test integral que recorre CADA endpoint público de las 9 entidades: usuario de UniA no ve NADA de UniB (listados vacíos de UniB, 404 al acceder por id a recursos de UniB). Implementado en `tests/integration/test_multi_tenant_aislamiento.py` a nivel repository+service (el filtro real vive ahí, ARCH-001); los routers son wiring fino ya cubierto por sus tests unitarios propios.
- [x] 11.2 Test integral: superadmin sin universidad activa ve datos de ambas universidades en listados y dashboards.
- [x] 11.3 Test: superadmin con UniA seleccionada queda scopeado a UniA.
- [x] 11.4 Correr la suite completa y confirmar 0 regresiones contra el baseline de 1.1 (mismas failures preexistentes, nada nuevo roto). Este es el gate para el checkpoint humano. **1578 passed, 1 pre-existing failure (idéntica a la de 1.1) — 0 regresiones.**

## 12. Cierre

- [x] 12.1 Verificar máx 500 LOC/archivo en los repositories tocados; anotar los que ya estaban por encima (deuda preexistente, no de esta fase). Over-500 preexistente (confirmado con `git diff --numstat`, ninguno cruzó el umbral por esta fase): `permissions.py` (730→787), `comision_repository.py` (637→665), `entrega_repository.py` (595→627), `materia_repository.py` (621→649), `comision_service.py` (546→602), `materia_service.py` (516→578), `correccion_service.py` (1425→1441), `entrega_service.py` (1168→1204). `correccion_repository.py` pasó de 509→530 (ya estaba sobre el límite). `rubrica_repository.py` se mantiene bajo el límite (424→441).
- [x] 12.2 Confirmar que el guard 409 de Fase 3 (`verificar_materia_universidad_activa`) sigue intacto y que `permissions.py` no perdió cobertura. Confirmado: 8/8 tests de `test_permissions_oq1_materia_universidad.py` verdes, 172/172 tests de `tests/unit/core/` verdes.
- [x] 12.3 Preparar reporte de equivalencia (invariante mono-tenant) + resumen de las Open Questions resueltas para el checkpoint humano antes de archivar. Ver design.md (sección Open Questions, todas marcadas RESUELTO) y el reporte final del apply.
