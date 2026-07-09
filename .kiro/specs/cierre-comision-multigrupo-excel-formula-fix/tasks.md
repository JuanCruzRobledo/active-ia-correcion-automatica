# Implementation Plan

> Metodología exploratoria de bugfix (observación primero): primero se hace SURFACE de cada bug con
> tests que FALLAN sobre el código sin arreglar (para el Bug 1, además, un paso de DIAGNÓSTICO real
> que CONFIRMA la causa raíz con los datos reales de TAMARA — GATING antes de codificar), luego se
> escriben tests de preservación (property-based) que PASAN sobre el código sin arreglar, y recién
> después se implementan los fixes. Cada tarea referencia las Correctness Properties (Property 1..3)
> y los requisitos del diseño/bugfix.
>
> **Este spec cubre exactamente dos bugs coordinados:**
> - **Bug 1** — Alumnos multi-grupo caen en "Sin comisión asignada" (`gestion_parser.py` regex +
>   `cierre_cursada_service._resolver_comision`).
> - **Bug 2** — Fórmulas del Excel muestran `#NAME?` (`excel_cierre_cursada.py` +
>   `test_excel_cierre_cursada.py`).
>
> **Referencias:** Requisitos en `bugfix.md` (secciones 1.x, 2.x, 3.x) y `design.md` (Correctness
> Properties 1–3, Fix Implementation, Testing Strategy). Respetar Clean Architecture (Router →
> Service → Repository) y el máximo de 500 LOC por archivo.

---

## Fase 1 — Exploración (tests que FALLAN antes del fix)

