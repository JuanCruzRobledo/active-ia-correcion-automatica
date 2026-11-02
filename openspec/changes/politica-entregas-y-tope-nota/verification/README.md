# Evidencia de verificación

Evidencia inicial: 2026-10-30; revalidación frontend y migración: 2026-11-02. Estado: implementación y verificación local completas; pendiente despliegue y archivo del change. Esta evidencia corresponde a desarrollo local con datos ficticios, sin producción ni despliegue.

## Frontend

Baseline completo: **31 archivos, 150 tests**; baseline enfocado: **44 tests**. Resultado: **35 archivos, 163 tests PASS** (13 casos nuevos), revalidado el 2026-11-02 en **135,55 s**, con `--maxWorkers=2 --no-file-parallelism`. Typecheck: **PASS**, revalidado el 2026-11-02. Build: **PASS** en la evidencia previa del 2026-10-30; no repetido en esta revalidación.

ESLint enfocado de `AnalisisArchivosEntrega` y `LimiteNotaEntrega`: **PASS sin warnings** el 2026-11-02.

Lint completo: **66 errores y 4 warnings**, idéntico al baseline. Los componentes y tests nuevos no agregan errores de lint. No se corrigieron fallos preexistentes ajenos al cambio. Build informa el aviso previo de base de datos Browserslist desactualizada.

### TDD Cycle Evidence

| Tarea | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.2 Análisis en entrega | `frontend/src/features/entregas/components/EntregaViewModal.politica.test.tsx` | Componente | 44 enfocados; 150 suite | 2 fallos iniciales; caso mixto produjo 1 fallo | 4 casos PASS | Restricción, limpia, histórica y residuos junto a infracción | Texto de residuos depende del máximo; suite verde |
| 4.2 Notas y edición | `frontend/src/features/correcciones/components/CorreccionViewEditModal.politica.test.tsx` | Componente | 44 enfocados; 150 suite | 2 fallos iniciales; nota manual 82 frente a final 50 | 4 casos PASS | Ambas notas, limpia, histórica y edición de nota académica | Verificado sin cambios adicionales de comportamiento |
| 4.3 Excepciones | `frontend/src/features/rubricas/components/DirectoriosPermitidosEditor.test.tsx` | Componente | 150 suite | Módulo/componente ausente | 3 casos PASS | Selección, conservación de metadata y accesibilidad | Suite completa verde |
| 4.3 Metadata existente | `frontend/src/features/rubricas/components/MetadataAdicionalEditor.test.tsx` | Componente | 150 suite | Módulo/componente ausente | 2 casos PASS | Preserva política al editar metadata y evita pérdida de campos | Wrapper aislado; suite completa verde |

### Verificación visual

Política visual: `off`, elección explícita del usuario; se conservó el estilo existente. No se requirieron mockups.

Se abrieron los componentes implementados en un navegador real con datos ficticios. El harness temporal usó QueryClient precargado y un adaptador Axios que rechazaba cualquier llamada API; se eliminó al terminar y el servidor local del puerto 4178 quedó detenido. No se utilizaron sesión, credenciales ni base de datos reales.

| Pantalla | Móvil 390x844 | Escritorio 1440x900 | Resultado |
|----------|---------------|--------------------|-----------|
| Detalle de entrega | [Captura](entrega-mobile.png) | [Captura](entrega-desktop.png) | Análisis y restricción visibles; sin desborde horizontal |
| Detalle de corrección | [Captura](correccion-mobile.png) | [Captura](correccion-desktop.png) | Ambas notas y explicación visibles; sin desborde horizontal |
| Editor de rúbrica | [Captura](rubrica-mobile.png) | [Captura](rubrica-desktop.png) | Excepciones visibles y accesibles; sin desborde horizontal |

Las seis capturas fueron abiertas e inspeccionadas por el agente frontend; el coordinador revisó además tres imágenes. No se registraron errores de consola ni solicitudes API. También se verificó en el DOM el estado limpio sin tope y con nota 82. Los estados históricos se cubren con tests de componentes.

Alcance: verificación de los componentes reales con datos controlados. No equivale a una prueba de autenticación o de importación Moodle contra un servidor real.

## Backend e integración

Baseline enfocado confirmado: **71 tests PASS**. Regresión backend final del 2026-11-02: **1825 PASS, 10 SKIP, 2912 warnings**, en **85,63 s**. Suite focal final: **50 PASS** (política 19, concurrencia 8, integración 12, exportaciones 9 y SQLite 2). Los warnings globales incluyen deprecaciones; no se declara una suite sin warnings.

Ejecución aislada: Python 3.13 con `-B -m pytest -p no:cacheprovider -q --tb=short`, `DEBUG=True`, `DATABASE_URL` dummy en `127.0.0.1:1` y `PYTHONDONTWRITEBYTECODE=1`. Sin base de producción ni proveedor real. `git diff --check`: **PASS**; no se generaron `.pyc`.

