# Tasks — autorizacion-por-pertenencia

**Gobernanza: CRÍTICA (Seguridad).** Cada fase se revisa línea por línea con aprobación humana antes de continuar a la siguiente. No encadenar fases sin confirmación.

**Modo TDD estricto.** Para cada tarea de código: safety net (correr los tests existentes del archivo y anotar el baseline) → RED (test que falla primero) → GREEN (mínimo código) → TRIANGULATE (≥2 casos: happy path + edge) → REFACTOR (tests verdes después de cada paso).

Patrón de test de referencia: `backend/tests/unit/core/test_permissions_materia.py` (guards con `db` mockeado vía `AsyncMock`/`MagicMock`) y `backend/tests/unit/routers/test_comisiones_crear_authz.py` (handler invocado directo, service parcheado con `patch`).

---

## 0. Preparación y safety net

- [x] 0.1 Correr `pytest` completo y registrar el baseline de tests que pasan. Si algo ya falla, reportarlo como fallo preexistente y NO arreglarlo en este change.
- [x] 0.2 (VERIFICADO en Postgres real 2026-07-20: 3 cuentas fantasma bloqueadas -carmco/ramsesgir/cmut, last_login NULL, 0 actividad-; 0 usuarios con actividad real quedarian bloqueados. Deploy seguro.) Escribir y correr una query de auditoría (script descartable, no se commitea) que liste usuarios activos no-ADMIN sin ninguna fila en `ComisionTutor` ni en `CoordinadorMateria`. Reportar el resultado: son los usuarios que quedarían bloqueados al desplegar.
- [x] 0.3 Verificar con `grep` que `require_coordinador_of_materia` y `require_tutor_of_comision` no tienen referencias fuera de `app/core/permissions.py` (esperado: 6 autorreferencias). Dejar constancia del conteo.

## 1. Guards nuevos en `permissions.py`

- [x] 1.1 RED: tests de `verificar_acceso_comision_o_materia` en `backend/tests/unit/core/test_permissions_pertenencia.py` — casos ADMIN (no consulta DB), TUTOR asignado (pasa), TUTOR ajeno (403), COORDINADOR de la materia (pasa), COORDINADOR de otra materia (403), GESTOR (403), comisión inexistente (404).
- [x] 1.2 GREEN: implementar `verificar_acceso_comision_o_materia(db, usuario, comision_id) -> None` en `app/core/permissions.py`. Una sola query con LEFT JOIN a `ComisionTutor` y `CoordinadorMateria`; ADMIN retorna antes de consultar; selecciona solo columnas de clave.
- [x] 1.3 RED+GREEN: `verificar_acceso_entrega(db, usuario, entrega_id) -> None` — resuelve `Entrega.comision_id` y delega. Tests: entrega propia OK, entrega ajena 403, entrega inexistente 404.
- [x] 1.4 Test explícito de que `verificar_acceso_entrega` selecciona SOLO `Entrega.id` y `Entrega.comision_id` — assert de que la query compilada no menciona `contenido_consolidado` ni `pdf_contenido_b64` (columnas `deferred`).
- [x] 1.5 RED+GREEN: `verificar_acceso_correccion(db, usuario, correccion_id) -> None` — resuelve `Correccion → Entrega → comision_id` y delega. Tests: propia OK, ajena 403, inexistente 404.
- [x] 1.6 RED+GREEN: `filtrar_entregas_accesibles(db, usuario, entrega_ids) -> tuple[set[int], set[int]]` — devuelve `(permitidos, denegados)` en UNA query. Tests: lote mixto particiona bien, ADMIN recibe todo sin consultar, IDs inexistentes caen en denegados, lote sin ninguno accesible devuelve permitidos vacío.
- [x] 1.7 Test anti-N+1: verificar que `filtrar_entregas_accesibles` con 100 IDs ejecuta exactamente **una** llamada a `db.execute` (assert sobre el mock).
- [x] 1.8 RED+GREEN: `comisiones_visibles_para(db, usuario) -> list[int] | None` — `None` para ADMIN (sin filtro), lista de IDs de comisiones para tutor y coordinador (unión de ambos ejes). Tests para los tres roles + GESTOR (lista vacía).
- [x] 1.9 REFACTOR: revisar que los guards nuevos no dupliquen lógica con `verificar_acceso_comision` / `verificar_acceso_materia_de_comision` existentes. NO modificar los existentes (los usan otros routers). Tests verdes.

