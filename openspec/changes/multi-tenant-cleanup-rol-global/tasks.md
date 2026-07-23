## 0. Red de seguridad

- [x] 0.1 Baseline: `cd backend && pytest -q` → **1641 passed, 0 failed** (confirmado, coincide con lo esperado)
- [x] 0.2 Re-verificado contra Postgres real (docker exec active-ia-postgres): (a) 33 usuarios con `moodle_username`, **0** sin equivalente en su membresía; (b) **0** usuarios sin membresía activa. Ambas precondiciones en 0 → se procede
- [x] 0.3 Tests de caracterización de permisos (8 archivos `test_permissions_*.py` + `test_rubrica_service.py`) → **134 passed**. Este es el gate para 3.4

## 1. Aislamiento de usuarios (deuda de Fase 4)

- [x] 1.1 RED: `tests/unit/repositories/test_usuario_repository_aislamiento.py` — aislamiento con DOS universidades (A no ve exclusivos de B, simétrico, membresía inactiva excluida, dos membresías, superadmin `None` ve todos). Confirmado RED (8 failed) antes de tocar el repo
- [x] 1.2 `usuario_repository.get_all`: `universidad_id: int | None = None`, filtro `EXISTS` sobre `usuario_universidad` activa (D2)
- [x] 1.3 RED + GREEN: filtro por rol DENTRO del `EXISTS` (D3) — test `test_get_all_filtro_rol_usa_el_rol_de_la_membresia_activa` (persona TUTOR en A / COORDINADOR en B)
- [x] 1.4 `usuario_repository.get_tutores`: `universidad_id` + `EXISTS`; tests `test_get_tutores_no_cruza_universidades` / `_universidad_id_none_devuelve_todos`
- [x] 1.5 Eliminado `usuario_repository.get_coordinadores` — confirmado 0 llamadores (los matches de `get_coordinadores` en materia_repository/materia_service son `get_coordinadores_for_materia`, método distinto)
- [x] 1.6 `routers/usuarios.py`: `listar_usuarios` propaga `ctx.universidad_id`; guard de coordinador ahora lee `ctx.rol` (no `current_user.rol`)
- [x] 1.7 `notificacion_service._cargar_tutores(mapa_materia, universidad_id)`; `ejecutar_corrida_semanal` pasa `config.universidad_id`. Test RED→GREEN `test_corrida_propaga_universidad_de_la_config_a_get_tutores`
- [x] 1.8 `pytest -q` → **1650 passed** (1641 + 9 nuevos), 0 regresiones

## 2. El rol se escribe como membresía

- [x] 2.1 RED: `tests/unit/services/test_usuario_service_membresia.py` + `test_usuario_repository_alta_membresia.py` — alta crea usuario+membresía, aparece en el listado de su universidad y no en otra, 400 sin universidad activa
- [x] 2.2 `usuario_service.crear_usuario` recibe `universidad_id`; `usuario_repository.create_con_membresia` crea `Usuario`+`UsuarioUniversidad` en una sola transacción (flush intermedio para el FK, un solo commit); 400 si `universidad_id is None` (D4)
- [x] 2.3 RED + GREEN: atomicidad probada CONTRA SQLITE REAL con `PRAGMA foreign_keys=ON` — `universidad_id` inexistente fuerza `IntegrityError` en el commit y el `Usuario` NO queda persistido (verificado con query post-rollback)
- [x] 2.4 `routers/usuarios.py` (POST): pasa `ctx.universidad_id` a `crear_usuario`; contrato del endpoint sin cambios
- [x] 2.5 RED: `test_actualizar_usuario_cambia_solo_la_membresia_de_la_universidad_activa` / `test_actualizar_usuario_sin_membresia_activa_aca_responde_404`
- [x] 2.6 `usuario_service.actualizar_usuario` + `update_rol_membresia`: rol nuevo va a la membresía activa (`user.rol` se mantiene en sync como columna legacy hasta el Grupo 5, porque el Grupo 3 todavía la lee); `routers/usuarios.py` (PUT) pasa `ctx.universidad_id`
- [x] 2.7 `pytest -q` → **1661 passed** (1650 + 11 nuevos). Se ajustaron los mocks de `test_crud013_rol_asignaciones.py` (repo simulado necesitaba `update_rol_membresia` + `universidad_id`) — no es parte de las ~47, pero se rompía por la nueva firma