La primera regresión completa produjo 1814 PASS y 9 fallos por expectativas de fixtures frente al contrato nuevo: siete fixtures Moodle requerían `criterios_json` como diccionario y dos asserts PDF esperaban basename en vez de ruta completa. Se ajustaron los tests y se repitió la suite completa con el resultado final anterior. No se clasifican esos nueve fallos como preexistentes.

Flujo integrado SQLite en memoria: **2/2 PASS**, con servicios y repositorios reales y sólo la salida HTTP simulada. Verifica nota académica 90 → final 50 con infracción; reentrega limpia en estado SUBIDA sin corrección vigente → nueva corrección 90; reentrega aún infractora → final 50. Se preservan fuente y criterios en el historial. No equivale a una importación contra Moodle real.

Revisión final focal: **aprobada sin hallazgos abiertos**. Se comprobaron bloqueo y lectura de integridad, liberación del claim antes del proveedor, guardas de estado pendiente, conservación del snapshot y exportación PDF.

### TDD Cycle Evidence

| Tarea | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1–1.3, 3.1–3.2 Política y límite | `backend/tests/unit/services/test_politica_entrega.py`, `test_ia015_limite_codigo.py` | Unidad/servicio | 71 PASS previos | RED observado durante implementación original (helper ausente, inclusión de `dist` y `.properties`); log no conservado | Política 19 PASS; regresión completa PASS | Clasificación, excepciones, límites y notas cubiertos por suite | Suite final verde |
| 1.3, 2.1–2.3 Concurrencia y versiones | `backend/tests/unit/services/test_politica_entrega_concurrencia.py` | Servicio | 71 PASS previos | 6 RED ejecutados; luego 2 RED de guardas de carga | 8 concurrencia PASS; grupo intermedio 22 PASS | Cuatro canales, hash previo/nuevo, FOR UPDATE y snapshot sin commit final | 50 focales PASS |
| 2.1–2.3 Historial | `backend/tests/unit/services/test_politica_entrega_integracion.py` | Integración de servicios | 71 PASS previos | Snapshot raw/Moodle: KeyError observado | Integración 12 PASS | Reconsolidación y reentrega invalidan corrección activa; historial preservado | 50 focales PASS |
| 3.3 Exportaciones | `backend/tests/unit/services/test_politica_entrega_exportaciones.py` | Servicio/exportación | 7 PASS iniciales | 2 RED por motivo Moodle; luego 2 RED por comentario de auditoría | 9 PASS | Nota 90, nota 35 y ausencia de restricción | 50 focales PASS |
| 3.3 Ruta PDF | `backend/tests/unit/services/test_politica_entrega.py` | Unidad | Baseline enfocado previo | 3 RED con rutas anidadas | GREEN confirmado | Ruta normal, prefijo `./` y separadores Windows | Regresión completa PASS |
| 5.2 Flujo completo | `backend/tests/unit/services/test_politica_entrega_flujo_sqlite.py` | Integración SQLite | Suite focal previa | Verificación posterior; no se atribuye RED | 2 PASS | Reentrega limpia y nueva entrega todavía infractora | 50 focales PASS |

La tabla distingue ciclos RED confirmados de verificaciones posteriores. La evidencia RED original de política proviene del informe del agente del 2026-10-30; no se conservó su log ni se atribuye un conteo exacto de fallos. El refactor final ajustó alias/imports de fixtures para lint sin alterar comportamiento y se verificó con los 50 tests focales.

Lint backend final: Ruff 0.14.14 sobre **27 archivos Python del change**, **36 diagnósticos actuales frente a 37 en HEAD, cero nuevos**, comparando código, mensaje y ruta. Se corrigieron tres diagnósticos nuevos propios. Se excluyó el script no versionado ajeno `backend/scripts/purge_cohortes_viejas.py` (tres E402), que no fue modificado.

## Migración aislada

Validada el 2026-11-02 la revisión `b219adce5108`, con padre `f8b4d2e6c901`, como único head de Alembic. No se cargó `.env` ni se usó una base de datos real.

- PostgreSQL offline: upgrade genera dos columnas JSONB nullable sin backfill; downgrade genera los dos `DROP COLUMN` correspondientes.
- SQLite en memoria: upgrade conserva filas existentes con análisis `NULL`; lectura/escritura JSON comprobada; downgrade conserva las filas.
- Esta validación comprueba el SQL generado y la compatibilidad de datos en memoria; no constituye una ejecución de migración contra PostgreSQL real.

## Despliegue y límites

- Requiere revisar y ejecutar la migración aditiva que incorpora el análisis nullable a entrega e historial. No hay backfill de infracciones ni recalificación automática de entregas pasadas.
- Durante este trabajo no se ejecutan migraciones ni consultas sobre producción.
- Revisar la política y sus excepciones en las consignas antes de aplicarla a entregas de alumnos.
- Las entregas existentes que necesitan reconsolidación requieren aportar su archivo original; no se inventa evidencia a partir de una corrección anterior.
- El exceso de contenido evaluable debe bloquearse y comunicarse, sin enviar un prefijo incompleto al proveedor.
- Despliegue, cambios de datos de producción y archivo del change no están ejecutados.
