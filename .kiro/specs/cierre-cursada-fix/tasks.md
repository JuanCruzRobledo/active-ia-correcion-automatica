# Plan de Implementación — Cierre de Cursada (Bugfix)

Metodología bugfix: **reproducir** el defecto sobre el código SIN arreglar (tests
exploratorios que FALLAN) → **fijar la línea base** que no debe cambiar (tests de
preservación que PASAN sobre el código sin arreglar) → **implementar** el fix dirigido por
`ExamenMateria` → **verificar** que los exploratorios pasan y la preservación se mantiene.

Todas las funciones puras nuevas viven en `cierre_cursada_calculo.py` (sin I/O). Se respeta
Clean Architecture (Router → Service → Repository), el máximo de **500 LOC por archivo**
(se marca extracción donde aplica) y `pytest` para todos los tests del backend.

> **PBT / hypothesis:** los tests basados en propiedades usan `hypothesis`, que hoy NO está
> en `backend/requirements.txt`. La primera tarea que lo necesita debe agregar
> `hypothesis` a `backend/requirements.txt` e instalarlo (`pip install hypothesis`).

> **Frontend (HAY regresión — corregir):** existe una pantalla **"Cierre de cursada"** en
> la ruta `/cierre-cursada`, implementada en `frontend/src/features/cierre-cursada/`, que
> HOY consume exactamente los endpoints/campos que este fix elimina (los `/items` de mapeo
> manual y el `umbral_tp_pct`/`reglas` del `generar`). Por lo tanto este fix SÍ produce
> regresiones de frontend que se resuelven en la misma entrega (ver **tarea 16**). Se
> mantiene TypeScript strict y la estructura feature-folder; la verificación del frontend es
> `npm run build` + `npm run lint` (AGENTS.md).

---

- [x] 1. Escribir tests exploratorios de la Bug Condition (ANTES del fix)
  - **Property 1: Bug Condition** - Clasificación/planilla sin consumir ExamenMateria
  - **CRÍTICO**: estos tests DEBEN FALLAR sobre el código sin arreglar — la falla confirma
    que el bug existe. **NO** arreglar el test ni el código cuando fallen.
  - **NOTA**: estos tests codifican el comportamiento esperado; validarán el fix cuando pasen
    tras la implementación (tareas 11.x).
  - **GOAL**: exhibir contraejemplos que demuestren la causa raíz (sistema paralelo con
    umbrales fijos + mapeo manual + layout ad-hoc + Nota Final mal calculada).
  - **Enfoque PBT acotado**: para los casos determinísticos, acotar la propiedad a los casos
    concretos que fallan (abajo) para reproducibilidad.
  - Archivo: `backend/tests/unit/services/test_cierre_cursada_calculo.py` (clasificación /
    Nota Final) y `backend/tests/unit/services/test_excel_cierre_cursada.py` (layout).
  - Casos que fallan sobre el código actual (de "Exploratory Bug Condition Checking" del diseño):
    1. Parcial `nota_minima=50` (escala 100), alumno con `55` → esperado: aprueba el mínimo;
       actual: `calcular_estado` compara contra el fijo `60` y NO lo aprueba. (Req 1.1)
    2. Materia con examen GLOBAL; alumno aprueba parciales y NO rinde el global → esperado:
       **REGULARIZA** (global opcional para regular, obligatorio para promoción); actual: el
       global no existe como concepto → clasifica sin exigirlo. (Req 1.2)
    3. Parcial `nota_minima=70` (escala 100), alumno con `55` → banda esperada `50` (55 ≥ 50
       → REGULARIZA); actual usa el fijo `parcial_regulariza_min_pct=40`. (Req 1.3, 1.4)
    4. Parcial `nota_minima=6` (escala 10), alumno con `4` → banda `2` (4 ≥ 4 → REGULARIZA);
       actual trata `4` como 4 % → RECURSA. (Req 1.3)
    5. Excel: generar con una corrida de ejemplo y comparar headers/estructura contra el
       modelo CORREGIDO → el actual trae `TPs Aprobados / Autoeval OK / TPI / Habilitado para
       Final` + dona, que el modelo NO tiene. (Req 1.5)
    6. Nota Final: alumno REGULARIZA con parciales y global numéricos → el generador actual
       deja `nota_final = None` (`N/E`, sólo la computa para PROMOCIONA); esperado: NF
       numérica ponderada. Y alumno con parciales escala 100 + global escala 10 → el cálculo
       viejo (`round_half_up(nf/10)` sobre crudos mezclados) da un valor incorrecto vs. la NF
       con escala normalizada. (Req 1.7)
  - Marcar que el mapeo manual (`CierreCursadaItem`) es exigido hoy para calcular (Req 1.6):
    documentar que `generar` bloquea con 400 si faltan ítems por confirmar (comportamiento a
    eliminar).
  - Ejecutar sobre el código SIN arreglar: `pytest backend/tests/unit/services/test_cierre_cursada_calculo.py backend/tests/unit/services/test_excel_cierre_cursada.py`
  - **RESULTADO ESPERADO**: los tests FALLAN (correcto — prueban que el bug existe).
  - Documentar los contraejemplos encontrados (veredicto real vs. esperado; headers reales
    vs. modelo; NF real vs. esperada).
  - Marcar la tarea completa cuando los tests estén escritos, corridos y la falla documentada.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

