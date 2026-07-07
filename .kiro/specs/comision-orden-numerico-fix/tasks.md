# Implementation Plan

Fix del orden numérico natural de comisiones (una causa raíz — comparación del nombre como `str` —
replicada en 4 superficies). El plan sigue la metodología bugfix: primero un test de exploración de
la **Bug Condition** que DEBE fallar sobre el código sin arreglar en las 4 superficies, luego el
helper compartido, luego los fixes por superficie, luego tests de preservación/propiedad/integración
y un checkpoint final que corre toda la suite de backend.

> **Referencias:** Requisitos en `bugfix.md` (secciones 1.x, 2.x, 3.x) y `design.md`
> (Correctness Properties 1–5, Fix Implementation, Testing Strategy).

---

- [x] 1. Escribir test de exploración de la Bug Condition (ANTES del fix, en las 4 superficies)
  - **Property 1: Bug Condition** - Orden numérico natural del nombre de comisión
  - **CRITICAL**: Este test DEBE FALLAR sobre el código sin arreglar — la falla confirma que el bug existe.
  - **DO NOT** intentar arreglar el test ni el código cuando falle en esta tarea.
  - **NOTE**: Este test codifica el comportamiento esperado — validará el fix cuando pase tras la implementación (tarea 3.2).
  - **GOAL**: Surface counterexamples que demuestren el orden lexicográfico defectuoso (comparar el nombre como `str`).
  - **Scoped PBT Approach**: para el defecto determinístico, escopar la propiedad a casos concretos con sufijos de distinta longitud (`COMI-2` vs `COMI-10`) para garantizar reproducibilidad, y complementar con generación aleatoria de listas `PREFIJO-<n>`.
  - Crear el archivo de test (p. ej. `backend/tests/test_orden_natural_comision.py`) con casos por superficie:
    - **Superficie 1 (Excel)**: sembrar alumnos en `COMI-1, COMI-2, COMI-10, COMI-20` y asertar que las claves/orden de bloques de `_agrupar_por_comision` sean `COMI-1, COMI-2, COMI-10, COMI-20`. Hoy devuelve `COMI-1, COMI-10, COMI-2, COMI-20` → FALLA.
    - **Superficie 2 (Listado)**: comisiones del mismo año `COMI-2` y `COMI-10` → asertar `COMI-2` antes de `COMI-10` en `get_all`. Hoy `COMI-10` primero → FALLA.
    - **Superficie 3 (Corrida de cierre)**: alumnos con `comision_nombre` `M26 C1-02` y `M26 C1-10` en `get_alumnos_de_run` → asertar `…-02` antes de `…-10`. Hoy `…-10` primero → FALLA.
    - **Superficie 4 (Avance)**: `AvanceAlumno.comision` `COMI-3` y `COMI-21` en `get_alumnos_de_snapshot` → asertar `COMI-3` antes de `COMI-21`. Hoy `COMI-21` primero → FALLA.
  - Las aserciones deben matchear las Expected Behavior Properties del diseño (orden por valor ENTERO del sufijo dentro de cada prefijo).
  - Ejecutar el test sobre el código SIN ARREGLAR.
  - **EXPECTED OUTCOME**: el test FALLA en las 4 superficies (correcto — prueba que el bug existe).
  - Documentar los contraejemplos hallados (p. ej. "`_agrupar_por_comision` ubica `COMI-10` antes de `COMI-2`") para confirmar la causa raíz: comparación textual del nombre sin extraer el sufijo numérico como entero.
  - Marcar la tarea completa cuando el test esté escrito, ejecutado y la falla documentada.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