## 2. Router `entregas.py` (SEC-002 — 8 endpoints)

- [x] 2.1 Safety net: correr los tests de entregas existentes y anotar el baseline.
- [x] 2.2 RED+GREEN: `GET /entregas/{entrega_id}` y `GET /entregas/{entrega_id}/contenido` — `verificar_acceso_entrega` como primera sentencia. Tests en `backend/tests/unit/routers/test_entregas_authz.py`: tutor propio 200, tutor ajeno 403, coordinador de la materia 200, coordinador ajeno 403, admin 200, GESTOR 403. Verificar explícitamente que `/contenido` NO devuelve el código del alumno en el caso 403.
- [x] 2.3 RED+GREEN: `DELETE /entregas/{entrega_id}` — mismo guard, mismos casos. Verificar que en el 403 el service de borrado nunca se invoca (assert sobre el mock).
- [x] 2.4 RED+GREEN: `POST /entregas/` y `POST /entregas/masiva` — `verificar_acceso_comision_o_materia` sobre el `comision_id` del Form, antes de procesar el archivo. Tests: comisión propia crea, comisión ajena 403 sin tocar el archivo.
- [x] 2.5 RED+GREEN: `GET /entregas/` con `comision_id` explícito → guard (403 si es ajena). Tests para los 4 roles.
- [x] 2.6 RED+GREEN: `GET /entregas/` SIN `comision_id` → scoping. Agregar el filtro por comisiones visibles en `EntregaRepository` con `JOIN` (patrón `comision_repository.py:118-124`), aplicado ANTES del `count`. Tests: tutor ve solo lo suyo, coordinador ve solo sus materias, admin ve todo, y el total paginado refleja el subconjunto (no el total global).
- [x] 2.7 RED+GREEN: `PATCH /entregas/archivar` — particionar con `filtrar_entregas_accesibles`, operar solo sobre permitidos, 403 si ninguno es accesible. Extender `EntregaAccionMasivaResponse` en `app/schemas/entrega.py` con `omitidas: int` y `ids_omitidos: list[int]`. Tests: lote mixto archiva solo lo permitido e informa lo omitido; lote todo-denegado da 403.
- [x] 2.8 RED+GREEN: `DELETE /entregas/masivo` — misma partición y mismo schema extendido. Tests: lote mixto borra solo lo permitido, `ids_omitidos` los lista, lote todo-denegado 403, y el service de borrado recibe SOLO los IDs permitidos (assert sobre el argumento del mock).
- [x] 2.9 REFACTOR: eliminar los `require_any_authenticated(current_user)` que quedaron redundantes y actualizar los docstrings "Authorization: Any authenticated user" de los 8 endpoints para que digan la regla real. Tests verdes.

## 3. Router `correcciones.py` (SEC-001 — 6 endpoints)

- [x] 3.1 Safety net: correr los tests de correcciones existentes y anotar el baseline.
- [x] 3.2 RED+GREEN: `POST /correcciones/entregas/{entrega_id}/corregir` y `.../recorregir` — `verificar_acceso_entrega` antes de resolver credenciales de IA. Tests en `backend/tests/unit/routers/test_correcciones_authz.py` para los 4 roles.
- [x] 3.3 RED+GREEN: `GET /correcciones/{correccion_id}` y `GET /correcciones/entregas/{entrega_id}` — `verificar_acceso_correccion` / `verificar_acceso_entrega`. Tests 4 roles.
- [x] 3.4 RED+GREEN: `PUT /correcciones/{correccion_id}` — `verificar_acceso_correccion`. Test específico: un tutor ajeno intentando cambiar `nota` recibe 403 y el service de edición nunca se invoca.
- [x] 3.5 RED+GREEN: `POST /correcciones/lote` — particionar con `filtrar_entregas_accesibles` **antes** de `background_tasks.add_task`. Extender `CorregirLoteAceptadoResponse` en `app/schemas/correccion.py` con `omitidas` y `entrega_ids_omitidos`; `mensaje` menciona las omitidas cuando `omitidas > 0`.
- [x] 3.6 Test crítico de orden: verificar que la background task recibe SOLO los IDs permitidos (assert sobre los kwargs de `add_task`). El background task no tiene request ni usuario para re-validar.
- [x] 3.7 Verificar que los 2 endpoints de Moodle (`GET /{id}/moodle/preview`, `POST /{id}/moodle`) siguen SIN guard duplicado y que sus tests existentes pasan sin cambios.

## 4. Router `documentos.py` (SEC-004 — 4 endpoints)