- [x] 2. Escribir tests de preservación (ANTES del fix)
  - **Property 2: Preservation** - Comportamiento no relacionado sin cambios
  - **IMPORTANTE**: seguir metodología observación-primero — observar el comportamiento del
    código SIN arreglar y escribir property-based tests que capturen ese comportamiento.
  - Observar y capturar sobre el código actual (deben PASAR sobre el código sin arreglar):
    1. **Cadena de rescate** (`examen_mapper.calcular_resultados_examenes`): parcial
       desaprobado + recuperatorio aprobado → `resultado == "aprobado"` y `rescatado == True`.
       Precedencia `aprobado > sin_corregir > desaprobado > ausente`. (Req 3.1)
    2. **Examen ESCALA** (`examen_mapper.interpretar_resultado`): "Aprobado"/"Desaprobado"/""
       → `aprobado`/`desaprobado`/`ausente`, evaluado por escala y no por nota numérica. (Req 3.2)
    3. **Agrupación por comisión/tutor** (`CierreCursadaService._resolver_comision`): un match
       único → `(comision_id, nombre, tutor)`; 0 o >1 matches → `(None, "Sin comisión
       asignada", None)`. (Req 3.3, 3.6)
    4. **Histórico append-only** (`CierreCursadaRepository.crear_run`/`listar_runs`): dos
       corridas de la misma materia coexisten, más reciente primero, sin sobrescribir. (Req 3.4)
    5. **Estilos de la casa** (`excel_estilos`): el `.xlsx` sigue usando `banda_titulo`,
       `celda_header`, `fila_datos`, `FILL_BLOQUE`/`FONT_BLOQUE`, paleta y bordes. (Req 3.5)
  - Property-based (con `hypothesis`) para rescate y escala en
    `backend/tests/unit/services/test_examen_mapper.py`; el resto como tests puntuales en
    `test_cierre_cursada_service.py`.
  - Ejecutar sobre el código SIN arreglar: `pytest backend/tests/unit/services/test_examen_mapper.py backend/tests/unit/services/test_cierre_cursada_service.py`
  - **RESULTADO ESPERADO**: los tests PASAN (confirman la línea base a preservar).
  - Marcar la tarea completa cuando los tests estén escritos, corridos y pasando.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Funciones puras de escala en `cierre_cursada_calculo.py`
  - Agregar `detectar_escala(nota_minima)` → `100 | 10 | None` (None si `nota_minima is None`;
    `100` si `>= 10`, si no `10`). Ver "Detección de escala" del diseño.
  - Agregar `banda_regular(nota_minima)` → `20` (escala 100), `2` (escala 10), `None` (ESCALA).
  - Agregar `normalizar_a_10(valor_real, nota_minima)` → escala 100 divide por 10; escala 10
    (o None) sin cambio; `None` si `valor_real is None`.
  - Conservar `round_half_up` (lo reutiliza la Nota Final). Mantener el módulo SIN I/O.
  - Tests unitarios en `test_cierre_cursada_calculo.py`: `6→10/2`, `60→100/20`, frontera `10`,
    `None` (ESCALA), mínimos `50`/`7`; `normalizar_a_10(80, 60)==8.0`, `(9.0, 6)==9.0`,
    `(None, x) is None`.
  - _Requirements: 2.4_
  - _Design: Correctness Property 4 (normalización), sección "Detección de escala"_