- [x] 2. Escribir tests de preservación (ANTES del fix — observation-first)
  - **Property 2: Preservation** - Fallback alfabético, año primario, desempates, nulos e intra-bloque
  - **IMPORTANT**: seguir metodología observation-first — ejecutar el código SIN ARREGLAR con inputs que NO disparan el bug, observar la salida real y escribir property-based tests que la capturen.
  - Cubrir (Correctness Properties 2, 3, 4 y 5 del diseño):
    - **Fallback alfabético (Property 2, 3.1)**: nombres SIN sufijo numérico (`Teórica, Práctica, Laboratorio`) → el orden observado es idéntico a `sorted(..., key=str.casefold)`. Property-based: para toda lista de nombres sin sufijo numérico, `natural_key` degrada al orden alfabético actual.
    - **Año primario y paginación/filtros (Property 3, 3.3, 3.7)**: observar en `get_all` que `anio desc` es el criterio primario y que, para cualquier filtro (materia/año/tutor/coordinador) y paginación (`per_page`), el conjunto de filas y el `total` no cambian respecto al comportamiento actual.
    - **Desempate estable + intra-bloque + "Sin comisión asignada" al final (Property 4, 3.2, 3.4, 3.5)**: observar que el desempate secundario existente se mantiene, que los alumnos dentro de un bloque/reporte se ordenan por `(Apellido, Nombre)` y que el bloque "Sin comisión asignada" queda último en el Excel, con encabezado "{comisión} — Tutor: {tutor}" intacto.
    - **Nulos al final (Property 5, 3.6)**: observar que filas con `comision_nombre`/`comision` = `NULL` quedan al final (`NULLS LAST`) sin excepción ni interrupción del reporte.
  - Escribir los tests como property-based donde aplique (fallback, estabilidad, nulls last) y como integración con datos sembrados para año/paginación/filtros.
  - Ejecutar los tests sobre el código SIN ARREGLAR.
  - **EXPECTED OUTCOME**: los tests PASAN (confirman el comportamiento base a preservar).
  - Marcar la tarea completa cuando los tests estén escritos, ejecutados y pasando sobre el código sin arreglar.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 3. Fix del orden numérico natural de comisiones

  - [x] 3.1 Crear el módulo compartido de orden natural
    - Crear `backend/app/utils/orden_natural.py` (utilidad pura, sin reglas de negocio ni acceso a datos; << 500 LOC).
    - Implementar `natural_key(nombre: str | None) -> tuple`: tokeniza `casefold(nombre)` en fragmentos texto/dígitos (`re.split(r"(\d+)", ...)`); dígitos → `(1, int(f))`, texto → `(0, f)`; `None` → cae al final; nombre vacío → `((0, ""),)`.
    - Implementar `orden_natural_sql(col) -> list`: `[func.lower(func.regexp_replace(col, r"\d+$", "")).asc(), cast(func.nullif(func.regexp_replace(col, r"^.*?(\d+)$", r"\1"), col), Integer).asc().nullslast(), col.asc()]` (prefijo alfabético case-insensitive + sufijo numérico a `Integer` con `NULLS LAST` + desempate por nombre completo).
    - _Bug_Condition: isBugCondition(nombres) donde el orden lexicográfico difiere del natural (design → Bug Condition)_
    - _Expected_Behavior: natural_key/orden_natural_sql ordenan por el valor entero del sufijo (design → Correctness Property 1)_
    - _Preservation: fallback alfabético (3.1), NULLS LAST (3.6), desempate estable (3.2)_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.6_

  - [x] 3.2 Superficie 1 — Excel de cierre de cursada
    - En `backend/app/services/excel_cierre_cursada.py`, función `_agrupar_por_comision`.
    - Importar `from app.utils.orden_natural import natural_key`.
    - Cambiar la clave de orden de las comisiones reales de `nombre.casefold()` a `natural_key(nombre)`, manteniendo la tupla `(0, natural_key(nombre))` para reales y `(1, ())` para el bucket "Sin comisión asignada" (que sigue al final).
    - No cambiar el mapeo `{titulo: [alumnos]}`, el título "{comisión} — Tutor: {tutor}", el orden intra-bloque por `(apellido, nombre)` ni los estilos.
    - _Bug_Condition: bloques con sufijos de distinta longitud (design → superficie 1)_
    - _Expected_Behavior: bloques en orden natural (design → Correctness Property 1)_
    - _Preservation: "Sin comisión asignada" al final (3.4), intra-bloque (3.5)_
    - _Requirements: 2.2, 3.4, 3.5_

  - [x] 3.3 Superficie 2 — Listado / gestión de comisiones
    - En `backend/app/repositories/comision_repository.py`, funciones `get_all`, `get_by_materia`, `get_by_materia_con_tutores`, `get_by_tutor`.
    - Importar `from app.utils.orden_natural import orden_natural_sql`.
    - `get_all`: reemplazar `.order_by(Comision.anio.desc(), Comision.nombre.asc())` por `.order_by(Comision.anio.desc(), *orden_natural_sql(Comision.nombre))` (año desc PRIMARIO; `order_by` antes de `offset/limit`, paginación y `count` intactos).
    - `get_by_materia` y `get_by_tutor`: reemplazar `Comision.nombre.asc()` por `*orden_natural_sql(Comision.nombre)`, conservando `Comision.anio.desc()` primero.
    - `get_by_materia_con_tutores`: reemplazar `.order_by(Comision.nombre.asc())` por `.order_by(*orden_natural_sql(Comision.nombre))`.
    - _Bug_Condition: comisiones del mismo año con sufijos de distinta longitud (design → superficie 2)_
    - _Expected_Behavior: orden natural del nombre como criterio secundario (design → Correctness Property 1)_
    - _Preservation: anio desc primario (3.3), filtros/paginación/total (3.7)_
    - _Requirements: 2.1, 3.3, 3.7_

  - [x] 3.4 Superficie 3 — Corrida de cierre (alumnos)
    - En `backend/app/repositories/cierre_cursada_repository.py`, función `get_alumnos_de_run`.
    - Importar `orden_natural_sql`.
    - Reemplazar `CierreCursadaAlumno.comision_nombre.asc().nullslast()` por `*orden_natural_sql(CierreCursadaAlumno.comision_nombre)`, conservando `apellido.asc()` y `nombre.asc()` como desempates finales.
    - _Bug_Condition: alumnos con comision_nombre de sufijo distinto (design → superficie 3)_
    - _Expected_Behavior: agrupación por orden natural del nombre (design → Correctness Property 1)_
    - _Preservation: NULLS LAST (3.6), intra-grupo (Apellido, Nombre) (3.5)_
    - _Requirements: 2.3, 3.5, 3.6_

  - [x] 3.5 Superficie 4 — Reporte de avance
    - En `backend/app/repositories/avance_repository.py`, funciones `get_alumnos_de_snapshot` y `get_alumnos_por_estado`.
    - Importar `orden_natural_sql`.
    - En ambas, reemplazar `AvanceAlumno.comision.asc().nullslast()` por `*orden_natural_sql(AvanceAlumno.comision)`, conservando `apellido.asc()` y `nombre.asc()`.
    - `orden_natural_sql` aplica `.nullslast()` en prefijo y sufijo para mantener "nulos al final".
    - _Bug_Condition: filas con comision de sufijo distinto (design → superficie 4)_
    - _Expected_Behavior: agrupación por orden natural del nombre (design → Correctness Property 1)_
    - _Preservation: NULLS LAST (3.6), intra-reporte (Apellido, Nombre) (3.5)_
    - _Requirements: 2.4, 3.5, 3.6_

  - [x] 3.6 Verificar que el test de exploración de la Bug Condition ahora pasa
    - **Property 1: Expected Behavior** - Orden numérico natural del nombre de comisión
    - **IMPORTANT**: re-ejecutar EL MISMO test de la tarea 1 — NO escribir un test nuevo.
    - El test de la tarea 1 codifica el comportamiento esperado; cuando pasa, confirma el orden natural en las 4 superficies.
    - Ejecutar el test de exploración de la tarea 1.
    - **EXPECTED OUTCOME**: el test PASA (confirma que el bug está arreglado).
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.7 Verificar que los tests de preservación siguen pasando
    - **Property 2: Preservation** - Fallback alfabético, año primario, desempates, nulos e intra-bloque
    - **IMPORTANT**: re-ejecutar LOS MISMOS tests de la tarea 2 — NO escribir tests nuevos.
    - Ejecutar los tests de preservación de la tarea 2.
    - **EXPECTED OUTCOME**: los tests PASAN (confirma que no hay regresiones).
    - Confirmar que todos los tests siguen pasando tras el fix.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 4. Tests unitarios, de propiedad e integración adicionales
  - **Unit — `natural_key`**: `COMI-2 < COMI-10 < COMI-27`; distintos prefijos (`A-1 < B-2`); alfabéticos puros (= `casefold`); case-insensitive (`comi-2` == `COMI-2`); número embebido no final (`COMI-1A` como texto); nombre vacío / `None` (no rompe, cae al final).
  - **Unit — `orden_natural_sql`**: devuelve 3 expresiones; prefijo con `lower`; sufijo cast a `Integer` con `NULLS LAST`; desempate final por la columna completa (compilar la expresión o integración).
  - **Unit — `_agrupar_por_comision`**: bloques `COMI-1, COMI-2, COMI-10` en orden natural; "Sin comisión asignada" último; una sola comisión; título con tutor intacto.
  - **PBT — Property 1**: listas `PREFIJO-<n>` con `n`/prefijos aleatorios → `sorted(key=natural_key)` agrupa por prefijo y ordena `n` como enteros.
  - **PBT — Property 2**: nombres sin sufijo → `sorted(key=natural_key) == sorted(key=str.casefold)`.
  - **PBT — Property 4**: duplicados / mismos `(prefijo, n)` → orden determinista y estable.
  - **PBT — Property 5**: mezcla `None` + nombres → claves de `None` estrictamente al final.
  - **Integración — Superficie 2**: sembrar `COMI-1..COMI-12` (dos años) → `get_all` en `anio desc` + orden natural, paginación (`per_page`) coherente y `total` correcto; repetir con filtros; verificar `get_by_materia`/`get_by_materia_con_tutores`/`get_by_tutor`.
  - **Integración — Superficie 3**: `get_alumnos_de_run` con `M26 C1-01..C1-10` (+ algunos sin comisión) → orden natural, nulos al final, luego `(apellido, nombre)`.
  - **Integración — Superficie 4**: `get_alumnos_de_snapshot` y `get_alumnos_por_estado` con `COMI-2..COMI-11` (+ nulos) → orden natural, nulos al final.
  - **Integración — Superficie 1**: generar el `.xlsx` con comisiones de distinta longitud de sufijo → bloques en orden natural y "Sin comisión asignada" al final.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 5. Checkpoint - Correr la suite completa de backend
  - Ejecutar `pytest` en `backend/` (single run, sin watch) y asegurar que TODOS los tests pasan.
  - Verificar QA checklist: sin `print` de debug, sin secrets, archivos < 500 LOC, permisos de endpoints intactos (no se tocaron routers).
  - Confirmar que el test de exploración (tarea 1) pasa y que los tests de preservación (tarea 2) siguen pasando.
  - Si surgen dudas o fallas inesperadas, consultar al usuario.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