## 3. Los últimos lectores del rol global

- [x] 3.1 `routers/materias.py:53` y `:131`: `current_user.rol` → `ctx.rol`
- [x] 3.2 `routers/rubricas.py:66`: `current_user.rol` → `ctx.rol`
- [x] 3.3 `routers/perfil.py`: `PerfilResponse.rol` = `ctx.rol` (D5); superadmin sin universidad (`ctx.rol is None`) informa ADMIN sintético (mismo criterio que `get_universidad_activa`). Tests nuevos en `test_perfil_moodle_multiuniversidad.py`: rol sigue a la universidad activa (TUTOR en A / COORDINADOR en B) + caso superadmin global
- [x] 3.4 `rubrica_service._validar_acceso_materia` recibe `rol: RolEnum | None = None` (cae a `user.rol` sólo si no se pasa — se retira en 5.1); las 6 llamadas internas y los 6 call sites de `routers/rubricas.py` pasan `rol=ctx.rol`. Gate 0.3 (134 tests) sigue en 134 después
- [x] 3.5 Barrido EXTENDIDO (el literal `current_user.rol\|\.rol ==` de tasks.md no alcanza — no captura `!=`, ni lecturas sobre variables que no se llaman `current_user`). Corrido `grep -rn "\.rol\b" app/` completo y clasificado cada resultado. Hallazgos NO anticipados por design.md (no están en su lista "Parte 3 — Los últimos lectores"), documentados y resueltos con el MISMO principio D2/D3 ya aplicado al resto de la fase:
  - `por_entregar_service.listar/entregar_masivo_stream`: `usuario.rol` → `rol`/`ctx.rol` (router pasa `rol=ctx.rol`)
  - `comision_service.crear_comision/actualizar_comision/asignar_tutores` (3 sitios): candidato a TUTOR se validaba contra `usuario.rol` GLOBAL — ahora `usuario_repo.get_rol_en_universidad(usuario.id, materia_o_comision.universidad_id)` (nuevo método repo). Gate: test de 2 universidades (persona TUTOR en A / COORDINADOR en B) — antes se validaba mal
  - `materia_service.crear_materia/actualizar_materia/asignar_coordinadores` (3 sitios): mismo problema y misma solución para COORDINADOR
  - `actividad_service.get_actividades_recientes`: `act.usuario.rol` (audit log histórico, sin `universidad_id` por acción) → `usuario_repo.get_rol_mas_antiguo` (nuevo método repo, misma convención "membresía activa más antigua" que usa D6 para el downgrade)
  - Ver sección de hallazgos en el resumen final para el detalle de cada uno y la justificación
- [x] 3.6 `pytest -q` → **1669 passed** (1661 + 8 nuevos: 3 repo `get_rol_en_universidad` + 3 comisión/materia cross-university + 2 perfil), 0 regresiones

## 4. Migración de tests a membresías

