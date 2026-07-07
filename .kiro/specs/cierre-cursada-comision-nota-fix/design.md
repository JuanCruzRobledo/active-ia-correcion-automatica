# Cierre de Cursada — Comisión y Nota Final Bugfix Design

## Overview

Este diseño ataca dos defectos independientes del cierre de cursada que degradan el reporte
generado (Excel + persistencia por alumno):

- **Bug 1 — Resolución de comisión.** `CierreCursadaService._resolver_comision` matchea el
  nombre del grupo de Moodle del alumno contra el campo manual `Comision.moodle_group_code`.
  Ese campo casi nunca está poblado (es un texto que hay que cargar a mano en el formulario de
  comisión), por lo que ningún alumno matchea y TODOS caen en "Sin comisión asignada". El fix
  reemplaza el puente frágil por el puente que YA funciona en el resto de la plataforma
  (`gestion_service`, `moodle_import_service`): el **id del grupo de Moodle**
  (`Comision.moodle_group_id` ↔ `group["id"]` del enrolled user), con un fallback por nombre de
  comisión derivado del grupo (`gestion_parser.parse_comision` → `Comision.nombre`).

- **Bug 2 — Nota Final "N/E".** `cierre_cursada_calculo.calcular_nota_final` devuelve `None`
  (que el Excel imprime como "N/E") ante cualquier examen principal sin nota numérica. El fix
  cambia el cálculo para que un examen no entregado cuente como **0** (y un examen en modo
  ESCALA cuente como 10 si está aprobado y 0 en cualquier otro caso), de modo que la Nota Final
  sea SIEMPRE un entero 0–10 cuando la materia tiene PARCIAL y GLOBAL configurados. La columna
  del examen en el Excel sigue mostrando "N/E"; sólo cambia el número que alimenta la Nota Final.

Ambos fixes son quirúrgicos: Bug 1 toca `CierreCursadaService._resolver_comision` (+ su
llamada) y Bug 2 toca `cierre_cursada_calculo.calcular_nota_final`. La lógica de clasificación
(PROMOCIONA/REGULARIZA/RECURSA) y el resto del pipeline de Moodle no cambian.

Tras completar Bug 1 y Bug 2, se sumaron dos ajustes de corrección del reporte que refinan la
salida del Excel de cierre (ambos también quirúrgicos):

- **Bug 3 — Orden de los bloques de comisión.** `excel_cierre_cursada._agrupar_por_comision`
  arma el dict de bloques en el orden de inserción de los alumnos (orden de llegada desde la
  inscripción de Moodle) y `_escribir_detalle` itera `.items()` en ese mismo orden, por lo que
  los bloques por comisión salen en un orden arbitrario. El fix ordena los BLOQUES
  ALFABÉTICAMENTE por nombre de comisión, forzando el bucket "Sin comisión asignada" al FINAL.
  Es un cambio de presentación puro: el orden de los alumnos DENTRO de cada bloque (por
  `(apellido, nombre)`) ya existe en `_escribir_detalle` y no cambia; el formato del encabezado
  "{comisión} — Tutor: {tutor}" tampoco cambia.

- **Bug 4 — Nota Final sólo para PROMOCIONA.** Tras el fix de Bug 2, `calcular_estado_cierre`
  devuelve `nota_final = calcular_nota_final(examenes)` para TODO alumno con PARCIAL+GLOBAL, sin
  importar el estado, de modo que REGULARIZA y RECURSA también obtienen un número. El fix acota
  esa regla: la Nota Final se completa SÓLO cuando `estado == "PROMOCIONA"`; para REGULARIZA y
  RECURSA `nota_final` pasa a ser `None` y el Excel debe renderizar la celda "Nota Final" en
  BLANCO (celda vacía), NUNCA "N/E". Esto revierte parcialmente la regla que instaló Bug 2 (que
  daba número a todos). La fórmula numérica de PROMOCIONA, el "N/E" de las columnas de examen y
  la clasificación de estado no cambian.

## Glossary

- **Bug_Condition (C)**: Condición que dispara cada bug. C1: un alumno pertenece a un grupo de
  comisión válido de Moodle pero queda "Sin comisión asignada". C2: un alumno tiene al menos un
  examen principal sin nota numérica y la Nota Final resulta "N/E".
- **Property (P)**: Comportamiento deseado. P1: el alumno queda asociado a su `Comision` real
  (`comision_id`, `comision_nombre`, `tutor_nombre`). P2: la Nota Final es un entero 0–10 que
  trata los no entregados como 0.
- **Preservation**: Comportamiento existente que no debe cambiar (comisión ambigua/sin grupo →
  "Sin comisión asignada"; columna del examen sigue mostrando "N/E"; fórmula ponderada para
  alumnos con todo numérico; 400 sin exámenes configurados; clasificación de estado).
- **`_resolver_comision`**: Método estático de `CierreCursadaService` que mapea los grupos de
  Moodle de un alumno a su registro `Comision` (`comision_id`, `comision_nombre`, `tutor_nombre`).
  Un alumno pertenece habitualmente a VARIOS grupos de Moodle a la vez; este método debe filtrar
  cuál(es) de esos grupos son de comisión.
- **Grupos múltiples / grupo de comisión**: En Moodle un alumno suele estar simultáneamente en
  más de un grupo — p. ej. su comisión real ("M26 C1-01"), un grupo regional ("R-Mendoza") y un
  grupo de TPI/trabajo ("Grupo_500"), además de cohortes u otros. Para el cierre SÓLO interesa el
  grupo de COMISIÓN; los demás (regional, TPI, cohortes, etc.) deben ignorarse. El formato de un
  grupo de comisión es el que reconoce `parse_comision` (`^[MA]\d+\s+C\d+-\d+$`); los grupos
  regional/TPI no matchean ese formato ni tienen `moodle_group_id` asociado a ninguna `Comision`,
  por lo que quedan naturalmente descartados.
- **`calcular_nota_final`**: Función PURA en `cierre_cursada_calculo.py` que pondera los exámenes
  principales del alumno (N parciales al 40 %, global al 60 %) y redondea con `round_half_up`.
- **`moodle_group_id`**: Columna de `Comision` con el id numérico del grupo de Moodle. Es el
  puente confiable (lo poblan/usan `moodle_import_service` y `gestion_service`).
- **`moodle_group_code`**: Columna de texto manual de `Comision`. Casi siempre vacía; es la causa
  raíz del Bug 1.
- **`parse_comision`**: Función pura de `gestion_parser` que, dado un nombre de grupo, devuelve el
  código de comisión (ej. "M26 C1-09") si matchea el formato `^[MA]\d+\s+C\d+-\d+$`, o `None`.
- **`resultado_escala`**: Resultado de un examen en modo ESCALA (`"aprobado"` / `"desaprobado"` /
  `"ausente"`), ya resuelto por `examen_mapper`.
- **`valor_real`**: Mejor nota numérica del examen (instancia base + rescates), o `None` si no se
  rindió / no tiene valor numérico.
