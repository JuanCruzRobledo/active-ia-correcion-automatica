# Implementation Plan

> Metodología exploratoria de bugfix: primero se hace SURFACE del bug con tests que FALLAN sobre el
> código sin arreglar (confirmando la causa raíz), luego se escriben tests de preservación que PASAN
> sobre el código sin arreglar, y recién después se implementa el fix. Cada tarea referencia las
> Correctness Properties (Property 1..7) y los requisitos del diseño/bugfix.
>
> Orden de exploración: una tarea de exploración por bug (Property 1..6 = Bug Condition) + una tarea
> de preservación (Property 7). **Bug 3 requiere una fase de DIAGNÓSTICO real (tarea 3) que confirme
> la hipótesis de grupos separados ANTES de codificar su fix.**

## Fase 1 — Exploración (tests que FALLAN antes del fix)

- [x] 1. Escribir test de exploración de la condición de bug — Tipo de actividad ASSIGN vs QUIZ (Bug 1)
  - **Property 1: Bug Condition** - Alta/edición y resolución de examen `quiz`
  - **CRITICAL**: Estos tests DEBEN FALLAR sobre el código sin arreglar — la falla confirma que el Bug 1 existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Estos tests codifican el comportamiento esperado — validarán el fix cuando pasen luego de implementarlo
  - **GOAL**: Surface counterexamples que demuestren que hoy no hay forma de representar un examen `quiz` ni resolver su link
  - **Scoped PBT Approach**: Al ser un bug determinista, acotar la propiedad a los casos concretos que fallan (quiz cmid 17679/20467, assign cmid 17648) para asegurar reproducibilidad
  - Test de resolución de link en `backend/tests/unit/services/test_moodle_url_parser.py` (crear/extender), importando el helper esperado `construir_url_actividad` desde `app.services.moodle_url_parser`:
    - Esperado: `construir_url_actividad(host, 17679, "quiz") == "https://.../mod/quiz/view.php?id=17679"`; hoy el helper NO existe (ImportError / AttributeError) → confirma que no hay resolución por tipo
    - Esperado: `construir_url_actividad(host, 17648, "assign") == "https://.../mod/assign/view.php?id=17648"`
  - Test de schema/modelo en `backend/tests/unit/services/test_examen_service.py` (o `test_examen_schema.py`):
    - Esperado: `ExamenMateriaCreate(... tipo_actividad="quiz")` es válido y `ExamenMateria` persiste `tipo_actividad`; hoy el campo NO existe (ValidationError / AttributeError)
    - Detalle de la Bug Condition: `input.examen.actividad_moodle_real == "quiz" AND NOT existeCampoTipoActividad(examen)` (ver `isBugCondition` de Bug 1 en design)
    - Las aserciones deben coincidir con las Expected Behavior Properties (Property 1 del design)
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_moodle_url_parser.py tests/unit/services/test_examen_service.py -k "quiz or tipo_actividad or actividad"`
  - **EXPECTED OUTCOME**: Los tests FALLAN (correcto — prueba que el Bug 1 existe)
  - Documentar los contraejemplos hallados (no existe `construir_url_actividad`; `ExamenMateria`/schemas no aceptan `tipo_actividad`; el link sale `/mod/assign/...`)
  - Marcar la tarea como completa cuando los tests estén escritos, ejecutados y la falla documentada
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Escribir test de exploración de la condición de bug — Excel de dos hojas (Bug 2)
  - **Property 2: Bug Condition** - Excel con dos hojas
  - **CRITICAL**: Este test DEBE FALLAR sobre el código sin arreglar — la falla confirma que el Bug 2 existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: El test codifica el comportamiento esperado — validará el fix cuando pase luego de implementarlo
  - **GOAL**: Surface counterexample de que hoy el Excel tiene UNA sola hoja y no existe la hoja "Crudo" con columnas Comision/Tutor
  - Test en `backend/tests/unit/services/test_excel_cierre_cursada.py` (extender el archivo existente), invocando `generar_excel_cierre(run)` con una corrida mockeada de una materia (p. ej. "Programación 3"):
    - Esperado: `len(wb.worksheets) == 2` con títulos `"Programación 3 por Comisiones"` y `"Programación 3 Crudo"`; hoy `len(wb.worksheets) == 1` (falla)
    - Esperado: la hoja "Crudo" tiene encabezados que incluyen `"Comision"` y `"Tutor"`; hoy no existe (falla)
    - Detalle de la Bug Condition: `cantidadDeHojas(wb) != 2 OR NOT existeHoja("... Crudo") OR NOT hojaCrudoTieneColumnas(["Comision","Tutor"])` (ver `isBugCondition` de Bug 2 en design)
    - Las aserciones deben coincidir con la Expected Behavior Property (Property 2 del design)
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_excel_cierre_cursada.py -k "dos_hojas or crudo or worksheets"`
  - **EXPECTED OUTCOME**: El test FALLA (correcto — prueba que el Bug 2 existe)
  - Documentar el contraejemplo (`generar_excel_cierre` devuelve 1 hoja; no hay hoja "Crudo")
  - Marcar la tarea como completa cuando el test esté escrito, ejecutado y la falla documentada
  - _Requirements: 1.4, 1.5_