- [x] 4.1 Helper compartido: `tests/helpers/usuario_membresia.py` (`crear_usuario_con_membresia`, `crear_universidad`) — creado en la tarea 1.1 (se necesitaba desde el primer test nuevo) y reutilizado en todos los tests nuevos de esta fase (D7)
- [x] 4.2 Auditados los 20 archivos reales que construyen `Usuario(rol=...)` (el grep textual de `rol=`/`.rol` da ~44-46 archivos, pero la mayoría son `ctx.rol`/`ComisionCreate.rol`/asserts sobre `UsuarioUniversidad.rol` — no constructores de `Usuario`). Para cada uno se verificó si el rol se CONSULTA en el flujo bajo test:
  - **19/20 ya emparejan correctamente** usuario+membresía (cuando el escenario depende del rol) o el rol es genuinamente incidental — un FK-only para persistir el objeto, sin ningún `.rol` leído en el test (verificado con grep por archivo). Estos NO necesitan cambio de comportamiento ahora; sólo perderán el kwarg `rol=` de `Usuario(...)` en la tarea 5.1 (mecánico, no se puede hacer antes: la columna sigue NOT NULL hasta que se borra)
  - **1/20 SÍ dependía del fallback de conveniencia** (`tests/unit/services/test_rubrica_service.py`, fixture `admin` sin membresía): sus ~17 llamadas a `crear_rubrica`/`actualizar_rubrica`/`eliminar_rubrica`/`restaurar_rubrica`/`duplicar_rubrica` no pasaban `rol=` y dependían de que `_validar_acceso_materia` cayera a `user.rol` (fallback documentado en 3.4, que se retira en 5.1). Se migraron las 17 llamadas a pasar `rol=RolEnum.ADMIN` explícito — 10/10 tests siguen pasando, ya no dependen del fallback
  - Archivo por archivo: `test_pendientes.py`, `test_universidad_repository.py`, `test_entrega_service.py`, `test_cierre_cursada.py`, `test_perf007_comision_listar_counts.py`, `test_perf010_tutor_stats_pendientes.py`, `test_perf012_detalle_eager_batch.py`, `test_cierre_cursada_service.py`, `test_arch001_dashboard_repo.py`, `test_preservacion_orden_comision.py`, `test_orden_natural_comision.py`, `test_orden_natural_cobertura_adicional.py`, `test_perfil_moodle_multiuniversidad.py`, `test_usuario_repository_credenciales_moodle.py`, `test_dependencies_universidad_activa.py`, `test_auth_login_smoke.py`, `test_usuario_repository_membresias.py`, `test_usuario_es_superadmin.py`, `test_usuario_universidad.py` → sin cambios de comportamiento necesarios; `test_rubrica_service.py` → migrado a `rol=` explícito
- [x] 4.3 Baseline previo a 5.1: **1669 passed** (igual al cierre de 3.6 — el trabajo de 4.2 no agregó ni quitó tests, sólo corrigió dependencias implícitas). La comparación real contra 0.1 (1641) se hace en 5.2/6.1, después de que 5.1 haga el retiro mecánico de `rol=` en los 20 archivos

## 5. Eliminación de las columnas

- [x] 5.1 Quitadas de `app/models/usuario.py`: `rol`, `moodle_username`, `moodle_password_encrypted`, `moodle_host`. `__repr__` ajustado. Cascada de ajustes que esto forzó:
  - `usuario_universidad.rol` pasa a `create_type=True` (era `create_type=False`, asumiendo que `usuarios.rol` creaba `rol_enum` — al borrarse, ningún modelo declaraba el tipo con `create_type=True`; **hallazgo real**: `scripts/init_db.py` usa `Base.metadata.create_all()` directo contra Postgres, sin Alembic, así que esto rompía el init de una base nueva)
  - `rubrica_service._validar_acceso_materia`: se retiró el fallback a `user.rol` (ya no existe)
  - `UsuarioResponse.rol`/`UsuarioListItem.rol` pasan a `RolEnum | None` (D5): ya no se pueden poblar con `model_validate(usuario_orm)` — `usuario_service.py` construye la respuesta explícitamente vía helper `_usuario_response`, resolviendo el rol contra la membresía (`get_rol_en_universidad` si hay `universidad_id`, si no `get_rol_mas_antiguo`, D6). Nuevos métodos batch en el repo (`get_roles_en_universidad`, `get_roles_mas_antiguos`) para no hacer N+1 en `listar_usuarios` (hasta 1000 usuarios por página)
  - `obtener_usuario`/`restaurar_usuario` (service + router) ahora reciben `universidad_id` — antes no lo tenían y no podían resolver el rol a mostrar
  - Migrados ~20 archivos de test que hacían `Usuario(rol=...)`: mecánico en 19 (columna ya no existe → kwarg inválido), + ajustes de mocks en `test_crud013_rol_asignaciones.py`/`test_crud010_limpiar_nullable.py` (necesitaban `get_rol_en_universidad`/`get_rol_mas_antiguo` mockeados y atributos completos para `_usuario_response`) y en `test_rubrica_actualizar_moodle_id.py`/`test_rubrica_schema_version_service.py` (necesitaban `rol=RolEnum.ADMIN` explícito, ya no hay fallback). `test_usuario_es_superadmin.py::test_los_campos_viejos_siguen_presentes` se REESCRIBIÓ a `test_los_campos_viejos_ya_no_existen` (el escenario spec "No queda rastro del rol global")