- **Bug_Condition (C3)**: El Excel escribe los bloques por comisión en orden de inserción (llegada
  desde Moodle) y NO alfabéticamente, y/o el bloque "Sin comisión asignada" no queda al final.
- **Bug_Condition (C4)**: Un alumno con estado REGULARIZA o RECURSA (materia con PARCIAL+GLOBAL)
  obtiene una `nota_final` numérica y/o el Excel muestra algo distinto de una celda en blanco en
  "Nota Final".
- **`_agrupar_por_comision`**: Función de `excel_cierre_cursada.py` que agrupa los
  `CierreCursadaAlumno` por título de bloque (`"{comisión} — Tutor: {tutor}"`). Hoy devuelve un
  dict en orden de inserción; la causa raíz del Bug 3.
- **`_escribir_detalle`**: Función de `excel_cierre_cursada.py` que itera los bloques por comisión
  (en el orden que le da `_agrupar_por_comision`) y, DENTRO de cada bloque, ordena los alumnos por
  `(apellido, nombre)` — este orden intra-bloque ya existe y NO es un defecto.
- **`_fmt_nota_final`**: Formateador del Excel para la celda "Nota Final". Hoy devuelve "N/E" ante
  `None`; el fix de Bug 4 lo cambia para devolver blanco (`""`) ante `None`.
- **`_fmt_valor`**: Formateador del Excel para las columnas de examen (`Parcial n` / `Global TPI`).
  Devuelve "N/E" ante `None` y NO cambia (debe diverger de `_fmt_nota_final`).
- **`calcular_estado_cierre`**: Función PURA en `cierre_cursada_calculo.py` que arma el veredicto
  `{estado, resultados_examenes, global_valor, nota_final}`. El fix de Bug 4 gatea aquí la
  `nota_final` por estado.

## Bug Details

### Bug Condition

**Bug 1 — Resolución de comisión.** El bug se manifiesta cuando un alumno pertenece a un grupo de
Moodle con formato de comisión válido (ej. "M26 C1-09") y existe una `Comision` real de la materia
que le corresponde, pero `_resolver_comision` lo deja "Sin comisión asignada" porque sólo compara
el NOMBRE del grupo contra `Comision.moodle_group_code`, que está vacío o no coincide.

Un punto clave del contexto real: `u.get("groups")` trae VARIOS grupos por alumno a la vez (su
comisión más grupos regional, de TPI/trabajo, cohortes, etc.). La resolución debe FILTRAR sólo
el(los) grupo(s) que son de comisión y descartar el resto. El filtro se hace naturalmente por los
dos puentes válidos: `parse_comision` (que sólo matchea el formato `^[MA]\d+\s+C\d+-\d+$`, así que
ignora "R-*", "Grupo_NN", cohortes, etc.) y el `moodle_group_id` (que sólo está poblado en las
`Comision` de la materia, nunca en los grupos regional/TPI). Los grupos que no son de comisión no
producen match y por lo tanto no generan falsos positivos ni ambigüedad.

**Bug 2 — Nota Final "N/E".** El bug se manifiesta cuando un alumno tiene al menos un examen
principal (algún PARCIAL o el GLOBAL) sin nota numérica (no entregado, o en modo ESCALA sin valor),
y la materia tiene PARCIAL y GLOBAL configurados: `calcular_nota_final` retorna `None` en lugar de
un entero, propagando "N/E" a la Nota Final.

**Bug 3 — Orden de los bloques de comisión.** El bug se manifiesta cuando la materia tiene varias
comisiones: `_agrupar_por_comision` construye el dict de bloques en el orden en que los alumnos
llegan desde la inscripción de Moodle (orden de inserción del dict), y `_escribir_detalle` itera
`.items()` en ese mismo orden, por lo que los bloques salen desordenados y el bloque
"Sin comisión asignada" queda en la posición del primer alumno sin comisión en vez de al final.

**Bug 4 — Nota Final para no promocionados.** El bug se manifiesta cuando un alumno con estado
REGULARIZA o RECURSA tiene la materia con PARCIAL+GLOBAL configurados: `calcular_estado_cierre`
devuelve `nota_final = calcular_nota_final(examenes)` para TODOS los estados, y `_fmt_nota_final`
renderiza ese número (o "N/E" si fuese `None`) en la columna "Nota Final", en lugar de dejar la
celda en blanco para los no promocionados.

**Formal Specification:**

```
FUNCTION isBugCondition_comision(alumno, comisiones)
  INPUT: alumno con groups = [{id, name}, ...]  (VARIOS grupos: comisión + regional + TPI + ...),
         comisiones = [Comision, ...] de la materia
  OUTPUT: boolean

  # Sólo interesan los grupos que son de comisión. Un grupo cuenta si matchea una Comision
  # por moodle_group_id o por nombre derivado (parse_comision); los grupos regional/TPI/cohorte
  # no matchean y se descartan sin contarse.
  comisiones_matcheadas := { c IN comisiones :
        c.moodle_group_id IN {g.id FOR g IN alumno.groups}
        OR (EXISTS g IN alumno.groups WHERE parse_comision(g.name) CASEFOLD-EQ c.nombre) }
  existe_comision_real := |comisiones_matcheadas| == 1   # único grupo de comisión resuelto
  resuelto := _resolver_comision(alumno.groups, comisiones).comision_id IS NOT None

  RETURN existe_comision_real AND NOT resuelto
END FUNCTION


FUNCTION isBugCondition_nota_final(examenes)
  INPUT: examenes = lista de principales del alumno {tipo, modo_aprobacion, nota_minima,
                                                      valor_real, resultado_escala}
  OUTPUT: boolean

  tiene_parcial := COUNT(e IN examenes WHERE e.tipo == "PARCIAL") >= 1
  tiene_global  := COUNT(e IN examenes WHERE e.tipo == "GLOBAL") == 1
  algun_no_entregado := ANY e IN examenes WHERE valorParaNotaFinal(e) is derived from a
                        missing value (valor_real IS None, o ESCALA no aprobado)

  RETURN tiene_parcial AND tiene_global AND algun_no_entregado
         AND calcular_nota_final(examenes) IS None   # hoy devuelve None → "N/E"
END FUNCTION


FUNCTION isBugCondition_orden_bloques(alumnos)
  INPUT: alumnos = lista de CierreCursadaAlumno con comision_nombre / tutor_nombre
  OUTPUT: boolean

  bloques_actuales := _agrupar_por_comision(alumnos).keys()    # orden de inserción
  nombres := [nombre de comisión de cada bloque]               # sin el "— Tutor: ..."
  # orden esperado: comisiones reales alfabéticas + "Sin comisión asignada" al final
  bloques_esperados := SORT(nombres_reales, casefold) ++ ["Sin comisión asignada" if existe]

  RETURN existen >= 2 bloques
         AND bloques_actuales != bloques_esperados   # hoy: orden de llegada, no alfabético
END FUNCTION


FUNCTION isBugCondition_nota_no_promociona(alumno)
  INPUT: alumno con estado en {PROMOCIONA, REGULARIZA, RECURSA} y nota_final
  OUTPUT: boolean

  RETURN alumno.estado IN {"REGULARIZA", "RECURSA"}
         AND alumno.nota_final IS NOT None   # hoy: número también para no promocionados
END FUNCTION
```