- [x] 3. DIAGNÓSTICO + test de exploración — Exploración de grupos de Moodle (Bug 3) — PRIMER PASO DEL FIX DE BUG 3
  - **Property 3: Bug Condition** - Comisiones resueltas por mapa autoritativo
  - **CRITICAL — CONFIRMAR CAUSA RAÍZ ANTES DE CODIFICAR**: Este bug NO se codifica hasta confirmar (o refutar) la hipótesis de "grupos separados". Es el primer paso obligatorio del fix de Bug 3.
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: El test codifica el comportamiento esperado — validará el fix cuando pase luego de implementarlo
  - **GOAL**: Confirmar que `core_enrol_get_enrolled_users` devuelve `groups[]` incompleto (grupos separados) mientras `core_group_get_course_groups` sí lista las comisiones faltantes, y surface el counterexample "alumno con grupo válido → Sin comisión"
  - **Diagnóstico real (observación primero)**:
    - Inspeccionar, en un curso afectado (Prog 3 con `M25 C3-01/02/15`; Prog 1 con alumnos "sin comisión"), la respuesta cruda de `core_enrol_get_enrolled_users` vs `core_group_get_course_groups` + `core_group_get_group_members`
    - Confirmar: el `groups[]` embebido omite grupos de comisión que SÍ aparecen en `core_group_get_course_groups` (hipótesis de `groupmode=1` sin `moodle/site:accessallgroups`)
    - Si el `groups[]` viene completo → REFUTAR la hipótesis y re-hipotetizar con la variante de formato de nombre (espacios múltiples, NBSP, guion distinto que rompe `_COMISION_RE`); documentar el hallazgo en el design antes de continuar
  - Test en `backend/tests/unit/services/test_cierre_cursada_service.py` (y/o `test_moodle_service.py`): con `core_enrol_get_enrolled_users` mockeado que OMITE el grupo de comisión (simulando separate groups) mientras `core_group_get_course_groups` sí lo lista:
    - Esperado: `_resolver_comision` (usando el mapa autoritativo) asocia al alumno a su comisión real; hoy (dependiendo del `groups[]` embebido) devuelve `(None, "Sin comisión asignada", None)` (falla)
    - Detalle de la Bug Condition: `existeGrupoComision(grupos_reales) AND NOT existeGrupoComision(grupos_devueltos)` (ver `isBugCondition` de Bug 3 en design)
    - Las aserciones deben coincidir con la Expected Behavior Property (Property 3 del design)
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_moodle_service.py -k "grupo or comision or separados"`
  - **EXPECTED OUTCOME**: El test FALLA (correcto — prueba que el Bug 3 existe) y el diagnóstico confirma/refuta la causa raíz
  - Documentar el contraejemplo y la conclusión del diagnóstico (hipótesis confirmada o re-hipótesis) — bloquea el fix de la tarea 11 hasta cerrarse
  - Marcar la tarea como completa cuando el diagnóstico esté documentado, el test escrito/ejecutado y la falla documentada
  - _Requirements: 1.6, 1.7_

- [x] 4. Escribir test de exploración de la condición de bug — Conteos y Recuperable estáticos (Bug 4)
  - **Property 4: Bug Condition** - Conteos y Recuperable con fórmulas nativas
  - **CRITICAL**: Estos tests DEBEN FALLAR sobre el código sin arreglar — la falla confirma que el Bug 4 existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Estos tests codifican el comportamiento esperado — validarán el fix cuando pasen luego de implementarlo
  - **GOAL**: Surface counterexamples de que los conteos del resumen son enteros fijos (no fórmulas) y de que no existe columna/fórmula Recuperable
  - Test en `backend/tests/unit/services/test_excel_cierre_cursada.py`, leyendo las celdas generadas por `generar_excel_cierre`:
    - Esperado: la celda del conteo "PROMOCIONADOS" es una fórmula que empieza con `=CONTAR.SI(F:F;"PROMOCIONA")`; hoy es un `int` estático (falla)
    - Esperado: existe una columna "Recuperable" cuya celda por fila es una fórmula `=SI(F{n}<>"RECURSA";"";SI(Y(...` con las referencias de la hoja "por Comisiones" (estado F, parciales C/D, aux H); hoy no existe (falla)
    - Esperado: existe el conteo de recuperables `=CONTAR.SI(H:H;"RECUPERABLE*")` y el de abandonos `=CONTAR.SI(F:F;"ABANDONO")`; hoy no existen (falla)
    - Detalle de la Bug Condition: `esValorEstatico(celda_resumen) OR NOT existeColumnaRecuperable OR NOT esFormulaNativa(celda_recuperable)` (ver `isBugCondition` de Bug 4 en design)
    - Las aserciones deben coincidir con la Expected Behavior Property (Property 4 del design) y con las fórmulas es-AR de bugfix.md
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_excel_cierre_cursada.py -k "formula or recuperable or conteo or resumen"`
  - **EXPECTED OUTCOME**: Los tests FALLAN (correcto — prueba que el Bug 4 existe)
  - Documentar los contraejemplos (celdas de resumen son enteros; no hay columna ni conteo de recuperables)
  - Marcar la tarea como completa cuando los tests estén escritos, ejecutados y la falla documentada
  - _Requirements: 1.8, 1.9, 1.10_

- [x] 5. Escribir test de exploración de la condición de bug — Estado ABANDONO (Bug 5)
  - **Property 5: Bug Condition** - Estado ABANDONO
  - **CRITICAL**: Este test DEBE FALLAR sobre el código sin arreglar — la falla confirma que el Bug 5 existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: El test codifica el comportamiento esperado — validará el fix cuando pase luego de implementarlo
  - **GOAL**: Surface counterexample de que un alumno con todos los exámenes en `N/E` se clasifica hoy como RECURSA en vez de ABANDONO
  - **Scoped PBT Approach**: Al ser determinista, acotar la propiedad al caso concreto "todos los principales ausentes"; complementar con property-based en la tarea 7/9
  - Test en `backend/tests/unit/services/test_cierre_cursada_calculo.py`, invocando `calcular_estado_cierre`:
    - Alumno con Parcial 1, Parcial 2 y Global todos `N/E` (modo NUMERICO `valor_real=None` / modo ESCALA sin resultado) → esperado `estado == "ABANDONO"`; hoy devuelve `"RECURSA"` (falla)
    - Detalle de la Bug Condition: `todos_ne AND clasificacionActual(examenes) == "RECURSA"` (ver `isBugCondition` de Bug 5 en design)
    - Las aserciones deben coincidir con la Expected Behavior Property (Property 5 del design)
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_cierre_cursada_calculo.py -k "abandono"`
  - **EXPECTED OUTCOME**: El test FALLA (correcto — prueba que el Bug 5 existe)
  - Documentar el contraejemplo (`calcular_estado_cierre` con todo `N/E` devuelve "RECURSA")
  - Marcar la tarea como completa cuando el test esté escrito, ejecutado y la falla documentada
  - _Requirements: 1.11, 1.12_

- [x] 6. Escribir test de exploración de la condición de bug — Nota Final = 5 para REGULARIZA (Bug 6)
  - **Property 6: Bug Condition** - Nota Final = 5 para REGULARIZA
  - **CRITICAL**: Este test DEBE FALLAR sobre el código sin arreglar — la falla confirma que el Bug 6 existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: El test codifica el comportamiento esperado — validará el fix cuando pase luego de implementarlo
  - **GOAL**: Surface counterexample de que un alumno REGULARIZA queda con `nota_final = None` en vez de `5`
  - Test en `backend/tests/unit/services/test_cierre_cursada_calculo.py`, invocando `calcular_estado_cierre`:
    - Alumno REGULARIZA (cumple banda pero no promoción) → esperado `nota_final == 5`; hoy devuelve `None` (falla)
    - Detalle de la Bug Condition: `estado == "REGULARIZA" AND nota_final != 5` (ver `isBugCondition` de Bug 6 en design)
    - Las aserciones deben coincidir con la Expected Behavior Property (Property 6 del design)
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_cierre_cursada_calculo.py -k "regulariza"`
  - **EXPECTED OUTCOME**: El test FALLA (correcto — prueba que el Bug 6 existe)
  - Documentar el contraejemplo (`calcular_estado_cierre` para REGULARIZA devuelve `nota_final=None`)
  - Marcar la tarea como completa cuando el test esté escrito, ejecutado y la falla documentada
  - _Requirements: 1.13_

## Fase 2 — Preservación (tests que PASAN antes del fix)

- [x] 7. Escribir tests de preservación (property-based) — ANTES de todos los fixes
  - **Property 7: Preservation** - Exámenes assign, clasificación existente, orden, estilos, N/E, histórico
  - **IMPORTANT**: Seguir la metodología observation-first — correr el código SIN arreglar con inputs que NO disparan ninguna condición de bug y capturar el comportamiento observado
  - Property-based testing recomendado para la preservación de la clasificación y de la resolución de comisión (genera muchos casos del dominio y detecta edge cases)
  - Bug 1 (assign) — en `test_moodle_url_parser.py` / `test_cierre_cursada_service.py`:
    - Examen `assign` → link `/mod/assign/view.php?id=...` (via `construir_url_entrega` intacto) y uso del grade estructural (`mod_assign_get_grades`) igual que hoy (3.1)
    - Cadena de rescate (recu/ext/extraordinaria) mantiene su precedencia actual (3.2)
  - Bugs 5/6 (clasificación) — property-based en `test_cierre_cursada_calculo_pbt.py`:
    - Generar listas de exámenes aleatorias → sólo cambian los casos ABANDONO (todo-`N/E`) y la Nota Final de REGULARIZA; el resto de estados y la Nota Final ponderada de PROMOCIONA coinciden con el original (3.3, 3.4-scope, 3.5-scope)
    - PROMOCIONA conserva su Nota Final ponderada numérica (parciales 0–10 al 40 %, global al 60 %, `round_half_up`) (3.3)
    - Alumno que rindió al menos un examen (no todo-`N/E`) sigue RECURSA/REGULARIZA como hoy (3.5)
  - Bug 3 (comisión) — property-based en `test_cierre_cursada_service.py`:
    - Generar mapas de grupos aleatorios → alumno realmente sin grupo de comisión válido o mapeo ambiguo → "Sin comisión asignada" sin romper la corrida (3.7)
    - Orden numérico natural de comisiones y orden alfabético `(apellido, nombre)` dentro de bloque, con "Sin comisión asignada" al final (3.6)
  - Bugs 2/4 (Excel) — en `test_excel_cierre_cursada.py`:
    - Columnas de examen (`Parcial n`, `Global TPI`) siguen mostrando `N/E` cuando no hay nota (3.8)
    - Ambas hojas usan los estilos de la casa de `excel_estilos.py` (banda de título, headers, filas) (3.10)
  - Otras preservaciones observadas: histórico append-only y congelado de `examenes_snapshot` (3.9); bloqueo 400 sin exámenes PARCIAL/GLOBAL (3.11); modo ESCALA evaluado por Aprobado/Desaprobado (3.12)
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_cierre_cursada_calculo_pbt.py tests/unit/services/test_cierre_cursada_calculo.py tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_excel_cierre_cursada.py tests/unit/services/test_moodle_url_parser.py`
  - **EXPECTED OUTCOME**: Los tests PASAN (confirma el comportamiento base a preservar)
  - Marcar la tarea como completa cuando los tests estén escritos, ejecutados y pasando sobre el código sin arreglar
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12_

## Fase 3 — Implementación de los fixes

- [x] 8. Fix — Tipo de actividad ASSIGN vs QUIZ (Bug 1)

  - [x] 8.1 Agregar el enum, la columna del modelo y la migración
    - En `backend/app/models/enums.py`, agregar `class TipoActividadMoodleEnum(str, Enum)` con `ASSIGN = "assign"` y `QUIZ = "quiz"` (minúscula para comparar directo con `modname` de Moodle)
    - En `backend/app/models/examen_materia.py`, agregar `tipo_actividad: Mapped[TipoActividadMoodleEnum]` con `SQLEnum(TipoActividadMoodleEnum, name="tipoactividadmoodleenum", create_type=True)`, `nullable=False`, `server_default="assign"`
    - Crear una revisión Alembic (a mano, estilo `20260610_1600_..._examenes_materia.py`, `down_revision='e4f5a6b7c8d9'`): `CREATE TYPE tipoactividadmoodleenum AS ENUM ('assign','quiz')` (con `checkfirst`), `ADD COLUMN tipo_actividad ... NOT NULL DEFAULT 'assign'` en `examenes_materia`; `downgrade` = `DROP COLUMN` + `DROP TYPE`
    - Verificar que los registros existentes queden en `assign` (cumple 2.2)
    - _Bug_Condition: isBugCondition(input) de Bug 1 — falta campo tipo_actividad_
    - _Expected_Behavior: Property 1 — persistir `assign`/`quiz`, default `assign` para registros previos_
    - _Preservation: default `assign` = comportamiento actual (3.1)_
    - _Requirements: 2.1, 2.2_

  - [x] 8.2 Exponer `tipo_actividad` en schemas y service
    - En `backend/app/schemas/examen.py`: agregar `tipo_actividad: TipoActividadMoodleEnum` con default `ASSIGN` en `ExamenMateriaCreate` y `ExamenMateriaUpdate` (clientes viejos → `assign`); agregar `tipo_actividad` en `ExamenMateriaResponse`
    - En `backend/app/services/examen_service.py`: `crear`/`actualizar` setean `examen.tipo_actividad = data.tipo_actividad`; `_a_response` incluye `tipo_actividad=examen.tipo_actividad`
    - Validar permisos en el endpoint (regla del proyecto) — sin cambios de autorización, sólo el campo nuevo
    - _Bug_Condition: isBugCondition(input) de Bug 1 (alta/edición)_
    - _Expected_Behavior: Property 1 — alta/edición marca `assign`/`quiz` sin error (caso Extraordinaria 2/3 quiz sobre Parcial 2)_
    - _Preservation: default `assign` para payloads sin el campo (3.1)_
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 8.3 Resolver el link de Moodle por tipo de actividad
    - En `backend/app/services/moodle_url_parser.py`, agregar el helper puro `construir_url_actividad(host, cmid, tipo_actividad) -> str | None`: `/mod/quiz/view.php?id={cmid}` si `quiz`, `/mod/assign/view.php?id={cmid}` si `assign`
    - Dejar `construir_url_entrega` INTACTO (lo usan las entregas de alumno, siempre assign) → preserva 3.1
    - _Bug_Condition: isBugCondition(input) de Bug 1 (resolver_link)_
    - _Expected_Behavior: Property 1 — link `/mod/quiz/view.php` para quiz, `/mod/assign/view.php` para assign_
    - _Preservation: `construir_url_entrega` sin cambios (3.1)_
    - _Requirements: 2.3_

  - [x] 8.4 Seleccionar la fuente de notas por tipo de actividad
    - En `backend/app/services/cierre_cursada_service.py`, incluir `tipo_actividad` en el dict `examenes_config`
    - En el armado de `grades_por_cmid`, condicionar la llamada a `get_grades_full` a `ex["tipo_actividad"] == "assign"` (además del `modname`), para NO intentar el grade estructural en un `quiz` (el camino por texto del calificador para `quiz` ya existe en `examen_mapper`)
    - _Bug_Condition: isBugCondition(input) de Bug 1 (resolver_notas)_
    - _Expected_Behavior: Property 1 — quiz usa nota del calificador (texto), assign usa grade estructural_
    - _Preservation: assign sigue usando `mod_assign_get_grades` (3.1); cadena de rescate intacta (3.2)_
    - _Requirements: 2.4_

  - [x] 8.5 Frontend — Select "Actividad de Moodle" en el ABM de exámenes
    - En `frontend/src/features/materia-dashboard/types/index.ts`: agregar `type TipoActividadMoodle = 'assign' | 'quiz'` y el campo `tipo_actividad` en `ExamenMateria` y `ExamenInput`
    - En `frontend/src/features/materia-dashboard/components/ExamenesEditor.tsx`: agregar un `Select` "Actividad de Moodle" (Tarea/Cuestionario), cargarlo en `cargarParaEditar`, incluirlo en el payload de `guardar` y mostrarlo como columna en la tabla; default `assign`
    - Usar TypeScript strict (regla del proyecto)
    - _Bug_Condition: isBugCondition(input) de Bug 1 (alta/edición desde UI)_
    - _Expected_Behavior: Property 1 — el usuario puede marcar `assign`/`quiz` al dar de alta/editar_
    - _Preservation: default `assign` en alta/edición (3.1)_
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 8.6 Verificar que el test de exploración de Bug 1 ahora pasa
    - **Property 1: Expected Behavior** - Alta/edición y resolución de examen `quiz`
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 1 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_moodle_url_parser.py tests/unit/services/test_examen_service.py`
    - **EXPECTED OUTCOME**: Los tests PASAN (confirma que el Bug 1 está arreglado)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 8.7 Verificar que los tests de preservación siguen pasando (Bug 1)
    - **Property 7: Preservation** - Exámenes assign (link, grade estructural, cadena de rescate)
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 7 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_moodle_url_parser.py tests/unit/services/test_cierre_cursada_service.py`
    - **EXPECTED OUTCOME**: Los tests PASAN (confirma que no hay regresiones en assign — 3.1, 3.2)
    - _Requirements: 3.1, 3.2_

- [x] 9. Fix — Estado ABANDONO (Bug 5) y Nota Final = 5 para REGULARIZA (Bug 6)

  - [x] 9.1 Agregar el valor de enum ABANDONO, `total_abandono` y la migración
    - En `backend/app/models/enums.py`: agregar `ABANDONO = "ABANDONO"` a `EstadoCierreEnum`
    - En `backend/app/models/cierre_cursada_run.py` (o el modelo `CierreCursadaRun`): agregar `total_abandono: Mapped[int]` con `default=0`, `server_default="0"`
    - Migración Alembic: `ALTER TYPE estadocierreenum ADD VALUE IF NOT EXISTS 'ABANDONO'` (ejecutar con `op.execute` fuera del bloque transaccional / autocommit, porque `ADD VALUE` no corre dentro de una transacción en algunas versiones de PG — documentarlo) + `ADD COLUMN total_abandono INTEGER NOT NULL DEFAULT 0`
    - _Bug_Condition: isBugCondition de Bug 5 — falta el estado ABANDONO_
    - _Expected_Behavior: Property 5 — ABANDONO disponible y contado aparte de RECURSA_
    - _Preservation: los estados existentes no cambian de valor_
    - _Requirements: 2.16, 2.17_

  - [x] 9.2 Implementar la rama ABANDONO en `calcular_estado_cierre` (Bug 5)
    - En `backend/app/services/cierre_cursada_calculo.py`, en `calcular_estado_cierre`, detectar `todos_ausentes`: para cada examen, "ausente" = modo ESCALA con `resultado_escala` que no es `aprobado` ni `desaprobado`, o modo NUMERICO con `valor_real is None`
    - Si TODOS los principales están ausentes → `estado = "ABANDONO"`; el chequeo va ANTES del `else` de RECURSA y NO aplica si el alumno cumple promoción/banda (preserva 3.5)
    - _Bug_Condition: isBugCondition de Bug 5 — todos los principales en N/E_
    - _Expected_Behavior: Property 5 — todo-`N/E` → ABANDONO (no RECURSA)_
    - _Preservation: alumno que rindió al menos un examen sigue RECURSA/REGULARIZA (3.5)_
    - _Requirements: 2.16_

  - [x] 9.3 Implementar Nota Final = 5 para REGULARIZA (Bug 6)
    - En `backend/app/services/cierre_cursada_calculo.py`, en `calcular_estado_cierre`, cambiar la asignación de `nota_final`: `PROMOCIONA` → `calcular_nota_final(examenes)` (sin cambios); `REGULARIZA` → `5`; `RECURSA`/`ABANDONO` → `None`
    - NO tocar `calcular_nota_final` (regla concentrada en un solo punto para revertir fácil: cambiar `5` por `None`)
    - `_fmt_nota_final` del Excel ya imprime el entero cuando no es `None`, así que REGULARIZA mostrará `5` sin cambios adicionales
    - _Bug_Condition: isBugCondition de Bug 6 — REGULARIZA con nota_final != 5_
    - _Expected_Behavior: Property 6 — REGULARIZA → Nota Final = 5 (persistida y en el Excel)_
    - _Preservation: PROMOCIONA conserva Nota Final ponderada (3.3); RECURSA/ABANDONO → None (3.4-scope)_
    - _Requirements: 2.18_

  - [x] 9.4 Extender conteos y persistencia de totales en el service (Bug 5)
    - En `backend/app/services/cierre_cursada_service.py`, `generar`: extender `conteos` con `"ABANDONO": 0`, asignar `total_abandono` al `CierreCursadaRun` y a la actividad registrada
    - No romper el histórico append-only ni el congelado de `examenes_snapshot` (3.9)
    - _Bug_Condition: isBugCondition de Bug 5 — conteo de ABANDONO_
    - _Expected_Behavior: Property 5 — ABANDONO contado aparte de RECURSA (`total_abandono`)_
    - _Preservation: histórico append-only y snapshot intactos (3.9)_
    - _Requirements: 2.17_

  - [x] 9.5 Verificar que los tests de exploración de Bug 5 y Bug 6 ahora pasan
    - **Property 5: Expected Behavior** - Estado ABANDONO
    - **Property 6: Expected Behavior** - Nota Final = 5 para REGULARIZA
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de las tareas 5 y 6 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_cierre_cursada_calculo.py -k "abandono or regulariza"`
    - **EXPECTED OUTCOME**: Los tests PASAN (confirma que los bugs 5 y 6 están arreglados)
    - _Requirements: 2.16, 2.17, 2.18_

  - [x] 9.6 Verificar que los tests de preservación siguen pasando (Bugs 5/6)
    - **Property 7: Preservation** - Clasificación PROMOCIONA/RECURSA y Nota Final ponderada
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 7 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_cierre_cursada_calculo_pbt.py tests/unit/services/test_cierre_cursada_calculo.py tests/unit/services/test_cierre_cursada_service.py`
    - **EXPECTED OUTCOME**: Los tests PASAN — sólo cambian ABANDONO (todo-`N/E`) y la Nota Final de REGULARIZA; PROMOCIONA ponderada y RECURSA (rindió algo) sin regresiones (3.3, 3.4, 3.5)
    - _Requirements: 3.3, 3.4, 3.5, 3.9_

- [x] 10. Fix — Excel de dos hojas (Bug 2) y fórmulas nativas (Bug 4)

  - [x] 10.1 Refactor de `generar_excel_cierre` a orquestador de dos hojas (Bug 2)
    - En `backend/app/services/excel_cierre_cursada.py`, `generar_excel_cierre` pasa a orquestar dos hojas; extraer helpers para respetar el máximo de 500 LOC por archivo
    - Hoja 1 "por Comisiones": mover la lógica actual (`_escribir_resumen` + `_escribir_detalle` + `_agrupar_por_comision`) a escribir sobre `ws1 = wb.active`, con título `sheet_title(f"{materia_nombre} por Comisiones")`
    - Reutilizar los helpers de `excel_estilos.py` (`banda_titulo`, `celda_header`, `fila_datos`) → preserva 3.10
    - _Bug_Condition: isBugCondition de Bug 2 — el Excel no tiene 2 hojas_
    - _Expected_Behavior: Property 2 — hoja 1 "por Comisiones" con cuadros por comisión_
    - _Preservation: orden de comisiones y alumnos, estilos de la casa (3.6, 3.10)_
    - _Requirements: 2.5, 2.6_

  - [x] 10.2 Escribir la hoja "Crudo" (Bug 2)
    - En `excel_cierre_cursada.py`, nueva `ws2 = wb.create_sheet(sheet_title(f"{materia_nombre} Crudo"))` y función `_escribir_hoja_cruda(ws2, run, parciales, global_examen)`
    - Encabezados: `Nombre y Apellido | Email | Comision | Tutor | Parcial n… | Global TPI | Estado Alumno | Nota Final | Recuperable`
    - Filas: TODOS los alumnos ordenados alfabéticamente por `(apellido, nombre)` — sin cuadros por comisión —, con `comision_nombre` ("Sin comisión asignada" si aplica) y `tutor_nombre`
    - Resumen arriba (banda + conteos) con las referencias de columna de la hoja "Crudo" (ver 10.4)
    - _Bug_Condition: isBugCondition de Bug 2 — falta la hoja "Crudo" con Comision/Tutor_
    - _Expected_Behavior: Property 2 — hoja 2 plana alfabética con columnas Comision y Tutor_
    - _Preservation: columnas de examen muestran `N/E` (3.8); estilos de la casa (3.10)_
    - _Requirements: 2.5, 2.7_

  - [x] 10.3 Columna/fórmula "Recuperable" por fila en ambas hojas (Bug 4)
    - En `excel_cierre_cursada.py`, escribir la fórmula Recuperable por fila (localización es-AR, `;` como separador; documentar la dependencia de locale):
      - Hoja "por Comisiones" (aux col H, estado F, parciales C/D): `=SI(F{n}<>"RECURSA";"";SI(Y(SI.ERROR(VALOR(C{n});0)>=40;SI.ERROR(VALOR(D{n});0)<40);"RECUPERABLE CON PARCIAL 2";SI(Y(SI.ERROR(VALOR(D{n});0)>=40;SI.ERROR(VALOR(C{n});0)<40);"RECUPERABLE CON PARCIAL 1";"")))`
      - Hoja "Crudo" (col J, estado H, parciales E/F): misma fórmula con las columnas E/F/H/J
    - Escribir como fórmula = string que empieza con `=` en `ws.cell(...).value` (openpyxl la persiste como fórmula nativa)
    - _Bug_Condition: isBugCondition de Bug 4 — no existe columna/fórmula Recuperable_
    - _Expected_Behavior: Property 4 — Recuperable sólo para RECURSA con un parcial `>=40` y el otro `<40`/N/E, con referencias por hoja_
    - _Preservation: no altera cálculos ni estilos (3.10)_
    - _Requirements: 2.13, 2.14_

  - [x] 10.4 Conteos del resumen como fórmulas nativas en ambas hojas (Bug 4)
    - En `excel_cierre_cursada.py`, reemplazar los `run.total_*` estáticos por fórmulas:
      - Hoja "por Comisiones": `=CONTAR.SI(F:F;"PROMOCIONA")`, `=CONTAR.SI(F:F;"REGULARIZA")`, `=CONTAR.SI(F:F;"RECURSA")`, Recuperables `=CONTAR.SI(H:H;"RECUPERABLE*")`, Abandonos `=CONTAR.SI(F:F;"ABANDONO")`
      - Hoja "Crudo": mismas fórmulas con Estado en `H:H`; Recuperables `=CONTAR.SI(J:J;"RECUPERABLE CON*")`
    - _Bug_Condition: isBugCondition de Bug 4 — conteos como enteros estáticos_
    - _Expected_Behavior: Property 4 — conteos como `CONTAR.SI`, recalculan al editar "Estado Alumno"_
    - _Preservation: estilos de la casa (3.10)_
    - _Requirements: 2.11, 2.12, 2.15_

  - [x] 10.5 Verificar que los tests de exploración de Bug 2 y Bug 4 ahora pasan
    - **Property 2: Expected Behavior** - Excel con dos hojas
    - **Property 4: Expected Behavior** - Conteos y Recuperable con fórmulas nativas
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de las tareas 2 y 4 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_excel_cierre_cursada.py`
    - **EXPECTED OUTCOME**: Los tests PASAN (2 hojas; fórmulas de conteo y recuperable con las referencias por hoja)
    - _Requirements: 2.5, 2.6, 2.7, 2.11, 2.12, 2.13, 2.14, 2.15_

  - [x] 10.6 Verificar que los tests de preservación siguen pasando (Bugs 2/4)
    - **Property 7: Preservation** - `N/E` en columnas de examen y estilos de la casa
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 7 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_excel_cierre_cursada.py`
    - **EXPECTED OUTCOME**: Los tests PASAN — `N/E` en `Parcial n`/`Global TPI` (3.8), estilos de la casa en ambas hojas (3.10), orden de comisiones/alumnos (3.6)
    - _Requirements: 3.6, 3.8, 3.10_

- [x] 11. Fix — Exploración/sincronización de grupos de Moodle (Bug 3)

  > **BLOQUEADO por la tarea 3**: no implementar hasta que el diagnóstico de la tarea 3 haya
  > confirmado (o re-hipotetizado) la causa raíz.

  - [x] 11.1 Agregar `get_course_groups` y `get_group_members` en MoodleService
    - En `backend/app/services/moodle_service.py`: `get_course_groups(token, host, course_id) -> list[dict]` (`core_group_get_course_groups`, cacheado por course_id) → `[{id, name}]` de TODOS los grupos
    - `get_group_members(token, host, group_id) -> list[int]` (`core_group_get_group_members`) → `[userid]` por grupo
    - No exponer información sensible en logs (regla del proyecto)
    - _Bug_Condition: isBugCondition de Bug 3 — `groups[]` embebido incompleto_
    - _Expected_Behavior: Property 3 — fuente autoritativa de grupos vía `core_group_*`_
    - _Preservation: no cambia el comportamiento de usuarios sin grupo válido (3.7)_
    - _Requirements: 2.8, 2.10_

  - [x] 11.2 Construir el mapa autoritativo `uid → grupos`
    - En `moodle_service.py`, helper `construir_mapa_uid_grupos(groups, members_por_group) -> dict[int, list[dict]]` (`{uid: [{id, name}]}`), independiente del `groups[]` embebido
    - _Bug_Condition: isBugCondition de Bug 3_
    - _Expected_Behavior: Property 3 — mapa `uid → grupos` autoritativo_
    - _Preservation: mapeo ausente/ambiguo no rompe la corrida (3.7)_
    - _Requirements: 2.8, 2.9, 2.10_

  - [x] 11.3 Usar el mapa autoritativo en `CierreCursadaService`
    - En `backend/app/services/cierre_cursada_service.py`, `generar`: construir el mapa `uid → grupos` una vez por corrida y pasar esos grupos (no `u.get("groups")`) a `_resolver_comision`
    - El bridge por `moodle_group_id` y el fallback por `parse_comision` no cambian → preserva 3.7
    - _Bug_Condition: isBugCondition de Bug 3 — alumno con grupo válido resuelto como "Sin comisión"_
    - _Expected_Behavior: Property 3 — alumno con grupo válido asociado a su comisión_
    - _Preservation: sin grupo válido / ambiguo → "Sin comisión asignada" (3.7); orden intacto (3.6)_
    - _Requirements: 2.9_

  - [x] 11.4 Usar el mapa autoritativo en GestionService
    - En `backend/app/services/gestion_service.py`, `opciones_filtros`/`consultar`/`exportar_pendientes_excel`: derivar regionales/comisiones y resolver la comisión de cada alumno con el mismo mapa autoritativo, en vez de `u.get("groups", [])`
    - _Bug_Condition: isBugCondition de Bug 3 — comisiones faltantes en el explorador (Prog 3: M25 C3-01/02/15)_
    - _Expected_Behavior: Property 3 — todas las comisiones con grupo válido aparecen_
    - _Preservation: alumnos realmente sin grupo → "Sin comisión asignada" (3.7)_
    - _Requirements: 2.8, 2.9_

  - [x] 11.5 Fallback ante WS deshabilitado
    - En `moodle_service`/`cierre_cursada_service`/`gestion_service`: si `core_group_get_group_members` no está habilitado en el WS del cliente, degradar al `groups[]` embebido (comportamiento actual) y loguear la degradación — nunca romper la corrida
    - _Bug_Condition: isBugCondition de Bug 3 (con WS de grupos deshabilitado)_
    - _Expected_Behavior: Property 3 — degradación segura sin interrumpir la corrida_
    - _Preservation: comportamiento actual como fallback (3.7)_
    - _Requirements: 2.10_

  - [x] 11.6 Verificar que el test de exploración de Bug 3 ahora pasa
    - **Property 3: Expected Behavior** - Comisiones resueltas por mapa autoritativo
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 3 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_moodle_service.py -k "grupo or comision or separados"`
    - **EXPECTED OUTCOME**: Los tests PASAN (alumno con grupo válido asociado; comisiones antes faltantes aparecen)
    - _Requirements: 2.8, 2.9, 2.10_

  - [x] 11.7 Verificar que los tests de preservación siguen pasando (Bug 3)
    - **Property 7: Preservation** - "Sin comisión asignada" y orden de comisiones/alumnos
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 7 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_excel_cierre_cursada.py`
    - **EXPECTED OUTCOME**: Los tests PASAN — alumno sin grupo válido / ambiguo → "Sin comisión asignada" sin romper la corrida (3.7); orden numérico de comisiones y alfabético de alumnos, "Sin comisión asignada" al final (3.6)
    - _Requirements: 3.6, 3.7_

## Fase 4 — Checkpoint final

- [x] 12. Checkpoint - Asegurar que todos los tests pasan (6 bugs)
  - Ejecutar toda la suite del backend: `cd backend && pytest`
  - Ejecutar los tests del frontend: `cd frontend && npm run test && npm run lint`
  - Confirmar unit (`test_cierre_cursada_calculo.py`, `test_cierre_cursada_service.py`, `test_excel_cierre_cursada.py`, `test_moodle_url_parser.py`, `test_moodle_service.py`, `test_examen_service.py`), property-based (`test_cierre_cursada_calculo_pbt.py` — Property 5 ABANDONO, Property 6 REGULARIZA=5, resolución de comisión, fórmula Recuperable) e integración (`test_cierre_cursada.py`: cierre end-to-end con Moodle mockeado — ABANDONO + `total_abandono`, Nota Final 5, Excel de 2 hojas con fórmulas, grupos separados M25 C3-01/02/15, ABM de examen quiz)
  - QA checklist del proyecto: sin `print`/`console.log` de debug, permisos validados en endpoints, schemas Pydantic actualizados, migraciones generadas (Bugs 1 y 5), sin secrets, máximo 500 LOC por archivo, sin archivos temporales
  - Confirmar que las migraciones aplican correctamente: `alembic upgrade head` (revisiones de Bug 1 y Bug 5)
  - Asegurar que todos los tests pasan; consultar al usuario si surgen dudas (en particular la discrepancia Bug 6 vs modelo: Nota Final = 5 vs blanco)