- [x] 4.1 Safety net: correr los tests de documentos existentes y anotar el baseline.
- [x] 4.2 RED+GREEN: `GET /documentos/correcciones/{correccion_id}/pdf` — `verificar_acceso_correccion` antes de generar el PDF. Tests en `backend/tests/unit/routers/test_documentos_authz.py` para los 4 roles; en el 403 el `PDFService` nunca se invoca.
- [x] 4.3 RED+GREEN: `GET /documentos/comisiones/{comision_id}/rubricas/{rubrica_id}/pdfs` y `.../excel` — `verificar_acceso_comision_o_materia` sobre el `comision_id` del path. Tests 4 roles.
- [x] 4.4 RED+GREEN: `POST /documentos/pdfs-seleccionados` — particionar con `filtrar_entregas_accesibles`; el ZIP contiene solo lo permitido; los omitidos viajan en el header `X-Entregas-Omitidas`; 403 si ninguno es accesible.
- [x] 4.5 Test de que el ZIP generado NO incluye PDFs de entregas ajenas (assert sobre los IDs que recibe `PDFService.generar_zip_pdfs_seleccionados`).

## 5. Frontend — contratos de lote

- [x] 5.1 Actualizar `frontend/src/features/entregas/types/index.ts`: `EntregaAccionMasivaResponse` suma `omitidas: number` e `ids_omitidos: number[]`; `CorregirLoteAceptadoResponse` suma `omitidas: number` y `entrega_ids_omitidos: number[]`.
- [x] 5.2 Actualizar `frontend/src/features/entregas/services/entregas-service.ts` — tipos de retorno de `archivar`, `deleteMasivo` y `corregirLote`.
- [x] 5.3 Actualizar `frontend/src/features/correcciones/services/correcciones-service.ts` — `descargarPDFsSeleccionados` lee el header `X-Entregas-Omitidas` y devuelve los omitidos en lugar de `Promise<void>`.
- [x] 5.4 `EntregasPage.tsx` → `runArchivarSeleccionados` y `runCorregirMasiva`: cuando `omitidas > 0`, el toast informa cuántas se omitieron por falta de permisos, además del conteo de procesadas.
- [x] 5.5 `EntregasPage.tsx` → `runEliminarSeleccionados`: cuando `omitidas > 0`, usar toast de **advertencia** (no de éxito) con el detalle de lo NO borrado. Requisito explícito: el reporte debe ser prominente, no un campo perdido — el borrado es irreversible.
- [x] 5.6 `EntregasPage.tsx` → `handleDescargarPDFsSeleccionados`: informar los PDFs omitidos en el toast (hoy usa solo el conteo local `selectedCorregidasCount`).
- [x] 5.7 Correr `npm run lint` y `npm run typecheck` en `frontend/`. Sin errores nuevos.

## 6. Limpieza SEC-006

- [x] 6.1 Eliminar `require_coordinador_of_materia` (`permissions.py:268`) y `require_tutor_of_comision` (`:317`). Son placeholders sync que nunca consultaron la DB y son código muerto (confirmado en 0.3).
- [x] 6.2 Limpiar los imports y referencias internas que queden en `permissions.py` tras el borrado.
- [x] 6.3 `grep` en `backend/` (código y tests) confirmando cero referencias a los nombres eliminados.
- [x] 6.4 Test de invariante: toda función de `permissions.py` cuyo nombre refiera a pertenencia a comisión o materia es `async` y recibe una `AsyncSession` como parámetro (introspección con `inspect.signature`). Impide que vuelva a aparecer un guard placeholder.

## 7. Red de seguridad y cierre

- [x] 7.1 Test de cobertura de authz: enumerar programáticamente las rutas de los routers `entregas`, `correcciones` y `documentos` y fallar si alguna no aparece en el inventario de endpoints con test de authz. Protege contra endpoints nuevos agregados sin guard.
- [x] 7.2 Correr `pytest` completo y comparar contra el baseline de 0.1: cero regresiones, más los tests nuevos.
- [x] 7.3 Correr `pytest --cov=app/core/permissions.py` y verificar que los guards nuevos están cubiertos.
- [ ] 7.4 Revisión humana línea por línea del diff completo (gobernanza CRÍTICA) antes de mergear.
- [ ] 7.5 Documentar en el PR el resultado de la auditoría de asignaciones (0.2) y el plan de despliegue: backend primero (campos aditivos, compatible con el frontend actual), frontend después.