### Examples

**Bug 1:**
- Alumno en grupo "M26 C1-09" (id 342), materia con `Comision(nombre="M26 C1-09",
  moodle_group_id=342, moodle_group_code=NULL)`. Esperado: `comision_id=<esa comisión>`,
  `tutor_nombre` de sus tutores. Actual: "Sin comisión asignada" (porque `moodle_group_code` es
  NULL).
- **Multi-grupo (caso real).** Alumno con `groups = [{"id":342,"name":"M26 C1-01"},
  {"id":501,"name":"R-Mendoza"}, {"id":777,"name":"Grupo_500"}]` — pertenece a la vez a su comisión,
  a la regional y a un grupo de TPI. Materia con `Comision(nombre="M26 C1-01", moodle_group_id=342)`
  y sin ninguna `Comision` con `moodle_group_id` 501 o 777. Esperado: resuelve la comisión
  "M26 C1-01" (por id 342 y/o por nombre) e IGNORA "R-Mendoza" y "Grupo_500" (no matchean
  `parse_comision` ni ningún `moodle_group_id`). No hay ambigüedad: sólo un grupo es de comisión.
  Actual: "Sin comisión asignada".
- Materia con 5 comisiones, ninguna con `moodle_group_code` cargado. Esperado: cada alumno a su
  comisión. Actual: TODOS "Sin comisión asignada".

**Bug 2:**
- P1 = 93 (escala 100 → 9.3), P2 = N/E (→ 0), Global = N/E (→ 0). Esperado: Nota Final =
  `round_half_up(((9.3 + 0) / 2) * 0.4 + 0 * 0.6)` = `round_half_up(1.86)` = **2**. Actual: "N/E".
- Parcial en modo ESCALA aprobado + Global = 9.0. Esperado: `round_half_up(10*0.4 + 9*0.6)` =
  `round_half_up(9.4)` = **9**. Actual: "N/E".
- Alumno que no entregó ningún examen (materia con PARCIAL/GLOBAL configurados). Esperado: Nota
  Final = **0**. Actual: "N/E".
- Edge: materia SIN GLOBAL configurado (sólo parciales). Fuera del alcance de la garantía numérica
  (Req 2.6 exige PARCIAL **y** GLOBAL) → `calcular_nota_final` mantiene su guard y devuelve `None`.

**Bug 3:**
- Alumnos que llegan de Moodle en el orden de comisiones "M26 C1-03", "M26 C1-01", "M26 C1-02".
  Esperado: bloques en el orden "M26 C1-01", "M26 C1-02", "M26 C1-03". Actual: "M26 C1-03",
  "M26 C1-01", "M26 C1-02" (orden de llegada).
- Materia con dos comisiones y alumnos sin comisión, donde el primer alumno sin comisión llega
  antes que los de "M26 C1-02". Esperado: "M26 C1-01", "M26 C1-02", "Sin comisión asignada" (al
  final). Actual: "Sin comisión asignada" queda en el medio o al principio, según la llegada.
- Edge: una sola comisión (con o sin bloque "Sin comisión asignada") → el orden ya es correcto;
  el fix no lo altera. Si sólo hay "Sin comisión asignada", queda como único bloque.

**Bug 4:**
- Alumno REGULARIZA con Parcial=8, Global=5 (todos numéricos). Hoy: `nota_final` numérica (ej. 6)
  y el Excel la muestra. Esperado: `nota_final = None` y celda "Nota Final" en BLANCO.
- Alumno RECURSA con exámenes no entregados. Hoy: `nota_final = 0` y el Excel muestra 0. Esperado:
  `nota_final = None` y celda "Nota Final" en BLANCO.
- Alumno PROMOCIONA con Parcial=9, Global=9. Esperado (sin cambios): `nota_final` numérica (ej. 9)
  mostrada en el Excel. Las columnas de examen no entregado siguen mostrando "N/E".

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Un alumno SIN grupo de comisión válido de Moodle debe seguir clasificándose como "Sin comisión
  asignada" sin interrumpir la generación del cierre (3.1).
- Un alumno con match ambiguo debe seguir quedando "Sin comisión asignada" sin romper la corrida
  del resto de alumnos (3.2). La ambigüedad se mide SÓLO sobre las `Comision` DISTINTAS
  efectivamente matcheadas (por `moodle_group_id` o por nombre derivado): 0 comisiones o >1
  comisiones distintas → "Sin comisión asignada". Pertenecer además a grupos regional ("R-*"),
  de TPI ("Grupo_NN"), cohortes u otros NO cuenta como ambigüedad, porque esos grupos no matchean
  ninguna `Comision`. El caso >1 (raro) es un alumno que aparece en dos grupos de comisión
  distintos a la vez.
- La columna del examen (Parcial n / Global TPI) del Excel debe seguir mostrando "N/E" cuando el
  examen no se entregó — sólo cambia el cálculo de la Nota Final (3.3).
- Un alumno con TODOS sus exámenes numéricos debe conservar exactamente la fórmula ponderada
  actual (promedio de parciales normalizados a 0–10 al 40 %, global normalizado a 0–10 al 60 %,
  `round_half_up`) (3.4).
- Una materia sin exámenes PARCIAL/GLOBAL configurados debe seguir bloqueando el cierre con 400
  (3.5).
- La clasificación PROMOCIONA / REGULARIZA / RECURSA (`cumple_minimo`/`cumple_banda`) no cambia:
  un examen no entregado sigue contando como incumplimiento, independientemente del nuevo cálculo
  de la Nota Final (3.6).
- El orden de los alumnos DENTRO de cada bloque de comisión debe seguir siendo alfabético por
  `(apellido, nombre)` como hoy (ya existe en `_escribir_detalle`, no es defecto) (3.7).
- El encabezado de cada bloque debe seguir usando el formato "{comisión} — Tutor: {tutor}" sin
  cambios (3.8).
- Un alumno PROMOCIONA debe conservar su Nota Final numérica ponderada (parciales normalizados al
  40 %, global al 60 %, `round_half_up`, no entregados como 0), idéntica al fix de Bug 2 (3.9).
- La columna del examen (Parcial n / Global TPI) debe seguir mostrando "N/E" cuando el examen no
  se entregó: el cambio de Bug 4 afecta ÚNICAMENTE a la columna "Nota Final" (`_fmt_nota_final`),
  no a `_fmt_valor` (3.10).
- La lógica de clasificación de estado no cambia con Bug 4; sólo cambia para qué estados se
  completa la Nota Final (3.11).

**Scope:**
Los inputs que NO disparan cada bug deben quedar completamente inalterados:
- Alumnos sin grupo de comisión válido, o con match ambiguo (Bug 1).
- Alumnos con todos los exámenes numéricos, y materias sin la forma PARCIAL+GLOBAL (Bug 2).
- El orden intra-bloque de alumnos y el formato del encabezado de bloque (Bug 3).
- Los alumnos PROMOCIONA (su Nota Final numérica) y las columnas de examen "N/E" (Bug 4).
- El árbol de decisión del estado, el pipeline de descarga de Moodle, el histórico append-only y
  los estilos del Excel.