- [x] 4. Función pura de clasificación `calcular_estado_cierre` (reemplaza `calcular_estado`)
  - Implementar `cumple_minimo(examen)`, `cumple_banda(examen)` y `calcular_estado_cierre(
    examenes)` según el pseudocódigo del diseño ("Algoritmo de clasificación").
  - Entrada por examen principal: `{examen_id, tipo, modo_aprobacion, nota_minima, valor_real,
    resultado_escala}`. GLOBAL obligatorio para PROMOCIONA, excluido de la banda de REGULARIZA.
    ESCALA sin banda (`cumple_minimo == cumple_banda == resultado=='aprobado'`).
  - `calcular_estado_cierre` devuelve `{estado, resultados_examenes, global_valor, nota_final}`
    (la `nota_final` llamando a `calcular_nota_final`, tarea 5). `global_valor` = mejor
    `valor_real` del examen GLOBAL (o `None`).
  - Guard: lista vacía de exámenes principales → lanzar `SinExamenesConfigurados` (el service
    lo traduce a HTTP 400 en tarea 8).
  - Eliminar del módulo el sistema viejo: `sugerir_categoria`, las regex `_RE_*`, `tp_ok`,
    `autoeval_ok`, las constantes `CATEGORIA_*` y `_UNIDADES_OPCIONALES_DEFAULT`, y la vieja
    `calcular_estado`. Conservar `max_o_none` sólo si sigue usándose.
  - Tests unitarios: PROMOCIONA (todos incl. global), REGULARIZA (banda, global opcional),
    RECURSA; sin global; guard sin exámenes; borde `valor == nota_minima` (`>=`) y
    `valor == nota_minima − banda`.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 2.10_
  - _Design: Correctness Property 1_

- [x] 5. Función pura `calcular_nota_final` (Nota Final ponderada, escala normalizada)
  - Implementar `calcular_nota_final(examenes)` según el pseudocódigo del diseño ("Nota Final"):
    normalizar cada examen a 0–10 con `normalizar_a_10`, promediar los N PARCIAL, ponderar
    `promedio*0.4 + global*0.6`, `round_half_up` a entero 0–10.
  - Devolver `None` (`N/E`) si hay 0 parciales, ≠1 global, o algún insumo requerido falta
    (parcial/global ausente o en modo ESCALA sin valor numérico). Reutiliza `valor_real` (con
    rescate ya aplicado) — los mismos insumos que `calcular_estado_cierre`.
  - Tests unitarios (de "Unit Tests" del diseño): `P1=8,P2=6,Global=9`(escala 10)→`8`;
    3 parciales `(8,6,10)`→`8*0.4+Global*0.6`; falta global→`None`; falta un parcial→`None`;
    escala mixta `P1=80,P2=60(min60)+Global=9.0(min6)`→`8` (NO `28+5.4`); redondeo `6.5→7`,
    `6.49→6`.
  - _Requirements: 2.11, 2.13_
  - _Design: Correctness Property 4_

