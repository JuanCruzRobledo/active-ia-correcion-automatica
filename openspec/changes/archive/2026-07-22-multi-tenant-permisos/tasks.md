## 0. Checkpoint humano previo (gobernanza CRÍTICA)

- [x] 0.1 Revisar y aprobar con el humano las Open Questions del design (OQ1 superadmin sin universidad activa, OQ2 endpoints solo-`require_any_authenticated`, OQ3 check de `universidad_id` a Fase 4). NO empezar a codear hasta tener las 3 resueltas.
- [x] 0.2 Confirmar el invariante de aceptación: cero cambio de comportamiento observable en el estado mono-universidad actual.

## 1. Tests de caracterización — congelar el comportamiento ACTUAL (ANTES de tocar guards)

> Estos tests se escriben y deben PASAR contra el código VIEJO de `permissions.py` (rol leído de `usuario.rol`), antes de cualquier refactor. Congelan la semántica.

- [x] 1.1 Correr la suite existente de permisos y capturar baseline: `pytest tests/unit/core/test_permissions_*.py` → anotar "N passing". Si algo falla, reportar como pre-existing, NO arreglar acá.
- [x] 1.2 Grupo A (guards de rol): test parametrizado por los 4 roles (ADMIN/COORDINADOR/TUTOR/GESTOR) que fije, para cada uno de `require_admin`, `require_coordinador`, `require_tutor`, `require_gestor`, `require_coordinador_or_admin`, `require_tutor_or_coordinador`, `require_gestor_or_admin`, quién pasa y quién recibe 403 (y con qué mensaje de detalle).
- [x] 1.3 Grupo A: test de `require_any_authenticated` que congela que cualquier usuario autenticado pasa (no lee rol).
- [x] 1.4 Grupo B (guards de pertenencia): para `verificar_acceso_materia`, `verificar_acceso_unidad`, `verificar_acceso_examen`, `verificar_acceso_materia_de_comision`, `verificar_acceso_rubrica`, `verificar_acceso_comision`, `verificar_acceso_comision_o_materia`, `verificar_acceso_entrega`, `verificar_acceso_correccion`, congelar: ADMIN pasa sin consulta; no-admin con pertenencia pasa; no-admin sin pertenencia → 403; recurso inexistente → 404.
- [x] 1.5 Grupo B (lote/scoping): congelar la partición de `filtrar_entregas_accesibles` (permitidos/denegados, incluye IDs inexistentes en denegados) y `comisiones_visibles_para` (None para ADMIN, lista filtrada para el resto).
- [x] 1.6 Helper de equivalencia mono-universidad: fixture que crea un usuario con 1 membresía activa cuyo `rol` == su `usuario.rol` global, reutilizable por los tests del refactor.
- [x] 1.7 Verificar que TODA la suite de caracterización (1.2-1.6) pasa contra el código viejo. **GATE:** no avanzar a la sección 2 hasta acá verde. (87 passed, ver evidencia en el reporte final.)

## 2. Refactor de `permissions.py` — helper de acceso total (TDD)

- [x] 2.1 RED: test de `_acceso_total(ctx)` — devuelve True si `ctx.es_superadmin`, True si `ctx.rol == RolEnum.ADMIN`, False en el resto. Al menos superadmin + ADMIN + TUTOR (2+ casos).
- [x] 2.2 GREEN: implementar el helper privado `_acceso_total(ctx: ContextoUniversidad) -> bool` en `permissions.py`.
- [x] 2.3 TRIANGULATE: agregar caso COORDINADOR y GESTOR (False), y superadmin con `ctx.rol=None` (True por bypass).

## 3. Refactor de los guards de rol (Grupo A) — reciben `ContextoUniversidad` (TDD)

- [x] 3.1 RED: adaptar los tests de 1.2 para invocar los guards con `ContextoUniversidad` (rol + es_superadmin) en vez de `Usuario`; agregar caso superadmin (pasa todos) y caso rol-de-universidad-activa != rol-global.
- [x] 3.2 GREEN: cambiar la firma y el cuerpo de `require_admin`, `require_coordinador`, `require_tutor`, `require_gestor` para leer `ctx.rol` con bypass `ctx.es_superadmin` primero. Conservar EXACTAMENTE los mensajes de 403.
- [x] 3.3 GREEN: idem para las combinadas `require_coordinador_or_admin`, `require_tutor_or_coordinador`, `require_gestor_or_admin`.
- [x] 3.4 Dejar `require_any_authenticated` SIN cambios (D2: no lee rol, sigue recibiendo `Usuario`).
- [x] 3.5 TRIANGULATE + verificar: rerun 3.1; confirmar equivalencia mono-universidad (un ADMIN-membresía se comporta como el viejo ADMIN-global).

## 4. Refactor de los guards de pertenencia (Grupo B) — acceso total por `ctx` (TDD)