**Note:** El comportamiento correcto esperado ante cada condición de bug se define en las
Correctness Properties (Property 1 y 2 para Bug 1/2; Property 5 y 6 para Bug 3/4). Esta sección
enfoca lo que NO debe cambiar.

## Hypothesized Root Cause

**Bug 1 — Resolución de comisión:**

1. **Puente incorrecto (causa raíz principal)**: `_resolver_comision` usa
   `Comision.moodle_group_code` (texto manual, casi siempre NULL) como única llave de match. El
   resto de la plataforma usa `Comision.moodle_group_id` ↔ `group["id"]` del enrolled user
   (`gestion_service.exportar_pendientes_excel`, `moodle_import_service`), que SÍ está poblado.

2. **Se descarta el id del grupo**: `generar` construye `grupos = [g.get("name") ...]` y descarta
   `g.get("id")` antes de llamar a `_resolver_comision`, imposibilitando el match por id.

3. **No se deriva la comisión del nombre**: A diferencia de `snapshot_service`/`gestion_service`
   (que usan `parse_comision`), el cierre no deriva el código de comisión del nombre del grupo, así
   que depende 100 % de la config manual.

**Bug 2 — Nota Final "N/E":**

1. **Tratamiento de faltantes como "incalculable"**: `calcular_nota_final` retorna `None` apenas
   algún parcial o el global no tiene nota numérica (`any(v is None ...) or global_norm is None`),
   en vez de tratar el faltante como 0.

2. **ESCALA sin mapeo numérico**: los exámenes en modo ESCALA no tienen `valor_real`, por lo que
   `normalizar_a_10` devuelve `None` y arrastran la Nota Final a "N/E", en vez de mapear
   aprobado→10 / resto→0.

**Bug 3 — Orden de los bloques de comisión:**

1. **Orden de inserción del dict (causa raíz principal)**: `_agrupar_por_comision` usa
   `grupos.setdefault(titulo, []).append(a)`, por lo que las CLAVES del dict quedan en el orden en
   que aparece el primer alumno de cada comisión (orden de llegada desde Moodle). `_escribir_detalle`
   itera `.items()` en ese orden, así que los bloques salen sin ordenar.

2. **"Sin comisión asignada" sin tratamiento especial**: al no distinguirse ese bucket, queda
   intercalado en la posición de su primer alumno en lugar de al final.

3. **La clave del dict es el título compuesto**: el dict se indexa por
   `"{comisión} — Tutor: {tutor}"`, no por el nombre de comisión, así que ordenar por la clave
   compuesta no sería robusto — el sort debe usar el nombre de comisión subyacente (o detectar el
   bucket "Sin comisión asignada").

**Bug 4 — Nota Final para no promocionados:**

1. **`nota_final` sin condicionar al estado (causa raíz principal)**: tras el fix de Bug 2,
   `calcular_estado_cierre` arma el veredicto con `"nota_final": calcular_nota_final(examenes)`
   para TODO alumno, sin mirar `estado`. La regla de negocio "sólo PROMOCIONA tiene Nota Final" no
   está codificada en ninguna parte.

2. **`_fmt_nota_final` renderiza "N/E" ante `None`**: aunque se persistiera `nota_final = None`
   para los no promocionados, el Excel hoy mostraría "N/E" (mismo formateo que las columnas de
   examen) en vez de una celda en blanco.

## Correctness Properties

Property 1: Bug Condition - Resolución de comisión por grupo de Moodle

_For any_ alumno cuyo conjunto de grupos de Moodle (que puede incluir VARIOS grupos: comisión,
regional, TPI, cohortes, etc.) contiene exactamente un grupo que corresponde a una `Comision` real
de la materia (por `moodle_group_id` igual al `id` del grupo, o por nombre de comisión derivado del
grupo con `parse_comision` igual, case-insensitive, a `Comision.nombre`), `_resolver_comision` SHALL
devolver el `comision_id`, `comision_nombre` y `tutor_nombre` de esa `Comision` real, IGNORANDO los
grupos que no son de comisión (regional "R-*", TPI "Grupo_NN", cohortes, etc., que no matchean
`parse_comision` ni ningún `moodle_group_id`), y sin depender de que `Comision.moodle_group_code`
esté configurado manualmente.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition - Nota Final numérica tratando no entregados como 0

_For any_ lista de exámenes principales de un alumno con al menos un PARCIAL y exactamente un
GLOBAL, `calcular_nota_final` SHALL devolver un entero 0–10 (nunca `None`), computando cada examen
como: su valor normalizado a 0–10 si tiene nota numérica; 10 si es modo ESCALA aprobado; y 0 si no
fue entregado o es ESCALA no aprobado; ponderando el promedio de los parciales al 40 % y el global
al 60 % con `round_half_up`. En particular, P1=9.3 / P2=0 / Global=0 ⇒ Nota Final = 2.

**Validates: Requirements 2.3, 2.4, 2.5, 2.6**

Property 3: Preservation - Sin grupo válido o match ambiguo → sin comisión

_For any_ alumno cuyos grupos no corresponden a ninguna `Comision` de la materia (0 comisiones
matcheadas — aunque el alumno esté en grupos regional/TPI/cohorte), o corresponden a más de una
`Comision` DISTINTA (match ambiguo: el alumno está en dos grupos de comisión distintos a la vez),
`_resolver_comision` SHALL devolver `(None, "Sin comisión asignada", None)` sin lanzar excepción ni
interrumpir la generación del cierre para el resto de los alumnos. La pertenencia a grupos que no
son de comisión NO cuenta para esta ambigüedad, ya que no matchean ninguna `Comision`.

**Validates: Requirements 3.1, 3.2**

Property 4: Preservation - Columna N/E, fórmula numérica completa, 400 y estado

_For any_ input donde no se dispara el Bug 2, el sistema SHALL conservar el comportamiento
original: la columna del examen en el Excel muestra "N/E" cuando `valor_real`/`global_valor` es
`None`; un alumno con TODOS los exámenes numéricos obtiene la misma Nota Final ponderada que hoy;
una materia sin exámenes configurados sigue produciendo un 400; y la clasificación
PROMOCIONA/REGULARIZA/RECURSA es idéntica a la actual.

**Validates: Requirements 3.3, 3.4, 3.5, 3.6**

Property 5: Bug Condition - Bloques de comisión ordenados alfabéticamente

_For any_ conjunto de alumnos repartidos en varias comisiones, el Excel de cierre SHALL escribir
los bloques por comisión ordenados ALFABÉTICAMENTE (case-insensitive) por nombre de comisión, con
el bloque "Sin comisión asignada" SIEMPRE al final, después de todas las comisiones reales. El
orden de los alumnos DENTRO de cada bloque permanece alfabético por `(apellido, nombre)` y el
formato del encabezado "{comisión} — Tutor: {tutor}" no cambia.

**Validates: Requirements 2.7, 2.8** (preserva 3.7, 3.8)