- [ ] 1. DIAGNÓSTICO + test de exploración de la condición de bug — Comisión multi-grupo (Bug 1) — PRIMER PASO DEL FIX DE BUG 1
  - **Property 1: Bug Condition** - Alumno multi-grupo asignado a su comisión real
  - **CRITICAL — CONFIRMAR CAUSA RAÍZ ANTES DE CODIFICAR (GATING)**: el Bug 1 NO se codifica hasta confirmar (o refutar) la hipótesis (a) "segundo match espurio" habilitada por (c) "mapa autoritativo". Es el primer paso obligatorio del fix de Bug 1.
  - **CRITICAL**: Estos tests DEBEN FALLAR sobre el código sin arreglar — la falla confirma que el Bug 1 existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Estos tests codifican el comportamiento esperado — validarán el fix cuando pasen luego de implementarlo
  - **GOAL**: Surface counterexamples que demuestren que un alumno con un único grupo de formato de comisión + varios grupos que no son de comisión cae en "Sin comisión asignada", y CONFIRMAR por qué
  - **Scoped PBT Approach**: al ser un bug determinista, acotar la propiedad al caso concreto reportado (TAMARA con sus 6 grupos reales) para asegurar reproducibilidad; complementar con property-based en la tarea 4/verificación
  - **Diagnóstico real (observación primero) — GATING**:
    - Construir la lista real de 6 grupos de TAMARA ROCIO ALBARRACÍN — `["A25 C2-01", "Extraordinaria_sdo_parcial", "NO_RINDIERON_PARCIAL_1", "No-rindieron-P1", "R-Mendoza", "Ultima_INSTANCIA_Examen"]`, cada uno con su `id` de Moodle — y el conjunto de `Comision` reales de Programación 2, e invocar `CierreCursadaService._resolver_comision` en `backend/tests/unit/services/test_cierre_cursada_service.py`
    - Instrumentar / inspeccionar el contenido de `encontradas`:
      - Si `len(encontradas) >= 2` y una de las comisiones matcheó por `moodle_group_id` desde un grupo que NO es `"A25 C2-01"` → **CONFIRMA (a)** (segundo match espurio), habilitado por (c) el mapa autoritativo que ahora entrega la lista completa de grupos
      - Si `len(encontradas) == 0` → **CONFIRMA (b)** (el grupo real `"A25 C2-01"` falla ambos puentes): re-hipotetizar y documentar en el design; revisar `moodle_group_id`/nombre de la comisión en la BD antes de continuar
    - Confirmar ADEMÁS que `"A25 C2-01"` matchea el regex generalizado y que su `Comision` existe (por `moodle_group_id` o por nombre), para garantizar que aislar el grupo de comisión NO pierda el match legítimo (supuesto flagged en design → "Hypothesized Root Cause / Bug 1")
  - **Test de resolución de comisión** en `test_cierre_cursada_service.py`:
    - Esperado: `_resolver_comision(grupos_tamara, comisiones_prog2)` devuelve `(comision_id, "A25 C2-01", tutor)`; hoy devuelve `(None, "Sin comisión asignada", None)` → FALLA (confirma el Bug 1)
    - Detalle de la Bug Condition: `count([g for g in X.grupos if matchesComisionFormat(g.name)]) == 1 AND resolver_comision(X.grupos, X.comisiones) == "Sin comisión asignada"` (ver `isBugCondition1` en design/bugfix)
    - Las aserciones deben coincidir con la Expected Behavior Property (Property 1 del design)
  - **Test de regex generalizado (año exactamente 2 dígitos)** en `backend/tests/unit/services/test_gestion_parser.py` (crear/extender):
    - Esperado tras el fix: `parse_comision("A2025 C2-01") is None` (año de 4 dígitos rechazado); hoy devuelve `"A2025 C2-01"` (el `\d+` acepta 4 dígitos) → FALLA
    - Esperado (se mantiene): `parse_comision("A25 C2-01") == "A25 C2-01"`
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_gestion_parser.py -k "tamara or multigrupo or comision or regex or dos_digitos"`
  - **EXPECTED OUTCOME**: Los tests FALLAN (correcto — prueba que el Bug 1 existe) y el diagnóstico confirma/refuta la causa raíz
  - Documentar los contraejemplos y la conclusión del diagnóstico (hipótesis (a)/(c) confirmada o re-hipótesis (b)) — bloquea el fix de la tarea 3 hasta cerrarse
  - Marcar la tarea como completa cuando el diagnóstico esté documentado, los tests escritos/ejecutados y la falla documentada
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2. Escribir test de exploración de la condición de bug — Fórmulas del Excel `#NAME?` (Bug 2)
  - **Property 2: Bug Condition** - Fórmulas del Excel válidas en cualquier locale
  - **CRITICAL**: Estos tests DEBEN FALLAR sobre el código sin arreglar — la falla confirma que el Bug 2 existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Estos tests codifican el comportamiento esperado — validarán el fix cuando pasen luego de implementarlo
  - **GOAL**: Surface counterexamples de que las celdas de fórmula del Excel se emiten con nombres de función es-AR (`SI`/`CONTAR.SI`) y `;`, sintaxis inválida para el `.xlsx` que se muestra como `#NAME?`
  - Test en `backend/tests/unit/services/test_excel_cierre_cursada.py` (extender el archivo existente), leyendo las celdas generadas por `generar_excel_cierre`:
    - **Celda "Recuperable" (fila `n`)**: esperado que empiece con `=IF(F{n}<>"RECURSA","",IF(AND(` (inglés + coma); hoy empieza con `=SI(F{n}<>"RECURSA";"";SI(Y(` → FALLA
    - **Conteos del resumen (celda "PROMOCIONADOS")**: esperado `=COUNTIF(F:F,"PROMOCIONA")` (inglés + coma); hoy `=CONTAR.SI(F:F;"PROMOCIONA")` → FALLA
    - Detalle de la Bug Condition: `usaNombresFuncionEsAR(X) OR usaPuntoYComaComoSeparador(X)` para toda celda de fórmula `X` emitida (ver `isBugCondition2` en design/bugfix)
    - Las aserciones deben coincidir con la Expected Behavior Property (Property 2 del design) y con las fórmulas inglesas de 2.7/2.8
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_excel_cierre_cursada.py -k "recuperable or conteo or resumen or formula"`
  - **EXPECTED OUTCOME**: Los tests FALLAN (correcto — prueba que el Bug 2 existe)
  - Documentar los contraejemplos (celda Recuperable empieza con `=SI(...;`, conteos con `=CONTAR.SI(...;`)
  - Marcar la tarea como completa cuando los tests estén escritos, ejecutados y la falla documentada
  - _Requirements: 1.4, 1.5, 1.6_

## Fase 2 — Preservación (tests que PASAN antes del fix)

- [ ] 3. Escribir tests de preservación (property-based) — ANTES de los fixes
  - **Property 3: Preservation** - Comportamiento inalterado fuera de las condiciones de bug
  - **IMPORTANT**: Seguir la metodología observation-first — correr el código SIN arreglar con inputs que NO disparan ninguna condición de bug y capturar el comportamiento observado
  - Property-based testing recomendado para la preservación de la resolución de comisión y de la semántica de la fórmula "Recuperable" (genera muchos casos del dominio y detecta edge cases)
  - **Bug 1 (resolución de comisión)** — property-based en `test_cierre_cursada_service.py`:
    - **Ambigüedad genuina (3.1)**: alumno con DOS grupos de comisión distintos (`"A25 C2-01"` + `"A25 C2-02"`) que mapean a dos comisiones distintas → "Sin comisión asignada" (igual que hoy)
    - **Sin grupo de comisión (3.2)**: alumno sólo con grupos de estado/instancia/regional (`["R-Mendoza", "NO_RINDIERON_PARCIAL_1"]`) → "Sin comisión asignada"
    - **Único grupo bien vinculado (3.3, 3.4)**: alumno con `["M25 C3-01"]` cuyo `moodle_group_id` matchea la comisión → resuelto por el puente primario `moodle_group_id`, con el mismo orden/prioridad de puentes y `comision_id`/`comision_nombre`/`tutor_nombre` iguales
    - **Regional preservada (3.5)**: `parse_regional("R-Mendoza") == "Mendoza"` y `parse_comision("R-Mendoza") is None`
    - **No interrumpe la corrida (3.6)**: mapeo ambiguo/roto → `_resolver_comision` devuelve "Sin comisión asignada" sin lanzar excepción
    - Property-based: generar listas mezclando 0/1/≥2 grupos con formato de comisión (con `moodle_group_id` seteado o no) + N grupos que no son de comisión (algunos con `moodle_group_id` que colisiona con otra comisión) → con exactamente 1 grupo de comisión resuelve esa comisión; con 0 o ≥2 distintos → "Sin comisión asignada"
  - **Bug 2 (Excel)** — en `test_excel_cierre_cursada.py`:
    - **Estructura (3.7, 3.9)**: el `.xlsx` sigue con las dos hojas ("por Comisiones" y "Crudo"), estilos de la casa, celdas `N/E` y "Nota Final" en blanco para no-PROMOCIONA; abre con openpyxl
    - **Referencias/criterios de fórmula (3.8)**: las fórmulas conservan Estado `F` / parciales `C`-`D` / Recuperable `H` (por Comisiones) y Estado `H` / parciales `E`-`F` / Recuperable `J` (Crudo), con criterios comodín `"RECUPERABLE*"` (por Comisiones) y `"RECUPERABLE CON*"` (Crudo)
    - **Semántica Recuperable (3.9)**: property-based — generar combinaciones de notas de parciales y estado y verificar que la clasificación "RECUPERABLE CON PARCIAL 1/2" cae exactamente en los mismos casos que la fórmula es-AR pretendida (RECURSA con un parcial `>=40` y el otro `<40`/N/E-tratado-como-0)
    - **Celdas que no son fórmula (scope)**: valores literales (`"N/E"`, números) quedan inalterados
  - Ejecutar sobre el código SIN arreglar: `cd backend && pytest tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_excel_cierre_cursada.py tests/unit/services/test_gestion_parser.py`
  - **EXPECTED OUTCOME**: Los tests PASAN (confirma el comportamiento base a preservar)
  - Marcar la tarea como completa cuando los tests estén escritos, ejecutados y pasando sobre el código sin arreglar
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

## Fase 3 — Implementación de los fixes

- [ ] 4. Fix — Comisión multi-grupo: aislar el grupo de comisión + generalizar el regex (Bug 1)

  > **BLOQUEADO por la tarea 1**: no implementar hasta que el diagnóstico de la tarea 1 haya
  > confirmado (o re-hipotetizado) la causa raíz y validado que `"A25 C2-01"` sobrevive al filtro.

  - [ ] 4.1 Generalizar el regex de comisión a año de exactamente 2 dígitos
    - En `backend/app/services/gestion_parser.py`, reemplazar `_COMISION_RE = re.compile(r"^[MA]\d+\s+C\d+-\d+$")` por `_COMISION_RE = re.compile(r"^[MA]\d{2}\s+C\d+-\d+$")`
    - Sólo se acota el año a 2 dígitos (`\d{2}`); cohorte (`[MA]`), semestre (`C\d+`) y número de comisión (`-\d+`) no cambian → no se hardcodean cohorte/año/semestre concretos
    - `parse_comision`, `parse_regional` y `resolver_grupos_alumno` no cambian su firma; el efecto del regex más estricto se propaga solo
    - _Bug_Condition: isBugCondition1(X) — regex reconoce año con distinta cantidad de dígitos (1.3)_
    - _Expected_Behavior: Property 1 — regex generalizado `{cohorte}{año} C{semestre}-{NN}` con año de exactamente 2 dígitos (2.3)_
    - _Preservation: regionales `"R-*"` siguen sin matchear comisión (3.5); grupos de estado/instancia nunca matchean_
    - _Requirements: 2.3, 3.5_

  - [ ] 4.2 Resolver la comisión sólo desde los grupos con formato de comisión
    - En `backend/app/services/cierre_cursada_service.py`, `_resolver_comision`: filtrar los grupos del alumno a los de formato de comisión ANTES de aplicar los puentes — `grupos_comision = [g for g in grupos if parse_comision(g.get("name") or "")]` — e iterar sólo sobre `grupos_comision`, de modo que los grupos que no son de comisión no puedan aportar un match espurio por `moodle_group_id` ni disparar la regla de ambigüedad (`len(encontradas) != 1`)
    - Conservar el puente por `moodle_group_id` como PRIMARIO (con su `continue`) y el fallback por `parse_comision`/nombre; la firma y el contrato de retorno (`comision_id, comision_nombre, tutor_nombre`) no cambian
    - `generar` de `CierreCursadaService` NO cambia: sigue armando el mapa autoritativo `uid → grupos` y pasando la lista COMPLETA; el filtrado por formato vive dentro de `_resolver_comision`
    - Respetar Clean Architecture (lógica en el service, sin acceso directo a BD) y el máximo de 500 LOC por archivo
    - _Bug_Condition: isBugCondition1(X) — grupo no-comisión aporta segundo match/ambigüedad; grupo real falla los puentes (1.1, 1.2)_
    - _Expected_Behavior: Property 1 — identificar el grupo de formato de comisión y asignar esa comisión, ignorando estado/instancia/regional (2.1, 2.2, 2.4)_
    - _Preservation: ambigüedad genuina → "Sin comisión asignada" (3.1); sin grupo de comisión → "Sin comisión asignada" (3.2); puente `moodle_group_id` primario con su orden (3.3); `comision_id`/nombre/tutor iguales (3.4); nunca interrumpe la corrida (3.6)_
    - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 3.4, 3.6_

  - [ ] 4.3 Verificar que el test de exploración de Bug 1 ahora pasa
    - **Property 1: Expected Behavior** - Alumno multi-grupo asignado a su comisión real
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 1 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_gestion_parser.py -k "tamara or multigrupo or comision or regex or dos_digitos"`
    - **EXPECTED OUTCOME**: Los tests PASAN (TAMARA queda en `"A25 C2-01"`; `parse_comision("A2025 C2-01") is None`)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 4.4 Verificar que los tests de preservación siguen pasando (Bug 1)
    - **Property 3: Preservation** - Ambigüedad genuina, sin grupo, único grupo, regionales, corrida
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 3 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_cierre_cursada_service.py tests/unit/services/test_gestion_parser.py`
    - **EXPECTED OUTCOME**: Los tests PASAN (sin regresiones — 3.1, 3.2, 3.3, 3.4, 3.5, 3.6)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 5. Fix — Fórmulas del Excel en inglés con coma (Bug 2)

  - [ ] 5.1 Reescribir `_formula_recuperable` a inglés + coma
    - En `backend/app/services/excel_cierre_cursada.py`, reescribir el string de `_formula_recuperable(estado_col, p1_col, p2_col, fila)` traduciendo 1:1 la fórmula es-AR: `SI→IF`, `Y→AND`, `SI.ERROR→IFERROR`, `VALOR→VALUE`, `;→,`, produciendo `=IF({estado}{n}<>"RECURSA","",IF(AND(IFERROR(VALUE({p1}{n}),0)>=40,IFERROR(VALUE({p2}{n}),0)<40),"RECUPERABLE CON PARCIAL 2",IF(AND(IFERROR(VALUE({p2}{n}),0)>=40,IFERROR(VALUE({p1}{n}),0)<40),"RECUPERABLE CON PARCIAL 1","")))`
    - Los strings de comparación/resultado (`<>"RECURSA"`, `"RECUPERABLE CON PARCIAL 1/2"`, `""`) NO cambian (insensibles al locale); las letras de columna se siguen recibiendo como parámetros → mismas referencias por hoja (por Comisiones F/C/D; Crudo H/E/F)
    - _Bug_Condition: isBugCondition2(X) — fórmula Recuperable con `SI`/`Y`/`;` (1.4)_
    - _Expected_Behavior: Property 2 — fórmula Recuperable en inglés + coma, mismo resultado (2.5, 2.7)_
    - _Preservation: mismas referencias de columna y criterios; misma semántica de clasificación (3.8, 3.9)_
    - _Requirements: 2.5, 2.7, 3.8, 3.9_

  - [ ] 5.2 Reescribir `_formulas_conteo_resumen` a inglés + coma
    - En `excel_cierre_cursada.py`, reescribir `_formulas_conteo_resumen` cambiando `CONTAR.SI→COUNTIF` y `;→,`, produciendo las cinco tuplas: `=COUNTIF({estado}:{estado},"PROMOCIONA")`, `"REGULARIZA"`, `"RECURSA"`, `=COUNTIF({recuperable}:{recuperable},"{recuperable_criterio}")`, `"ABANDONO"`
    - Conservar los criterios comodín (`"RECUPERABLE*"` por Comisiones, `"RECUPERABLE CON*"` Crudo) y las referencias por hoja (por Comisiones Estado `F` / Recuperable `H`; Crudo Estado `H` / Recuperable `J`)
    - _Bug_Condition: isBugCondition2(X) — conteos con `CONTAR.SI`/`;` (1.5)_
    - _Expected_Behavior: Property 2 — conteos `COUNTIF` en inglés, mismos 5 conteos (2.5, 2.8)_
    - _Preservation: mismos criterios comodín y referencias por hoja (3.8, 3.9)_
    - _Requirements: 2.5, 2.8, 3.8, 3.9_

  - [ ] 5.3 Reescribir el docstring/nota de locale del módulo y comentarios inline
    - En `excel_cierre_cursada.py`, reescribir la nota del docstring del módulo que hoy declara la dependencia es-AR como intencional: documentar que las fórmulas se emiten con nombres de función en inglés y coma (sintaxis canónica del `.xlsx`), que Excel/Google Sheets las muestran traducidas al locale de apertura y que por eso abren sin `#NAME?` en cualquier locale
    - Actualizar los comentarios inline de `_escribir_resumen` / `_escribir_resumen_crudo` / `_escribir_hoja_cruda` que citan la sintaxis es-AR; `_recuperable_para_fila`, `_escribir_resumen`, `_escribir_detalle`, `_escribir_hoja_cruda` y `generar_excel_cierre` no cambian su lógica
    - Sin `print` de debug; máximo 500 LOC por archivo
    - _Bug_Condition: isBugCondition2(X) — premisa de locale equivocada en el docstring (1.6)_
    - _Expected_Behavior: Property 2 — fórmulas válidas en cualquier locale, sin `#NAME?` (2.6)_
    - _Preservation: estructura de dos hojas, estilos, `N/E` y "Nota Final" intactos (3.7)_
    - _Requirements: 2.6, 3.7_

  - [ ] 5.4 Actualizar las aserciones es-AR de los tests existentes a la sintaxis inglesa
    - En `backend/tests/unit/services/test_excel_cierre_cursada.py`, actualizar las aserciones enumeradas en design.md → "Tests existentes a actualizar (Bug 2)" (dejan de reflejar el comportamiento correcto tras el fix):
      - `test_resumen_de_conteos_como_formulas_nativas_a2_b6`: `'=CONTAR.SI(F:F;"PROMOCIONA")'`→`'=COUNTIF(F:F,"PROMOCIONA")'`, `"REGULARIZA"`, `"RECURSA"` análogos, `'=CONTAR.SI(H:H;"RECUPERABLE*")'`→`'=COUNTIF(H:H,"RECUPERABLE*")'`, `'=CONTAR.SI(F:F;"ABANDONO")'`→`'=COUNTIF(F:F,"ABANDONO")'`
      - `test_bug_conteo_promocionados_es_formula_no_entero`: `'=CONTAR.SI(F:F;"PROMOCIONA")'`→`'=COUNTIF(F:F,"PROMOCIONA")'`
      - `test_bug_columna_recuperable_es_formula_por_fila`: `startswith(f'=SI(F{n}<>"RECURSA";"";SI(Y(')`→`startswith(f'=IF(F{n}<>"RECURSA","",IF(AND(')`; `f"SI.ERROR(VALOR(C{n});0)>=40"`→`f"IFERROR(VALUE(C{n}),0)>=40"`; `f"SI.ERROR(VALOR(D{n});0)<40"`→`f"IFERROR(VALUE(D{n}),0)<40"` (los asserts de `"RECUPERABLE CON PARCIAL 1/2"` no cambian)
      - `test_bug_conteo_recuperables_y_abandonos_son_formulas`: `'=CONTAR.SI(H:H;"RECUPERABLE*")'`→`'=COUNTIF(H:H,"RECUPERABLE*")'`, `'=CONTAR.SI(F:F;"ABANDONO")'`→`'=COUNTIF(F:F,"ABANDONO")'`
    - _Bug_Condition: isBugCondition2(X) — tests aseveran la sintaxis es-AR defectuosa_
    - _Expected_Behavior: Property 2 — los tests aseveran la sintaxis inglesa correcta (2.5, 2.7, 2.8)_
    - _Preservation: no se agregan/eliminan tests; sólo se actualizan las aserciones de sintaxis (3.8)_
    - _Requirements: 2.5, 2.7, 2.8_

  - [ ] 5.5 Verificar que el test de exploración de Bug 2 ahora pasa
    - **Property 2: Expected Behavior** - Fórmulas del Excel válidas en cualquier locale
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 2 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_excel_cierre_cursada.py -k "recuperable or conteo or resumen or formula"`
    - **EXPECTED OUTCOME**: Los tests PASAN (celda Recuperable empieza con `=IF(...,` y conteos con `=COUNTIF(...,`)
    - _Requirements: 2.5, 2.6, 2.7, 2.8_

  - [ ] 5.6 Verificar que los tests de preservación siguen pasando (Bug 2)
    - **Property 3: Preservation** - Dos hojas, estilos, `N/E`, referencias/criterios, archivo abre con openpyxl
    - **IMPORTANT**: Re-ejecutar los MISMOS tests de la tarea 3 — NO escribir tests nuevos
    - Ejecutar: `cd backend && pytest tests/unit/services/test_excel_cierre_cursada.py`
    - **EXPECTED OUTCOME**: Los tests PASAN — dos hojas con estilos y `N/E` (3.7), mismas referencias/criterios (3.8), mismos valores/conteos y archivo que abre con openpyxl (3.9)
    - _Requirements: 3.7, 3.8, 3.9_

## Fase 4 — Checkpoint final

- [ ] 6. Checkpoint - Asegurar que todos los tests pasan (Bug 1 + Bug 2)
  - Ejecutar toda la suite del backend: `cd backend && pytest`
  - Confirmar que el test de exploración de Bug 1 (tarea 1) y de Bug 2 (tarea 2) ahora PASAN, y que los tests de preservación (tarea 3) SIGUEN pasando — todos verdes juntos
  - Confirmar unit (`test_gestion_parser.py`, `test_cierre_cursada_service.py`, `test_excel_cierre_cursada.py`), property-based (resolución de comisión, regex generalizado, semántica de la fórmula Recuperable) e integración (cierre end-to-end con Moodle mockeado — TAMARA queda en `"A25 C2-01"`, Excel de dos hojas con fórmulas en inglés que abren sin `#NAME?`)
  - QA checklist del proyecto: sin `print`/`console.log` de debug, permisos validados en endpoints (no se tocaron routers), schemas Pydantic sin cambios, sin migraciones nuevas (no hay cambios de modelo), sin secrets, máximo 500 LOC por archivo, sin archivos temporales
  - Asegurar que todos los tests pasan; consultar al usuario si surgen dudas (en particular si el diagnóstico de la tarea 1 refutó (a)/(c) y confirmó (b), que requiere revisar el dato de la comisión en la BD)
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

---

## Task Dependency Graph

```
1. DIAGNÓSTICO + Bug Condition exploration Bug 1 (FALLA en unfixed, GATING) ─┐
2. Bug Condition exploration Bug 2 (FALLA en unfixed) ───────────────────────┤
3. Preservation tests property-based (PASAN en unfixed) ─────────────────────┤
                                                                             │
                        ┌────────────────────────────────────────────────────┘
                        v
   Fix Bug 1 (BLOQUEADO por diagnóstico de la tarea 1):
        4.1 Regex generalizado (gestion_parser.py) ──┐
        4.2 Aislar grupo de comisión (_resolver_comision) ──┤ (4.2 usa el regex de 4.1)
                        │                             │
                        v                             │
        4.3 Re-run test tarea 1 (ahora PASA) <────────┘
        4.4 Re-run tests preservación tarea 3 (siguen PASANDO)

   Fix Bug 2 (independiente de Bug 1):
        5.1 _formula_recuperable → inglés+coma ──┐
        5.2 _formulas_conteo_resumen → inglés+coma ──┤
        5.3 Docstring/nota de locale ────────────────┤
        5.4 Actualizar aserciones es-AR de los tests ┤ (tras 5.1/5.2)
                        │                             │
                        v                             │
        5.5 Re-run test tarea 2 (ahora PASA) <────────┘
        5.6 Re-run tests preservación tarea 3 (siguen PASANDO)
                        │
                        v
6. Checkpoint — pytest completo del backend (Bug 1 + Bug 2 verdes juntos)
```

Dependencias clave:
- **1, 2 y 3** deben completarse ANTES de cualquier cambio de código (baseline: 1 y 2 fallan, 3 pasa).
- **1 es GATING del fix de Bug 1** (tarea 4): el diagnóstico debe confirmar/refutar la causa raíz
  y validar que `"A25 C2-01"` sobrevive al filtro antes de codificar.
- **4.1** (regex) es prerequisito de **4.2** (el filtro `parse_comision` usa el regex generalizado).
- **Fix Bug 1 (4.x) y Fix Bug 2 (5.x) son independientes** y pueden hacerse en paralelo.
- **4.3/4.4** requieren 4.1+4.2; **5.5/5.6** requieren 5.1–5.4.
- **6** cierra corriendo toda la suite con ambos fixes + preservación verdes juntos.