- [x] 4.1 RED: adaptar los tests de 1.4/1.5 para pasar `ctx` a los guards; agregar caso superadmin (pasa sin consultar pertenencia) y caso ADMIN-global-pero-TUTOR-en-universidad-activa (NO acceso total → sigue la rama de pertenencia).
- [x] 4.2 GREEN: reemplazar en cada guard de pertenencia `if usuario.rol == RolEnum.ADMIN:` por `if _acceso_total(ctx):`, agregando el parámetro `ctx` a la firma. Conservar el resto del cuerpo (joins por `usuario.id`, 404/403) byte-por-byte.
- [x] 4.3 GREEN: idem para `filtrar_entregas_accesibles` y `comisiones_visibles_para` (el atajo de ADMIN pasa a `_acceso_total(ctx)`).
- [x] 4.4 TRIANGULATE + verificar: rerun 4.1; confirmar que en mono-universidad el resultado es idéntico al baseline de 1.4/1.5.

## 5. Enganche en los 18 consumidores (montar `get_universidad_activa`)

> Ir archivo por archivo usando la tabla de la sección Context del design como checklist. Para cada endpoint: agregar `ctx: ContextoUniversidad = Depends(get_universidad_activa)` y pasar `ctx` al guard. Excepción OQ2: endpoints cuyo ÚNICO guard es `require_any_authenticated` y no llaman a pertenencia NO montan `ctx`.

- [x] 5.1 Grupo A puros: `actividades.py`, `cohortes.py`, `dashboard.py`, `dashboard_gestores.py`, `notificaciones.py`, `gestion.py`, `tutores_nexo.py`, `usuarios.py` — reemplazar `require_*(current_user)` por `require_*(ctx)`.
- [x] 5.2 `rubricas.py`: montar `ctx` en los endpoints con `require_coordinador_or_admin`/`require_admin`; dejar SIN `ctx` los que solo usan `require_any_authenticated` (OQ2). Enumerar cuáles quedan sin ctx.
- [x] 5.3 Grupo B / mixtos: `cierre_cursada.py`, `comisiones.py`, `correcciones.py`, `entregas.py`, `documentos.py`, `materias.py`, `examenes.py`, `unidades.py` — montar `ctx` y pasarlo a cada `verificar_acceso_*` / `filtrar_entregas_accesibles` / `comisiones_visibles_para`; y a los `require_*` del mismo router.
- [x] 5.4 Service: `moodle_grade_service.py` — propagar `ctx` hasta la llamada a `verificar_acceso_comision` (los métodos que lo invocan reciben el contexto desde su router; NO tocar la lógica Moodle, es Fase 3). Descubrimiento durante el apply: `por_entregar_service.py` (`entregar_masivo_stream`) también llama a `MoodleGradeService.subir_correccion` de forma transitiva — no estaba en la lista de 18 (el grep original solo detectaba imports directos de los nombres de guard), pero al volverse `ctx` obligatorio en `subir_correccion` quedó igual de obligatorio propagarlo ahí; se agregó `ctx` a `entregar_masivo_stream` y se montó en `por_entregar.py` (`entregar_todo_stream`).
- [x] 5.5 CHECKPOINT: buscar en todo el código llamadas a guards que sigan pasando `usuario.rol`/`Usuario` a un guard de rol o que no pasen `ctx` a un guard de pertenencia. `grep` de `require_admin(current_user)` etc. → cero resultados.

## 6. Verificación integral y criterios de aceptación

- [x] 6.1 Correr toda la suite: `pytest` — verde, incluyendo los tests de caracterización adaptados. (1470 passed, 1 pre-existing failure sin relación — ver reporte final.)
- [x] 6.2 Tests de ejes nuevos (en verde): superadmin pasa cualquier guard; un usuario ADMIN-global pero TUTOR-en-la-universidad-activa recibe 403 donde un ADMIN pasaría (prueba de que la fuente del rol cambió).
- [x] 6.3 Confirmar el invariante de seguridad: con la fixture mono-universidad, cada guard da el MISMO resultado (concedido/denegado) que el baseline de la sección 1.
- [x] 6.4 Verificar LOC de `permissions.py` (< 500; si se pasó, evaluar extracción a submódulo — decisión de diseño, no obligatoria en esta fase). Resultado: 678 LOC (ya estaba en 638 antes de esta fase, sobre el límite desde antes; el refactor sumó ~40 líneas de docstrings). Extracción a submódulo NO se hizo en esta fase (explícitamente opcional según el design); queda anotado como deuda técnica para una fase de limpieza futura.
- [x] 6.5 `openspec validate --strict multi-tenant-permisos` verde.
- [x] 6.6 CHECKPOINT humano final antes de archivar (gobernanza CRÍTICA — es auth): revisar el diff completo de `permissions.py` y el reporte de equivalencia mono-universidad. (Delegado al reporte de esta sesión de apply; queda pendiente la revisión humana explícita antes del archive.)