Property 6: Bug Condition - Nota Final sólo para PROMOCIONA

_For any_ alumno de una materia con PARCIAL+GLOBAL configurados, `nota_final` SHALL ser un entero
0–10 si y sólo si `estado == "PROMOCIONA"`, y `None` en cualquier otro estado (REGULARIZA /
RECURSA); en consecuencia, el Excel SHALL renderizar la celda "Nota Final" en BLANCO (celda vacía)
para los no promocionados, NUNCA "N/E". La fórmula numérica para PROMOCIONA, el "N/E" de las
columnas de examen (`_fmt_valor`) y la clasificación de estado no cambian.

**Validates: Requirements 2.9, 2.10** (preserva 3.9, 3.10, 3.11)

> **Nota (Bug 4 revierte una regla del fix de Bug 2):** Property 2 estableció que TODO alumno con
> PARCIAL+GLOBAL obtiene Nota Final numérica. Property 6 acota esa regla a PROMOCIONA. El test
> existente `test_regulariza_con_global_numerico_tiene_nota_final_numerica` codifica la regla
> anterior y DEBE actualizarse para esperar `nota_final = None` en un alumno REGULARIZA.

## Fix Implementation

### Bug 1 — Resolución de comisión

**File**: `backend/app/services/cierre_cursada_service.py`

**Function**: `_resolver_comision` (+ su invocación en `generar`)

**Specific Changes**:

1. **Cambiar la firma para recibir los grupos completos**: `_resolver_comision(grupos, comisiones)`
   pasa a recibir `grupos` como la lista de dicts de Moodle (`[{"id", "name"}, ...]`), no sólo los
   nombres, para poder usar el `id`. En `generar`, en lugar de
   `grupos = [g.get("name") for g in ...]`, pasar los grupos crudos:
   `self._resolver_comision(u.get("groups") or [], comisiones)`. **`u.get("groups")` trae VARIOS
   grupos por alumno** (comisión + regional + TPI + cohortes...), así que la función debe iterar
   todos y FILTRAR sólo los que son de comisión.

2. **Bridge primario por `moodle_group_id`** (mismo puente que `gestion_service`/
   `moodle_import_service`): construir `por_group_id = {c.moodle_group_id: c for c in comisiones
   if c.moodle_group_id}` y matchear cada `g["id"]` del alumno contra ese mapa. Iterar TODOS los
   grupos del alumno es seguro: los grupos regional/TPI no tienen `moodle_group_id` en ninguna
   `Comision`, así que simplemente no matchean y se descartan sin generar falsos positivos.

3. **Fallback por nombre derivado (filtro natural del grupo de comisión)**: para grupos cuyo
   `g["name"]` matchea `parse_comision` (regex `^[MA]\d+\s+C\d+-\d+$`), matchear el código de
   comisión resultante (case-insensitive) contra `Comision.nombre` (y, opcionalmente, contra
   `moodle_group_code` para compatibilidad con configs viejas). `parse_comision` es justamente lo
   que separa el grupo de comisión del resto: devuelve `None` para "R-Mendoza", "Grupo_500",
   cohortes, etc., por lo que esos grupos quedan fuera del match automáticamente.

4. **Resolución de unicidad (preservación 3.1/3.2)**: juntar el conjunto de `Comision` DISTINTAS
   efectivamente matcheadas por cualquiera de los dos puentes a través de todos los grupos del
   alumno. Si hay exactamente una → devolver `(c.id, c.nombre, tutor_nombre)`. Si hay cero
   (ningún grupo de comisión, aunque el alumno esté en regional/TPI) o más de una (dos grupos de
   comisión distintos, caso raro/ambiguo) → `(None, "Sin comisión asignada", None)`. Pertenecer a
   grupos que no son de comisión NO cuenta para la unicidad, porque no aportan comisiones al
   conjunto.

5. **Tutor**: mantener `" / ".join(ct.tutor.nombre for ct in comision.tutores) or None`.

Bosquejo:

```
@staticmethod
def _resolver_comision(grupos, comisiones):
    # `grupos` trae VARIOS grupos del alumno (comisión + regional + TPI + cohortes...).
    # Iteramos todos y nos quedamos SÓLO con los que matchean una Comision de la materia;
    # los grupos que no son de comisión (R-*, Grupo_NN, cohortes) no matchean y se descartan.
    por_group_id = {c.moodle_group_id: c for c in comisiones if c.moodle_group_id}
    por_nombre = {c.nombre.strip().casefold(): c for c in comisiones}
    encontradas = set()  # ids de Comision distintas efectivamente matcheadas
    matched = {}
    for g in grupos:
        gid = g.get("id")
        if gid in por_group_id:          # match por id (regional/TPI no tienen id de comisión)
            c = por_group_id[gid]; matched[c.id] = c; encontradas.add(c.id); continue
        codigo = parse_comision(g.get("name") or "")  # None para R-*, Grupo_NN, cohortes...
        if codigo:
            c = por_nombre.get(codigo.strip().casefold())
            if c: matched[c.id] = c; encontradas.add(c.id)
    # 0 comisiones (aunque esté en regional/TPI) o >1 (dos comisiones distintas) → sin comisión.
    if len(encontradas) != 1:
        return None, "Sin comisión asignada", None
    comision = matched[next(iter(encontradas))]
    tutor_nombre = " / ".join(ct.tutor.nombre for ct in comision.tutores) or None
    return comision.id, comision.nombre, tutor_nombre
```

(Importar `parse_comision` desde `app.services.gestion_parser`.)

### Bug 2 — Nota Final con no entregados como 0

**File**: `backend/app/services/cierre_cursada_calculo.py`

**Function**: `calcular_nota_final`

**Specific Changes**:

1. **Guard estructural (sin cambio)**: mantener `if len(parciales) == 0 or len(globales) != 1:
   return None`. Es la forma de config que NO cubre la garantía numérica (Req 2.6 la condiciona a
   tener PARCIAL **y** GLOBAL); coincide con el 400 upstream (preservación 3.5).

2. **Helper `_valor_para_nota_final(examen) -> float`**: devuelve SIEMPRE un número:
   - modo ESCALA → `10.0` si `resultado_escala == "aprobado"`, si no `0.0` (Req 2.4).
   - modo NUMERICO → `normalizar_a_10(valor_real, nota_minima)`; si es `None` (no entregado) → `0.0`.

3. **Cálculo sin cortar por `None`**: reemplazar
   `if any(v is None ...) or global_norm is None: return None` por el uso del helper, de modo que
   los faltantes cuenten como 0 y la función siempre retorne un `int` (Req 2.3, 2.5, 2.6).

4. **Reutilizar** `normalizar_a_10` y `round_half_up` (sin cambios): preserva la fórmula ponderada
   para alumnos con todo numérico (3.4) y la normalización de escalas mixtas.

Bosquejo:

```
def _valor_para_nota_final(examen):
    if examen.get("modo_aprobacion") == "ESCALA":
        return 10.0 if examen.get("resultado_escala") == "aprobado" else 0.0
    norm = normalizar_a_10(examen.get("valor_real"), examen.get("nota_minima"))
    return norm if norm is not None else 0.0

def calcular_nota_final(examenes):
    parciales = [e for e in examenes if e.get("tipo") == "PARCIAL"]
    globales  = [e for e in examenes if e.get("tipo") == "GLOBAL"]
    if len(parciales) == 0 or len(globales) != 1:
        return None
    parciales_vals = [_valor_para_nota_final(e) for e in parciales]
    global_val = _valor_para_nota_final(globales[0])
    promedio = sum(parciales_vals) / len(parciales_vals)
    return round_half_up(promedio * 0.4 + global_val * 0.6)
```

5. **`calcular_estado_cierre`**: sin cambios por Bug 2 (ver el ajuste de Bug 4 más abajo). Sigue
   llamando `calcular_nota_final(examenes)`; la clasificación (`cumple_minimo`/`cumple_banda`) es
   independiente y no se toca (preservación 3.6). `global_valor` sigue siendo `max_o_none(...)` →
   `None` cuando no se rindió → Excel muestra "N/E" en la columna Global (3.3). `_valor_parcial`
   en el Excel sigue leyendo `valor_real` → "N/E" en la columna del parcial (3.3).

### Bug 3 — Bloques de comisión ordenados alfabéticamente

**File**: `backend/app/services/excel_cierre_cursada.py`

**Function**: `_agrupar_por_comision` (+ su consumo en `_escribir_detalle`)

**Specific Changes**:

1. **Ordenar los bloques por nombre de comisión, no por título compuesto**: el sort debe usar el
   nombre de comisión subyacente (`comision_nombre`), no la clave compuesta
   `"{comisión} — Tutor: {tutor}"`, para ser robusto. Clave de orden que fuerza
   "Sin comisión asignada" al final: `(1, "")` para el bucket sin comisión y
   `(0, comision_nombre.casefold())` para las comisiones reales.