---

## Task Dependency Graph

```
1. Bug Condition exploration test (FALLA en unfixed) ─┐
2. Preservation tests (PASAN en unfixed) ─────────────┤
                                                       │
                                                       v
3.1 Módulo compartido orden_natural.py  ──────────────┐
        │                                              │
        ├──> 3.2 Superficie 1 (Excel, natural_key)     │
        ├──> 3.3 Superficie 2 (comision_repository)    │ (3.2–3.5 en paralelo
        ├──> 3.4 Superficie 3 (cierre_cursada_repo)    │  tras 3.1)
        └──> 3.5 Superficie 4 (avance_repository)       │
                        │                               │
                        v                               │
        3.6 Re-run test tarea 1 (ahora PASA) <──────────┘
        3.7 Re-run tests tarea 2 (siguen PASANDO)
                        │
                        v
4. Unit + PBT + Integración por superficie
                        │
                        v
5. Checkpoint — pytest completo del backend
```

Dependencias clave:
- **1 y 2** deben completarse ANTES de cualquier cambio de código (baseline: 1 falla, 2 pasa).
- **3.1** (helper compartido) es prerequisito de **3.2, 3.3, 3.4, 3.5** (pueden hacerse en paralelo).
- **3.6 y 3.7** requieren los cuatro fixes de superficie aplicados.
- **4** amplía la cobertura tras confirmar el fix; **5** cierra corriendo toda la suite.