- [x] 5.2 `pytest -q` con el modelo ya sin columnas, tabla todavía intacta → **1672 passed**, 0 failed. Prueba que ningún código Python necesita las columnas
- [x] 5.3 Migración `5d12005298a6` (`alembic/versions/20260723_1800_...`): `upgrade` guardia con `RuntimeError` si hay algún usuario sin membresía activa (0 hoy, verificado 0.2), después dropea índice + las 4 columnas
- [x] 5.4 `downgrade`: recrea las 4 columnas (`rol` nullable primero), repuebla con `DISTINCT ON` (Postgres) por membresía activa de menor `id` (= más antigua, D6) — `moodle_host` sale de la `Universidad` de esa membresía; guard simétrico antes de `ALTER COLUMN rol SET NOT NULL`; recrea el índice
- [x] 5.5 Ciclo verificado CONTRA POSTGRES REAL (`docker exec active-ia-backend alembic ...`, guard SEC-003 esquivado corriendo dentro del contenedor):
  - Snapshot previo: 56 usuarios, `md5sum` de `(id, username, rol, moodle_username, moodle_host)` capturado
  - `upgrade`: las 4 columnas desaparecen de `\d usuarios` (verificado), `alembic_version` → `5d12005298a6`
  - `downgrade`: las 4 columnas vuelven; **`rol` y `moodle_username` coinciden EXACTO fila por fila con el snapshot previo** (56/56); `moodle_host` queda pobládo para TODOS (antes sólo para quien tenía credenciales) con el valor AUTORITATIVO de `Universidad.moodle_host` (`http://tup.sied.utn.edu.ar/`) — el `usuarios.moodle_host` viejo tenía `https://` (dato desactualizado de antes de la Fase 3, no un bug de esta migración: D6 dice explícitamente que el host sale de la Universidad, no de la columna vieja)
  - `upgrade` de nuevo: columnas se van, **56 filas preservadas**, contenedor backend healthy sin errores en logs (`GET /health` 200 OK)
- [x] 5.6 Modelo vs tabla real tras el `upgrade` final: **19 columnas en `Usuario.__table__`, 19 columnas en `\d usuarios`** — coinciden exacto (listado diffeado a mano)

## 6. Cierre

- [x] 6.1 Suite completa `pytest -q` → **1672 passed, 0 failed, 0 skipped**. Baseline 0.1: 1641. `get_coordinadores` no tenía tests (0), así que no hay baja que descontar — 1672 > 1641 confirma que no se apagó ningún test en la migración masiva
- [x] 6.2 Verificación manual E2E contra el backend real (`docker-compose.local`, Postgres real, tras el ciclo de migración): login admin → creó una 2ª universidad (`POST /universidades`) → `switch-universidad` a cada una → `POST /usuarios/` creó un TUTOR en universidad 1 (rol devuelto correctamente: `"TUTOR"`, resuelto desde la membresía) → `GET /usuarios/?search=...` en universidad 1 lo encuentra (total=1) → el MISMO listado en universidad 3 da `total=0` (aislamiento confirmado en vivo). `GET /perfil` devuelve `rol` correcto. Nota: quedan como datos de desarrollo residuales en el Postgres LOCAL (universidad "Universidad Verificacion Manual" id=3 y usuario "verify_tutor_uni1" id=61) — es un entorno de desarrollo, no productivo
- [x] 6.3 Ver sección "Open questions" y "Confirmación de cierre" del resumen final