2. **Mantener el mapeo título → alumnos**: `_agrupar_por_comision` sigue devolviendo el mapping
   `{titulo_bloque: [alumnos]}`, pero ahora ORDENADO. Como el título incluye el tutor, hay que
   conservar, por cada bloque, tanto el `comision_nombre` (para ordenar y detectar "Sin comisión
   asignada") como el título compuesto (para el encabezado). Un enfoque limpio es que
   `_agrupar_por_comision` agrupe por `comision_nombre` y construya el resultado ordenado, y que la
   barra de bloque siga formándose con `"{comisión} — Tutor: {tutor}"`.

3. **Detección del bucket sin comisión**: identificar "Sin comisión asignada" por el
   `comision_nombre` (que es `None` en el alumno y se normaliza a "Sin comisión asignada"), NO por
   substring del título compuesto.

4. **Sin cambios de cálculo ni de estilo**: el orden intra-bloque por `(apellido, nombre)` en
   `_escribir_detalle` (3.7) y el formato del encabezado (3.8) quedan intactos.

Bosquejo (ordenando el agrupamiento, preservando el título con tutor):

```
_SIN_COMISION = "Sin comisión asignada"

def _agrupar_por_comision(alumnos):
    # Agrupa por (nombre_comision, titulo_compuesto) preservando el tutor en el título.
    grupos: dict[str, tuple[str, list]] = {}   # nombre_comision -> (titulo, [alumnos])
    for a in alumnos:
        nombre = a.comision_nombre or _SIN_COMISION
        titulo = f"{nombre} — Tutor: {a.tutor_nombre}" if a.tutor_nombre else nombre
        grupos.setdefault(nombre, (titulo, []))[1].append(a)

    def clave(item):
        nombre = item[0]
        es_sin = nombre == _SIN_COMISION
        return (1, "") if es_sin else (0, nombre.casefold())

    # Devuelve dict ordenado {titulo: [alumnos]} — "Sin comisión asignada" al final.
    return {
        titulo: alumnos
        for _, (titulo, alumnos) in sorted(grupos.items(), key=clave)
    }
```

`_escribir_detalle` no cambia: sigue iterando `_agrupar_por_comision(alumnos).items()`, pero ahora
recibe los bloques ya ordenados. (Dict de Python preserva el orden de inserción, así que iterar el
dict ordenado respeta el orden alfabético con "Sin comisión asignada" al final.)

### Bug 4 — Nota Final sólo para PROMOCIONA

**Files**: `backend/app/services/cierre_cursada_calculo.py` y
`backend/app/services/excel_cierre_cursada.py`

**Decisión de diseño (Opción A, recomendada):** gatear la `nota_final` por estado dentro de
`calcular_estado_cierre` (el constructor del veredicto), NO dentro de `calcular_nota_final`.

- **Opción A (elegida)**: en `calcular_estado_cierre`, incluir la nota numérica sólo cuando
  `estado == "PROMOCIONA"`; en cualquier otro caso, `nota_final = None`. Mantiene
  `calcular_nota_final` PURA y reutilizable (sigue calculando el número para cualquier lista de
  exámenes) y centraliza la regla de negocio "sólo promociona" en el único lugar que ya conoce el
  estado. El service (`generar`) no cambia: sigue persistiendo `veredicto["nota_final"]`.
- **Opción B (descartada)**: gatear en `generar` al construir `CierreCursadaAlumno`. Se descarta
  porque dispersa la regla de negocio en la capa de orquestación y deja `calcular_estado_cierre`
  devolviendo un `nota_final` que el service tendría que "corregir".

**Change 1 — `cierre_cursada_calculo.calcular_estado_cierre`**:

```
if promociona:
    estado = "PROMOCIONA"
elif regulariza:
    estado = "REGULARIZA"
else:
    estado = "RECURSA"
...
return {
    "estado": estado,
    "resultados_examenes": resultados_examenes,
    "global_valor": global_valor,
    # Bug 4: la Nota Final se completa SÓLO para PROMOCIONA; None para REGULARIZA/RECURSA.
    "nota_final": calcular_nota_final(examenes) if estado == "PROMOCIONA" else None,
}
```

`calcular_nota_final` y el helper `_valor_para_nota_final` NO cambian (siguen puros; se usan tal
cual para PROMOCIONA) → preserva 3.9. La clasificación de estado tampoco cambia → preserva 3.11.

**Change 2 — `excel_cierre_cursada._fmt_nota_final`**: cambiar el render de `None` de "N/E" a
BLANCO (celda vacía). `_fmt_valor` (columnas de examen) NO cambia y sigue devolviendo "N/E" →
preserva 3.10. Ambos formateadores DIVERGEN: sólo `_fmt_nota_final` pasa a blanco-en-`None`.

```
def _fmt_nota_final(valor: int | None) -> str | int:
    return "" if valor is None else valor   # Bug 4: celda en blanco, no "N/E"

def _fmt_valor(valor):                        # sin cambios
    return "N/E" if valor is None else valor
```

## Testing Strategy

### Validation Approach

Enfoque en dos fases: primero exponer contraejemplos que demuestren cada bug sobre el código sin
arreglar, y luego verificar que el fix funciona y preserva el comportamiento existente. El grueso
de la validación es sobre las funciones PURAS (`calcular_nota_final`) y el helper puro
(`_resolver_comision`), que es donde vive la lógica que puede calcularse mal.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples que demuestren cada bug ANTES de implementar el fix; confirmar o
refutar el análisis de causa raíz. Si se refuta, re-hipotetizar.

**Test Plan**: Ejercitar los helpers puros con inputs que disparan cada condición de bug y observar
el resultado defectuoso sobre el código actual.

**Test Cases**:
1. **Comisión por group_id (Bug 1)**: `_resolver_comision` con un grupo `{"id":342,"name":"M26 C1-09"}`
   y una `Comision(moodle_group_id=342, moodle_group_code=None)` → hoy devuelve
   "Sin comisión asignada" (fallará hasta el fix).
2. **Comisión por nombre derivado (Bug 1)**: grupo `{"id":None,"name":"M26 C1-09"}` y
   `Comision(nombre="M26 C1-09", moodle_group_code=None)` → hoy "Sin comisión asignada".
2b. **Multi-grupo (Bug 1)**: alumno con `groups = [{"id":342,"name":"M26 C1-01"},
   {"id":501,"name":"R-Mendoza"}, {"id":777,"name":"Grupo_500"}]` y sólo
   `Comision(nombre="M26 C1-01", moodle_group_id=342)` en la materia → esperado: resuelve
   "M26 C1-01" ignorando los otros dos grupos; hoy "Sin comisión asignada" (fallará hasta el fix).
3. **Nota Final con parcial N/E (Bug 2)**: P1=93 (nota_minima 60), P2=None, Global=None → hoy
   `None`; esperado 2.
4. **Nota Final con ESCALA aprobado (Bug 2)**: parcial ESCALA aprobado + Global 9.0 → hoy `None`;
   esperado 9.
5. **Edge — sin ningún examen entregado (Bug 2)**: parciales y global todos `None` → hoy `None`;
   esperado 0.
6. **Orden de bloques (Bug 3)**: alumnos que llegan en comisiones "M26 C1-03", "M26 C1-01",
   "M26 C1-02" → hoy `_agrupar_por_comision` devuelve las claves en ese orden de llegada; esperado
   "M26 C1-01", "M26 C1-02", "M26 C1-03".
7. **"Sin comisión" al final (Bug 3)**: alumnos donde el primero no tiene comisión → hoy el bloque
   "Sin comisión asignada" queda primero; esperado, al final.
8. **Nota Final de REGULARIZA (Bug 4)**: alumno REGULARIZA con exámenes numéricos → hoy
   `calcular_estado_cierre(...)["nota_final"]` es un entero; esperado `None`.
9. **Nota Final de RECURSA (Bug 4)**: alumno RECURSA → hoy `nota_final` numérica (0 o más);
   esperado `None` y celda del Excel en blanco.

**Expected Counterexamples**:
- `_resolver_comision` devuelve `(None, "Sin comisión asignada", None)` pese a existir la comisión.
- `calcular_nota_final` devuelve `None` (→ "N/E") ante cualquier faltante.
- `_agrupar_por_comision` devuelve las claves en orden de llegada, no alfabético.
- `calcular_estado_cierre` devuelve `nota_final` numérica para REGULARIZA/RECURSA.
- Causas probables confirmadas: puente por `moodle_group_code` (Bug 1); corte por `None` (Bug 2);
  orden de inserción del dict (Bug 3); `nota_final` sin condicionar al estado (Bug 4).

### Fix Checking

**Goal**: Verificar que para todo input donde vale la condición de bug, la función arreglada
produce el comportamiento esperado.

**Pseudocode:**
```
FOR ALL alumno WHERE isBugCondition_comision(alumno, comisiones) DO
  cid, nombre, tutor := _resolver_comision(alumno.groups, comisiones)
  ASSERT cid IS NOT None AND nombre == comision_real.nombre
END FOR

FOR ALL examenes WHERE isBugCondition_nota_final(examenes) DO
  nf := calcular_nota_final(examenes)
  ASSERT nf IS integer AND 0 <= nf <= 10
END FOR

FOR ALL alumnos WHERE isBugCondition_orden_bloques(alumnos) DO
  bloques := keys(_agrupar_por_comision(alumnos))
  nombres := [nombre de comisión de cada bloque]
  ASSERT nombres == SORT(nombres_reales, casefold) ++ ["Sin comisión asignada" if existe]
END FOR

FOR ALL alumno WHERE isBugCondition_nota_no_promociona(alumno) DO
  veredicto := calcular_estado_cierre(alumno.examenes)
  ASSERT veredicto["nota_final"] IS None          # REGULARIZA / RECURSA
  ASSERT _fmt_nota_final(None) == ""               # celda en blanco, no "N/E"
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todo input donde NO vale la condición de bug, la función arreglada
produce el mismo resultado que la original.

**Pseudocode:**
```
FOR ALL alumno WHERE NOT isBugCondition_comision(alumno, comisiones) DO
  ASSERT _resolver_comision_fixed(alumno.groups, comisiones)
       == (None, "Sin comisión asignada", None)   # sin grupo válido / ambiguo
END FOR

FOR ALL examenes WHERE NOT isBugCondition_nota_final(examenes) DO
  ASSERT calcular_nota_final_fixed(examenes) == calcular_nota_final_original(examenes)
END FOR

# Bug 3: dentro de cada bloque el orden de alumnos no cambia; el encabezado no cambia.
FOR ALL alumnos DO
  FOR ALL bloque IN _agrupar_por_comision(alumnos) DO
    ASSERT orden_alumnos(bloque) == SORT(bloque.alumnos, key=(apellido, nombre))
    ASSERT encabezado(bloque) == "{comisión} — Tutor: {tutor}"
  END FOR
END FOR

# Bug 4: PROMOCIONA conserva su nota; las columnas de examen siguen en "N/E".
FOR ALL alumno WHERE alumno.estado == "PROMOCIONA" DO
  ASSERT calcular_estado_cierre_fixed(...)["nota_final"]
       == calcular_estado_cierre_original(...)["nota_final"]
END FOR
ASSERT _fmt_valor(None) == "N/E"   # columnas de examen sin cambios
```

**Testing Approach**: Se recomienda property-based testing para la preservación de la Nota Final:
genera muchos casos con todos los exámenes numéricos y compara el fix contra la fórmula ponderada
esperada; cubre bordes de redondeo y escalas mixtas que los tests manuales podrían perder.

**Test Plan**: Observar el comportamiento del código SIN arreglar para inputs no-bug (comisión
ambigua/sin grupo, todo numérico, sin global configurado, sin exámenes) y escribir tests que lo
capturen.

**Test Cases**:
1. **Comisión ambigua (3.2)**: alumno en dos grupos de comisión distintos a la vez (matchea dos
   `Comision`) → "Sin comisión asignada".
2. **Sin grupo de comisión (3.1)**: alumno sólo en grupos regional/TPI/cohorte ("R-Mendoza",
   "Grupo_500", ...) que no matchean ninguna comisión → "Sin comisión asignada" (pertenecer a esos
   grupos no cuenta como match ni como ambigüedad).
3. **Todo numérico (3.4)**: parciales + global numéricos → misma Nota Final que la fórmula actual.
4. **Sin global configurado (edge/3.5-scope)**: 0 globales o ≠1 → `calcular_nota_final` sigue
   devolviendo `None` (fuera del alcance de Req 2.6).
5. **Columna N/E (3.3)**: examen no entregado → el Excel sigue imprimiendo "N/E" en su columna,
   aunque la Nota Final ahora sea numérica.
6. **Estado sin cambios (3.6)**: un examen no entregado sigue produciendo el mismo estado
   PROMOCIONA/REGULARIZA/RECURSA que hoy.
7. **Orden intra-bloque (3.7)**: dentro de un bloque, los alumnos siguen ordenados por
   `(apellido, nombre)` tras ordenar los bloques.
8. **Encabezado de bloque (3.8)**: el título del bloque sigue siendo "{comisión} — Tutor: {tutor}".
9. **PROMOCIONA conserva su nota (3.9)**: un alumno PROMOCIONA mantiene la misma Nota Final
   numérica que el fix de Bug 2.
10. **Columna de examen "N/E" bajo Bug 4 (3.10)**: `_fmt_valor(None)` sigue siendo "N/E"; sólo
    `_fmt_nota_final(None)` cambió a blanco.

> **Nota sobre tests existentes:** `test_cierre_cursada_calculo.py` tiene tests que hoy afirman
> `calcular_nota_final(...) is None` (`test_nota_final_none_si_falta_global`,
> `test_nota_final_none_si_falta_un_parcial`, `test_nota_final_none_si_parcial_escala_sin_valor_numerico`).
> Esos casos codifican el comportamiento buggy (N/E) y DEBEN actualizarse al nuevo contrato
> numérico (3, 7 y 9 respectivamente). Los tests de guard estructural
> (`test_nota_final_none_si_no_hay_parciales`, `test_nota_final_none_si_no_hay_exactamente_un_global`)
> se conservan sin cambios. En `test_cierre_cursada_service.py`, los tests de `_resolver_comision`
> que pasan listas de strings deben migrarse a la nueva firma (lista de dicts `{id, name}`).
>
> **Bug 4:** El test `test_regulariza_con_global_numerico_tiene_nota_final_numerica` codifica la
> regla de Bug 2 (REGULARIZA con Nota Final numérica) y DEBE actualizarse al nuevo contrato:
> un alumno REGULARIZA debe pasar a tener `nota_final = None`. Renombrarlo/ajustarlo (p. ej.
> `test_regulariza_tiene_nota_final_none`). El test que verifica la Nota Final numérica de un
> alumno PROMOCIONA se conserva.

### Unit Tests

- `_resolver_comision`: match por `moodle_group_id`, match por nombre derivado, **multi-grupo**
  (alumno en "M26 C1-01" + "R-Mendoza" + "Grupo_500" → resuelve sólo la comisión, ignora regional
  y TPI), alumno sólo en regional/TPI sin grupo de comisión → "Sin comisión asignada", match
  ambiguo (>1 comisión distinta, dos grupos de comisión a la vez), unión de tutores con " / ",
  grupo sin id ni nombre válido.
- `calcular_nota_final`: parcial faltante→0, global faltante→0, ESCALA aprobado→10, ESCALA no
  aprobado/ausente→0, ejemplo P1=9.3/P2=0/Global=0 ⇒ 2, todo entregado (fórmula intacta), bordes
  de `round_half_up`, escala mixta, guard estructural (0 parciales / ≠1 global → None).
- `calcular_estado_cierre`: la Nota Final ahora numérica no altera el estado (mismos asserts de
  PROMOCIONA/REGULARIZA/RECURSA); **Bug 4**: `nota_final` numérica sólo para PROMOCIONA, `None`
  para REGULARIZA y RECURSA (actualizar
  `test_regulariza_con_global_numerico_tiene_nota_final_numerica`).
- `_agrupar_por_comision` (**Bug 3**): varias comisiones desordenadas → claves en orden alfabético;
  bucket "Sin comisión asignada" al final; una sola comisión (orden ya correcto); sólo
  "Sin comisión asignada" (bloque único); comisiones con distinto tutor pero conservando el título
  "{comisión} — Tutor: {tutor}".
- `_fmt_nota_final` / `_fmt_valor` (**Bug 4**): `_fmt_nota_final(None) == ""` (blanco),
  `_fmt_nota_final(8) == 8`, y `_fmt_valor(None) == "N/E"` (divergencia entre ambos).

### Property-Based Tests

- **Nota Final numérica (Property 2)**: generar listas con ≥1 parcial + 1 global y valores/faltantes
  aleatorios → `calcular_nota_final` siempre devuelve `int` en [0, 10].
- **Preservación de la fórmula (Property 4)**: generar exámenes con todos los valores numéricos →
  el fix coincide con la fórmula ponderada normalizada esperada.
- **Resolución de comisión (Property 1/3)**: generar alumnos con VARIOS grupos (un grupo de
  comisión más ruido aleatorio de grupos regional "R-*"/TPI "Grupo_NN"/cohortes que no matchean
  ninguna comisión) y comisiones aleatorias → un único grupo de comisión ⇒ esa comisión (el ruido
  no altera el resultado); cero grupos de comisión / dos grupos de comisión distintos ⇒
  "Sin comisión asignada".
- **Orden de bloques (Property 5)**: generar alumnos con nombres de comisión aleatorios (algunos
  sin comisión) en orden de llegada aleatorio → las claves de `_agrupar_por_comision` siempre
  quedan alfabéticas (case-insensitive) con "Sin comisión asignada" estrictamente último.
- **Nota Final por estado (Property 6)**: generar alumnos con estado y exámenes aleatorios → el
  `nota_final` del veredicto es `int` en [0, 10] sii `estado == "PROMOCIONA"`, y `None` en el resto.

### Integration Tests

- Flujo `generar` con un enrolled user que pertenece a VARIOS grupos (su grupo de comisión con
  `Comision.moodle_group_id` poblado, más un grupo regional y uno de TPI) → el
  `CierreCursadaAlumno` persistido queda con `comision_id`/`tutor_nombre` reales de la comisión,
  ignorando los grupos regional/TPI.
- Excel de cierre: alumnos agrupados por su comisión real (no todos bajo "Sin comisión asignada"),
  columna del examen en "N/E" pero Nota Final numérica en la misma fila (para PROMOCIONA).
- Excel de cierre con varias comisiones (**Bug 3**): los bloques salen ordenados alfabéticamente
  por comisión y "Sin comisión asignada" al final; los alumnos intra-bloque siguen por
  `(apellido, nombre)`.
- Excel de cierre con alumnos de distinto estado (**Bug 4**): un alumno PROMOCIONA muestra Nota
  Final numérica; un alumno REGULARIZA/RECURSA muestra la celda "Nota Final" en BLANCO mientras sus
  columnas de examen no entregado siguen mostrando "N/E".
- Materia sin exámenes configurados → 400 (preservación 3.5).