- [x] 6. Tests basados en propiedades (PBT) de las funciones puras
  - Agregar `hypothesis` a `backend/requirements.txt` e instalar.
  - En `test_cierre_cursada_calculo.py`, cubrir las 12 propiedades del diseño ("Property-Based
    Tests"):
    - Clasificación (1–8): monotonía (cumple mínimo en todos → PROMOCIONA); Regular ⊇ banda;
      Recursa por defecto; borde en el mínimo (`>=`); borde en la banda (4=6−2, 40=60−20);
      escala 10 vs 100 no se cruzan; rescate ⇒ cumple_minimo; global (quitarlo no cambia
      Regular, agregar uno no cumplido bloquea Promociona).
    - Nota Final (9–12): rango `[0,10]` cuando no es `N/E`; `N/E` sii falta insumo; monotonía
      no decreciente en cada insumo (antes de redondear); la escala no se filtra (mismo examen
      en escala 100 o 10 → misma NF).
  - Generadores: nº de parciales, presencia de global, `modo_aprobacion`, `nota_minima ∈
    {6,60,50,70}`, valores obtenidos, cadenas de rescate.
  - Ejecutar: `pytest backend/tests/unit/services/test_cierre_cursada_calculo.py`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.11, 2.13_
  - _Design: Correctness Properties 1 y 4_

- [x] 7. Extender `examen_mapper.calcular_resultados_examenes` con el mejor `valor_real`
  - Agregar a cada resultado principal el campo `valor_real`: mejor nota numérica entre la
    instancia base y sus rescates (usar `parsear_nota_numerica` sobre `notas_uid`; `None` si
    ausente o modo ESCALA sin nota). Exponer también `modo_aprobacion` y `nota_minima` del
    principal para que el service arme la entrada de `calcular_estado_cierre`.
  - **No romper firmas existentes** usadas por el dashboard de gestores: sólo AGREGAR campos
    al dict de salida, no quitar `resultado`/`rescatado`/`etiqueta`/`numero`. Preservar la
    precedencia de rescate y `interpretar_resultado`.
  - Tests de preservación (los de la tarea 2 deben seguir pasando) + nuevos: `valor_real` =
    máximo entre base y rescates; `None` para ESCALA; no cambia `resultado`.
  - Ejecutar: `pytest backend/tests/unit/services/test_examen_mapper.py`
  - _Requirements: 3.1, 3.2_
  - _Design: Correctness Property 2 (preservación), sección "examen_mapper"_

- [x] 8. Modelos y schemas (`models/cierre_cursada.py`, `schemas/cierre_cursada.py`)

  - [x] 8.1 Modelos SQLAlchemy
    - Eliminar el modelo `CierreCursadaItem` (la tabla se dropea en la migración, tarea 12).
    - `CierreCursadaRun`: hacer `umbral_tp_pct` y `reglas_snapshot` **nullable** (legacy, dejar
      de escribir); agregar `examenes_snapshot` (JSONB nullable) para congelar la config de
      exámenes de la corrida (reproducibilidad histórica).
    - `CierreCursadaAlumno`: agregar `resultados_examenes` (JSONB nullable) y `global_valor`
      (Float nullable). Reutilizar `nota_final` (Integer nullable, 0–10) con la nueva semántica
      (se llena para todos, `N/E` sólo si falta insumo). Hacer **nullable** las columnas legacy:
      `tp_ok`, `autoeval_ok`, `p1_max`, `p2_max`, `tpi_max`, `parcial1_instancias`,
      `parcial2_instancias`, `tpi_instancias`, `habilitado_final`. Conservar `estado`, `nombre`,
      `apellido`, `email`, `comision_id`, `comision_nombre`, `tutor_nombre`.
    - Actualizar el docstring del módulo (ya no describe el mapeo manual).
  - [x] 8.2 Schemas Pydantic
    - Eliminar `CierreItemSugeridoResponse`, `CierreItemConfirmado`, `CierreMappingConfirmRequest`,
      `CierreMappingConfirmResponse`.
    - `GenerarCierreRequest`: quitar `umbral_tp_pct`, `reglas` y el `model_validator`; queda sólo
      `cuatrimestre_id`.
    - `CierreRunResponse`: quitar `umbral_tp_pct` (o dejarlo opcional para corridas legacy).
    - Quitar el import de `CategoriaItemCierreEnum` si queda sin uso.
  - _Requirements: 2.7, 2.10, 3.4_
  - _Design: "Destino de CierreCursadaItem"_

- [x] 9. Repository (`repositories/cierre_cursada_repository.py`)
  - Eliminar `get_mapping` y `upsert_mapping` (y el import de `CierreCursadaItem`).
  - Conservar `crear_run`, `get_run`, `listar_runs`, `get_alumnos_de_run` sin cambios de
    contrato (acceso a BD sólo vía repo — AGENTS.md).
  - _Requirements: 2.7, 3.4_
  - _Design: sección "repositories/cierre_cursada_repository.py"_

- [x] 10. Router (`routers/cierre_cursada.py`)
  - Eliminar los endpoints `GET /materias/{materia_id}/items` y `POST /materias/{materia_id}/items`
    (mapeo manual) y las funciones `obtener_items_calificador`/`confirmar_mapping`.
  - `POST /materias/{materia_id}/generar`: nueva firma sin `umbral_tp_pct`/`reglas` (llama a
    `service.generar(materia_id, payload.cuatrimestre_id, current_user)`).
  - Conservar `GET /runs/{run_id}/excel` y `GET /materias/{materia_id}/historial` sin cambios.
  - Preservar los códigos HTTP: 404 (no encontrado), 400 (validación / sin exámenes), 424 (sin
    credenciales Moodle, patrón `_requerir_credenciales_moodle`), 502 (error Moodle). Sin lógica
    de negocio en el router (AGENTS.md).
  - Actualizar imports de schemas eliminados.
  - _Requirements: 2.7_
  - _Design: sección "routers/cierre_cursada.py", "Convenciones de error"_

- [x] 11. Servicio (`services/cierre_cursada_service.py`) — orquestación dirigida por ExamenMateria

  - [x] 11.1 Reemplazar la generación por el flujo dirigido por config
    - Inyectar `ExamenRepository`; en `generar`, cargar `examenes = await
      ExamenRepository(db).get_by_materia(materia_id)`.
    - **Guard nuevo**: si no hay exámenes PARCIAL/GLOBAL configurados → `HTTPException(400, "La
      materia no tiene exámenes configurados en el dashboard")`.
    - Quitar `umbral_tp_pct`/`reglas_override`, `REGLAS_CIERRE_DEFAULT`, `por_categoria`, los
      guards de mapeo, `_MODNAMES_CALIFICABLES`, `_items_del_curso`, `_parse_pct`, `_tp_resultado`,
      y toda referencia a `CierreCursadaItem`/`CategoriaItemCierreEnum`/`sugerir_categoria`.
    - Eliminar los métodos `obtener_items_calificador` y `confirmar_mapping`.
    - Reusar la descarga masiva actual (WS + sesión + `parsear_export_calificador_dual`) y, para
      exámenes con fuente `assign`, opcionalmente el grade estructural.
    - Armar la config por examen `{id, tipo, moodle_cmid, modo_aprobacion, nota_minima,
      recupera_examen_id, orden}` y llamar a `examen_mapper.calcular_resultados_examenes` para
      resolver rescates + `valor_real`; por alumno llamar a `calcular_estado_cierre` (+ Nota Final).
    - Poblar `CierreCursadaAlumno`: `estado`, `resultados_examenes`, `global_valor`, `nota_final`
      (de `calcular_nota_final`); dejar de escribir las columnas legacy.
    - Poblar `CierreCursadaRun` con `examenes_snapshot` (config congelada); no escribir
      `umbral_tp_pct`/`reglas_snapshot`.
    - **Conservar 1:1** `_resolver_comision` (Req 3.3, 3.6) y la persistencia append-only vía
      `crear_run` (Req 3.4). Mantener el registro de actividad `CIERRE_CURSADA_GENERADO`.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.7, 2.9, 2.10, 2.11, 2.13, 3.1, 3.2, 3.3, 3.4, 3.6_
    - _Bug_Condition: isBugCondition(input) — tiene_config AND (clasifica_con_umbral_fijo OR ignora_global OR ignora_banda_relativa OR exige_mapeo_manual OR nota_final_incorrecta)_
    - _Expected_Behavior: veredicto y NF derivados EXCLUSIVAMENTE de ExamenMateria (calcular_estado_cierre + calcular_nota_final)_
    - _Preservation: rescate, ESCALA, comisión/tutor, append-only, fallback "Sin comisión asignada"_
    - _Design: Correctness Properties 1 y 4, secciones "cierre_cursada_service.py" y "Data Flow"_

  - [x] 11.2 Vigilar el límite de 500 LOC
    - Si el service supera las 500 LOC, extraer el armado de config de examen (config por examen +
      normalización de notas por alumno) a un helper (p. ej. `cierre_cursada_builder.py`). Marcar
      la extracción si ocurre.
    - _Requirements: 2.7_

  - [x] 11.3 Verificar el test exploratorio de clasificación/NF (Property 1)
    - **Property 1: Expected Behavior** - Clasificación dirigida por ExamenMateria
    - **IMPORTANTE**: re-ejecutar los MISMOS tests de la tarea 1 (no escribir tests nuevos).
    - Ejecutar: `pytest backend/tests/unit/services/test_cierre_cursada_calculo.py`
    - **RESULTADO ESPERADO**: los tests de clasificación y Nota Final PASAN (bug resuelto).
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.11, 2.13_

  - [x] 11.4 Verificar que la preservación se mantiene (Property 2)
    - **Property 2: Preservation** - Comportamiento no relacionado sin cambios
    - **IMPORTANTE**: re-ejecutar los MISMOS tests de la tarea 2 (no escribir tests nuevos).
    - Ejecutar: `pytest backend/tests/unit/services/test_examen_mapper.py backend/tests/unit/services/test_cierre_cursada_service.py`
    - **RESULTADO ESPERADO**: los tests PASAN (sin regresiones en rescate/ESCALA/comisión/append-only/estilos).
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 12. Excel (`services/excel_cierre_cursada.py`) — layout del modelo CORREGIDO + Nota Final
  - Reescribir al layout del modelo CORREGIDO (sección "Layout exacto" del diseño): título
    `TOTAL MATERIA {NOMBRE}` (merge `A1:B1`), resumen de 3 filas
    `PROMOCIONADOS/REGULARES/RECURSANTES` con conteo en `A2:B4`, **sin dona**.
  - Columnas dinámicas: `Nombre y Apellido | Email | Parcial n… | Global TPI | Estado Alumno |
    Nota Final`. Una columna `Parcial n` por cada examen PARCIAL (numerado por `orden` /
    `examen_mapper.etiqueta_examen`), una `Global TPI` para el GLOBAL, y `Nota Final` como
    **última** columna (después de `Estado Alumno`). **Sin** columnas `TPs Aprobados / Autoeval
    OK / TPI / Habilitado para Final`.
  - Barra de bloque por comisión `COMISION N - TUTOR {NOMBRE}` mergeando desde la columna **C**
    hasta la última columna (`Nota Final`; con 2 parciales → `C..G`): parametrizar `barra_bloque`
    con columna inicial o mergear `C..{última}` explícito reutilizando `FILL_BLOQUE`/`FONT_BLOQUE`.
  - Formato de celdas: `Parcial n` = `valor_real` numérico o `N/E`; `Global TPI` = `global_valor`
    numérico o `N/E`; `Estado Alumno` = `PROMOCIONA/REGULARIZA/RECURSA`; `Nota Final` = entero
    0–10 (`a.nota_final`) o `N/E` (reutilizar `_fmt_nota_final`).
  - **Fix del resaltado RECURSA**: `Estado Alumno` ya NO es la última columna → recalcular el
    índice de columna a resaltar (ya no `len(HEADERS)`).
  - Reusar `banda_titulo`, `celda_header`, `fila_datos`, `sheet_title`, `sanitize_filename` y la
    paleta/bordes de `excel_estilos.py` (Req 3.5). Actualizar anchos iterando sobre el total real
    de columnas.
  - Tests en `test_excel_cierre_cursada.py`: headers exactos y en orden
    (`Nombre y Apellido | Email | Parcial 1 | Parcial 2 | Global TPI | Estado Alumno | Nota
    Final`); resumen de 3 conteos en `A2:B4`; barra de bloque mergeando `C..G`; **sin** columnas
    TP y **sin** dona (0 charts); celda `Nota Final` = entero o `N/E`; `Global TPI` = `N/E` cuando
    `global_valor is None`.
  - _Requirements: 2.6, 2.8, 2.9, 2.12, 3.5_
  - _Design: Correctness Property 3, sección "Layout exacto del modelo CORREGIDO"_

- [x] 13. Migración Alembic (`backend/alembic/versions/`)
  - Generar la revisión (`alembic revision --autogenerate -m "cierre_cursada dirigido por examenes"`)
    y revisarla a mano.
  - `drop_table('cierre_cursada_items')` (+ drop del tipo `categoriaitemcierreenum` si no lo usa
    ningún otro módulo — verificar primero con búsqueda).
  - `cierre_cursada_runs`: `alter_column` a nullable en `umbral_tp_pct` y `reglas_snapshot`;
    `add_column` `examenes_snapshot` (JSONB nullable).
  - `cierre_cursada_alumnos`: `alter_column` a nullable en las columnas legacy (`tp_ok`,
    `autoeval_ok`, `p1_max`, `p2_max`, `tpi_max`, `parcial1_instancias`, `parcial2_instancias`,
    `tpi_instancias`, `habilitado_final`); `add_column` `resultados_examenes` (JSONB nullable) y
    `global_valor` (Float nullable). (No se agrega ninguna columna de TPs.)
  - Implementar `downgrade` coherente (recrear tabla/columnas). Aplicar y verificar:
    `alembic upgrade head` y luego `alembic downgrade -1 && alembic upgrade head` en entorno local.
  - Las corridas viejas quedan legibles; su Excel regenerado usa el layout nuevo (best-effort).
  - _Requirements: 2.7, 3.4_
  - _Design: "Implicancias de migración"_

- [x] 14. Tests de integración (`backend/tests/integration/api/`)
  - Flujo completo `POST /cierre-cursada/materias/{id}/generar` con Moodle mockeado (export dual +
    config de `ExamenMateria`): conteos PROMOCIONA/REGULARIZA/RECURSA correctos, agrupación por
    comisión, corrida persistida (append-only: una segunda corrida no pisa la primera).
  - `GET /cierre-cursada/runs/{id}/excel` → `.xlsx` con el layout del modelo CORREGIDO (6 columnas
    + `Nota Final` última, sin TPs, sin dona), Nota Final poblada para alumnos con insumos y `N/E`
    para el resto.
  - Materia sin exámenes → `400`. Usuario sin credenciales Moodle → `424`. Corrida inexistente →
    `404`. Error de Moodle → `424/502`.
  - Ejecutar: `pytest backend/tests/integration/api`
  - _Requirements: 2.6, 2.7, 2.8, 2.9, 2.12, 3.3, 3.4_
  - _Design: sección "Integration Tests", "Convenciones de error"_

- [x] 15. Checkpoint — toda la suite verde
  - Ejecutar la suite completa del backend: `pytest` (desde `backend/`).
  - Confirmar: los exploratorios de la tarea 1 ahora PASAN; los de preservación (tarea 2) siguen
    PASANDO; unitarios + PBT + integración en verde.
  - Verificar el límite de 500 LOC en los archivos tocados (`cierre_cursada_service.py`,
    `excel_cierre_cursada.py`, `cierre_cursada_calculo.py`) y que no quedan referencias colgadas a
    `CierreCursadaItem` / `CategoriaItemCierreEnum` / `sugerir_categoria` / `umbral_tp_pct`.
  - Ante cualquier duda o falla que no se explique por el fix, consultar al usuario.
  - Este checkpoint cubre **backend** (`pytest`); el frontend se verifica en la tarea 16
    (`npm run build` + `npm run lint`). Ambas verificaciones deben quedar en verde para dar
    por cerrada la entrega.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 16. Frontend — alinear la pantalla "Cierre de cursada" al contrato nuevo (`frontend/src/features/cierre-cursada/`)

  Depende del cambio de contrato del backend (tareas 8 y 10): los tipos, el servicio y la UI
  se ajustan al `generar` sin `umbral_tp_pct`/`reglas` y a la eliminación de los endpoints
  `/items`. Mantener **TypeScript strict** y la estructura feature-folder (AGENTS.md).

  - [x] 16.1 Eliminar el componente de mapeo manual
    - Borrar `components/ItemsMappingEditor.tsx` completo (UI de categorías
      TP/AUTOEVAL/PARCIAL_1/PARCIAL_2/TPI/IGNORAR, conteos y confirmación de ítems): el mapeo
      manual desaparece, la fuente de verdad pasa a ser `ExamenMateria` (backend).
    - _Requirements: 2.7_
    - _Design: "Impacto frontend — cambios concretos" (punto 1)_

  - [x] 16.2 `types/index.ts` — alinear los tipos al contrato nuevo
    - Eliminar `CategoriaItemCierre`, `CierreItemSugerido`, `CierreItemConfirmado` y
      `ReglasCierreOverride` (todo el vocabulario del mapeo manual).
    - `GenerarCierreInput` pasa a ser `{ cuatrimestre_id: number }` (sin `umbral_tp_pct` ni
      `reglas`).
    - `CierreRun`: eliminar `umbral_tp_pct`. Conservar `EstadoCierre`
      (`PROMOCIONA | REGULARIZA | RECURSA`) y el resto de campos de `CierreRun`.
    - _Requirements: 2.7_
    - _Design: "Impacto frontend — cambios concretos" (punto 6)_

  - [x] 16.3 `services/cierre-cursada.service.ts` — quitar el mapeo manual
    - Eliminar `getItems()` y `confirmarMapping()` (endpoints `/items` borrados) y sus imports
      de tipos (`CierreItemSugerido`, `CierreItemConfirmado`).
    - Ajustar `generar()` al nuevo `GenerarCierreInput` (sólo `{ cuatrimestre_id }`).
    - Conservar `descargarExcel()` y `getHistorial()` sin cambios.
    - _Requirements: 2.7_
    - _Design: "Impacto frontend — cambios concretos" (punto 3)_

  - [x] 16.4 `hooks/useCierreCursada.ts` — quitar hooks y key del mapeo
    - Eliminar `useCierreItems` y `useConfirmarMapping`, la key `items` de
      `cierreCursadaKeys`, y el import de `CierreItemConfirmado`.
    - Conservar `useGenerarCierre` y `useHistorialCierre` (este último sigue usando la key
      `historial`).
    - _Requirements: 2.7_
    - _Design: "Impacto frontend — cambios concretos" (punto 4)_

  - [x] 16.5 `pages/CierreCursadaPage.tsx` — quitar el paso de mapeo y el umbral
    - Eliminar el render de `<ItemsMappingEditor />` y su import, la sección "Mapeo de ítems
      del calificador" y sus estados de carga/error (`itemsQuery.isLoading/.error/.data`) →
      quitar el uso de `useCierreItems`.
    - Eliminar el input **"% mínimo de TPs aprobados"**, el estado `umbralTp`/`setUmbralTp` y
      la validación `umbralValido`.
    - `handleGenerar` ahora envía **sólo** `{ cuatrimestre_id: cuatrimestreId }` y luego
      `descargarExcel(run.id)`.
    - Conservar los selectores de **materia + cuatrimestre** y la tabla de **historial**
      (`useHistorialCierre`). Actualizar el docstring/flujo de la pantalla (elegir materia +
      cuatrimestre → generar y descargar Excel; ya no hay revisión de mapeo).
    - _Requirements: 2.7_
    - _Design: "Impacto frontend — cambios concretos" (punto 2), "Flujo resultante de la pantalla"_

  - [x] 16.6 `components/HistorialRunsTable.tsx` — quitar la columna "Umbral TP"
    - Eliminar el `<th>Umbral TP</th>` y la celda `{r.umbral_tp_pct}%` (el campo desaparece de
      `CierreRun`). El resto de la tabla (Generado / Promociona / Regulariza / Recursa / Total
      + descarga de Excel) se conserva.
    - _Requirements: 2.7_
    - _Design: "Impacto frontend — cambios concretos" (punto 5)_

  - [x] 16.7 Verificación del frontend (typecheck + lint)
    - Ejecutar `npm run build` (typecheck + build) y `npm run lint` desde `frontend/` (AGENTS.md).
    - Confirmar que no quedan errores de TypeScript strict tras eliminar los tipos del mapeo,
      ni referencias colgantes a `getItems`/`confirmarMapping`/`useCierreItems`/
      `useConfirmarMapping`/`ItemsMappingEditor`/`umbral_tp_pct`.
    - **Nota**: esta verificación depende de que el contrato del backend (tareas 8 y 10) esté
      definido — es el lado frontend del mismo cambio de contrato de API.
    - _Requirements: 2.7_
    - _Design: "Impacto frontend — cambios concretos"_

---

## Task Dependency Graph

```
1. Exploratorios (Bug Condition)  ─┐
2. Preservación (baseline)        ─┤  (ambos ANTES del fix, sobre código sin arreglar)
                                    │
3. Escala pura (detectar/banda/normalizar) ──► 4. calcular_estado_cierre ──► 5. calcular_nota_final
                                                        │                          │
                                                        └──────────┬───────────────┘
                                                                   ▼
                                                     6. PBT de las funciones puras
7. examen_mapper (+valor_real)  ───────────────────────────────────────────┐
                                                                            ▼
8. Modelos + schemas ──► 9. Repository ──► 10. Router                       │
        │                                                                   │
        └──────────────────────────────┬────────────────────────────────────┘
                                        ▼
                        11. Service.generar (usa 4,5,7,8,9)
                        11.3 verifica Property 1 (necesita 4,5)
                        11.4 verifica Property 2 (necesita 7)
                                        │
                                        ▼
                        12. Excel (usa resultados_examenes/global_valor/nota_final de 8,11)
                                        │
                                        ▼
                        13. Migración Alembic (tras cerrar el shape en 8)
                                        │
                                        ▼
                        14. Tests de integración (usan 10,11,12,13)
                                        │
                                        ▼
                        15. Checkpoint backend (toda la suite pytest)

8. Modelos + schemas ──► 10. Router (contrato de API) ──► 16. Frontend (npm run build + lint)
        (cambio de contrato: generar sin umbral + sin endpoints /items)
```

**Orden crítico**: 1 y 2 primero (deben fallar/pasar sobre código sin arreglar). Núcleo puro
`3 → 4 → 5 → 6`. `7` (examen_mapper) es independiente del núcleo puro pero necesario para `11`.
El shape de datos `8 → 9 → 10` habilita `11`. `12` depende de los campos poblados por `8`/`11`.
`13` se genera una vez estabilizado el modelo (`8`). `14` cierra el flujo end-to-end. `15` valida
todo el backend junto. `16` (frontend) es el otro lado del **cambio de contrato de API**: depende
de que `8` (schemas) y `10` (router) hayan fijado el contrato nuevo (`generar` sin
`umbral_tp_pct`/`reglas`, sin endpoints `/items`); puede correr en paralelo al backend una vez
settleado ese contrato y se verifica con `npm run build` + `npm run lint`.

## Notas de alcance

- **Frontend afectado (regresión)**: existe la pantalla "Cierre de cursada" en
  `frontend/src/features/cierre-cursada/` (ruta `/cierre-cursada`) que consume los endpoints
  `/items` y el `umbral_tp_pct`/`reglas` que este fix elimina. La **tarea 16** la actualiza al
  contrato nuevo (borra el mapeo manual y el umbral, `generar` sólo con `cuatrimestre_id`) y la
  verifica con `npm run build` + `npm run lint`. Es el lado frontend del cambio de contrato de
  las tareas 8 y 10.
- **Máximo 500 LOC por archivo** (AGENTS.md): vigilado en `cierre_cursada_service.py` (tarea 11.2)
  y `excel_cierre_cursada.py` (tarea 12) — extraer helper si se supera.
- **Clean Architecture**: acceso a BD sólo vía repositorios; sin lógica de negocio en el router;
  funciones de cálculo puras y sin I/O en `cierre_cursada_calculo.py`. En frontend, TypeScript
  strict y estructura feature-folder (AGENTS.md).
- **Verificación de la entrega**: backend con `pytest` (tarea 15) y frontend con `npm run build`
  + `npm run lint` (tarea 16.7); ambas deben quedar en verde.
