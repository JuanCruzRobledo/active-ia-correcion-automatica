# ⚡ Auditoría de Optimización / Performance — Active-IA

**Dimensión**: Optimización / Performance
**Fecha**: 2026-07-12
**Alcance**: `backend/app/` (queries SQLAlchemy, N+1, índices, event loop, generación de Excel/PDF, uploads), `frontend/src/` (re-renders, React Query, bundle, lazy loading), modelos y migraciones Alembic.
**Fuera de alcance**: seguridad, arquitectura por capas (ya cubierto en `07-arquitectura.md`), documentación.

---

## Índice de hallazgos

| ID | Título | Severidad |
|----|--------|-----------|
| PERF-001 | Avalancha de `lazy="selectin"`: cargar una entidad arrastra colecciones enteras en cascada | 🔴 Crítica |
| PERF-002 | Los listados paginados traen columnas gigantes (`contenido_consolidado`, `pdf_contenido_b64`, `raw_response`) | 🔴 Crítica |
| PERF-003 | ZIP de PDFs de devoluciones: reportlab síncrono en el request + N+1 (re-query por corrección) | 🔴 Crítica |
| PERF-004 | Generación de Excel con openpyxl síncrono dentro de endpoints async (bloquea el event loop) | 🟠 Alta |
| PERF-005 | Carga masiva de entregas: ZIP entero en RAM, CPU síncrono en el request y un commit por alumno | 🟠 Alta |
| PERF-006 | PDFs de alumnos guardados como Base64 en columna `Text` de la tabla `entregas` | 🟠 Alta |
| PERF-007 | N+1 en listado de comisiones: query de tutores por comisión + carga de TODAS las entregas para contarlas | 🟠 Alta |
| PERF-008 | `MAX_UPLOAD_SIZE` definido pero nunca aplicado: uploads enteros a RAM sin límite efectivo | 🟠 Alta |
| PERF-009 | Exports "get all" con `per_page=1000`: truncan silenciosamente y cargan todo en memoria | 🟡 Media |
| PERF-010 | N+1 de COUNTs en dashboard de tutor (una query por comisión en loop) | 🟡 Media |
| PERF-011 | N+1 en dashboard de gestores: `get_ultimo_snapshot` por materia y árbol cohorte→cuatrimestre en loops | 🟡 Media |
| PERF-012 | N+1 en detalle de comisión/materia: `get_by_id` por tutor/coordinador dentro de loops | 🟡 Media |
| PERF-013 | Frontend manda `search` que el backend ignora: refetch inútil en cada búsqueda y filtro roto | 🟡 Media |
| PERF-014 | Casi ninguna página lazy-loaded: todo el frontend viaja en el bundle inicial | 🟡 Media |
| PERF-015 | `/sync/version` poleado cada 45s por cliente hace `MAX(updated_at)+COUNT(*)` sin índice | 🟢 Baja |
| PERF-016 | Falta índice en `comision_tutor.tutor_id` y en `entregas.created_at` (ordenamiento del listado) | 🟢 Baja |
| PERF-017 | `key={index}` en listas editables/mutables (fortalezas, recomendaciones, criterios) | 🟢 Baja |
| PERF-018 | Invalidaciones amplias `['entregas']` en cada mutación, superpuestas con el polling de 10s | 🟢 Baja |

---

### [CRÍTICA] Avalancha de `lazy="selectin"`: cargar una entidad arrastra colecciones enteras en cascada

- **ID**: PERF-001
- **Ubicación**: `backend/app/models/comision.py:61,66`, `backend/app/models/rubrica.py:154`, `backend/app/models/usuario.py:117-137`, `backend/app/models/materia.py:105-129`, `backend/app/models/entrega.py:141`, `backend/app/models/cohorte.py:49,87`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Performance
- **Descripción**: Casi todas las colecciones 1:N del modelo están declaradas con `lazy="selectin"`, que se dispara **siempre** que la entidad se materializa, en cualquier query, la necesites o no. Como los `selectin` se encadenan, cargar una entidad "liviana" desencadena una cascada: `Materia` → `comisiones` + `rubricas` → cada `Comision`/`Rubrica` → **TODAS sus entregas** (filas completas, ver PERF-002) → cada `Entrega` → todo su `historial`. `Usuario` es el peor caso: tiene 5 colecciones selectin, incluyendo `entregas_subidas` (todas las entregas que subió, con contenido completo), `correcciones_realizadas` (con `criterios_json` y `raw_response`) y `actividades_realizadas` (el audit log entero del usuario, que crece sin límite).
- **Evidencia**:
  - `comision.py:63-67`: `entregas: ... lazy="selectin"` — cualquier query que devuelva una `Comision` carga todas sus entregas.
  - `rubrica.py:151-155`: ídem para `Rubrica.entregas` — el ABM de rúbricas (`rubrica_repository.py:82-148`, `select(Rubrica)` paginado) arrastra todas las entregas de cada rúbrica listada.
  - `usuario.py:114-138`: 5 relaciones selectin. El listado de entregas hace `selectinload(Entrega.subido_por)` (`entrega_repository.py:118`) → materializa `Usuario` → dispara sus 5 selectin → una de ellas vuelve a cargar **todas las entregas** subidas por ese usuario → cada una con su `historial` selectin (`entrega.py:141`). Página de 20 entregas = potencialmente miles de filas pesadas.
  - `materia.py:102-130`: 5 colecciones selectin (`unidades`, `examenes`, `coordinadores`, `comisiones`, `rubricas`). `comisiones` y `rubricas` encadenan a la avalancha de entregas descripta arriba.
  - La autenticación fue mitigada a mano con `get_by_id_light` + `noload("*")` (`usuario_repository.py:53-65`) — señal de que el problema ya mordió y se parchó solo en ese camino; todos los demás caminos siguen expuestos.
- **Impacto**: Escala cuadráticamente con los datos: con 10 comisiones × 200 entregas × contenido consolidado de ~100KB, listar comisiones puede mover cientos de MB desde Postgres y serializar decenas de miles de objetos ORM por request. Es el multiplicador que convierte cada otro hallazgo (PERF-002, PERF-007) en catástrofe. Latencia y RAM del backend crecen con el cuatrimestre hasta degradar todo el sistema.
- **Reproducción**: activar `echo=True` en el engine y pegarle a `GET /comisiones/` o `GET /rubricas/`: se ven los `SELECT ... FROM entregas WHERE comision_id IN (...)` y `... FROM entregas_historial ...` que nadie pidió.
- **Fix propuesto**: sacar `lazy="selectin"` de todas las colecciones potencialmente grandes (`*.entregas`, `Usuario.entregas_subidas/correcciones_realizadas/actividades_realizadas`, `Entrega.historial`, `Materia.comisiones/rubricas`) y volver a `lazy="raise"` o `select`, cargando explícitamente con `selectinload()` solo donde cada endpoint lo necesita. Dejar selectin únicamente en colecciones chicas y acotadas (`unidades`, `componentes`, `cuatrimestres`).
- **Esfuerzo estimado**: M (el cambio es chico; el testing de regresión de cada endpoint es lo que pesa).

---

### [CRÍTICA] Los listados paginados traen columnas gigantes (`contenido_consolidado`, `pdf_contenido_b64`, `raw_response`)

- **ID**: PERF-002
- **Ubicación**: `backend/app/repositories/entrega_repository.py:115-157`, `backend/app/repositories/correccion_repository.py:161-195`, `backend/app/models/entrega.py:63-74`, `backend/app/models/correccion.py:95-98`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Performance
- **Descripción**: `Entrega` guarda en la misma fila el código consolidado completo (`contenido_consolidado`, `Text`) y el PDF en Base64 (`pdf_contenido_b64`, `Text`). Ningún query los difiere: `EntregaRepository.get_all` hace `select(Entrega)` con todas las columnas para armar un listado que solo usa nombre, estado, nota y metadatos. Lo mismo `CorreccionRepository.get_all`, que además de sus propios `criterios_json` + `raw_response` (respuesta cruda completa de Gemini) eager-loadea la `Entrega` entera vía `selectinload(Correccion.entrega)`.
- **Evidencia**:
  - `entrega_repository.py:115-120`: `select(Entrega).options(selectinload(...))` sin `load_only`/`defer` — cada página de 20 mueve 20 × (código completo + PDF b64).
  - `entrega_service.py:439-462`: el `EntregaListItem` construido solo usa campos livianos; el contenido pesado se descarta después de viajar desde la DB.
  - `correccion_repository.py:161-165`: `selectinload(Correccion.entrega)` → fila completa de entrega (con PDF b64) por cada corrección listada, más `raw_response` JSONB de la propia corrección.
  - El count de paginación (`entrega_repository.py:147`) se hace con `select(func.count()).select_from(query.subquery())` — un subquery que incluye todas las columnas pesadas en lugar de `count(*)` sobre la tabla filtrada.
- **Impacto**: Con entregas PDF de 5MB (b64 ≈ 6.7MB por fila), una página de 20 entregas puede mover >100MB entre Postgres y el backend para responder un JSON de 10KB. Combinado con PERF-001, el mismo costo se paga en endpoints que ni siquiera son de entregas.
- **Reproducción**: subir 20 entregas PDF de varios MB y medir `GET /entregas/?page=1` con `EXPLAIN ANALYZE` o el log de queries: el ancho de fila lo domina `pdf_contenido_b64`.
- **Fix propuesto**: marcar `contenido_consolidado`, `pdf_contenido_b64` y `raw_response` como `deferred` (carga explícita solo en los endpoints de contenido/corrección individual), o usar `load_only()` en los queries de listado. El count debería ser `select(func.count(Entrega.id)).where(...)` sobre los mismos filtros, sin subquery de fila completa.
- **Esfuerzo estimado**: S

---

### [CRÍTICA] ZIP de PDFs de devoluciones: reportlab síncrono en el request + N+1 (re-query por corrección)

- **ID**: PERF-003
- **Ubicación**: `backend/app/services/pdf_service.py:113-187` y `189-240`, `backend/app/routers/documentos.py:109-147`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Performance
- **Descripción**: `generar_zip_pdfs` primero trae hasta 1000 correcciones **con todas sus relaciones ya cargadas** (`correccion_repo.get_all`, línea 134) y después, dentro del loop (línea 170-172), llama `await self.generar_pdf_devolucion(correccion.id)` que **vuelve a consultar** la misma corrección con `get_by_id_with_relations` — N+1 puro sobre datos que ya estaban en memoria. Además, la construcción de cada PDF con reportlab es CPU-bound 100% síncrona y corre inline en el endpoint async: durante todo el armado del ZIP el event loop queda bloqueado y **ningún otro request del backend avanza**.
- **Evidencia**:
  - `pdf_service.py:134-139`: fetch masivo con relaciones (`per_page=1000`).
  - `pdf_service.py:170-172`: `for correccion in correcciones_list: pdf_bytes = await self.generar_pdf_devolucion(correccion.id)` → `pdf_service.py:83`: `await self.correccion_repo.get_by_id_with_relations(correccion_id)` (query + selectin cascada de nuevo, por cada una).
  - reportlab (`pdf_service.py:16-30`) no tiene API async; no hay `run_in_executor`/`to_thread` en todo `app/` (verificado por grep — solo `BackgroundTasks` en correcciones).
  - Mismo patrón en `generar_zip_pdfs_seleccionados` (líneas 232-233).
- **Impacto**: Para una comisión de 100 alumnos: 1 query masiva + 100 queries con relaciones + 100 PDFs renderizados + compresión ZIP, todo en el hilo del event loop. El backend entero (health checks, login, polling de entregas) se congela durante segundos o minutos. Es el candidato #1 a "se colgó el sistema" en época de cierre.
- **Reproducción**: pedir `GET /documentos/comisiones/{id}/rubricas/{id}/pdfs-zip` con 100+ correcciones y, en paralelo, `GET /health` — el health queda esperando hasta que termina el ZIP.
- **Fix propuesto**: (1) pasarle el objeto `correccion` ya cargado a la función de armado del PDF en lugar del ID (elimina el N+1); (2) mover el render reportlab + zipfile a `asyncio.to_thread` o, mejor, a un job en background (mismo patrón `BackgroundTasks` + polling que ya usa la corrección masiva) devolviendo 202 y un link de descarga.
- **Esfuerzo estimado**: M

---

### [ALTA] Generación de Excel con openpyxl síncrono dentro de endpoints async (bloquea el event loop)

- **ID**: PERF-004
- **Ubicación**: `backend/app/services/excel_service.py:37-237,245-346,352-475`, `backend/app/services/excel_cierre_cursada.py`, `backend/app/services/dashboard_excel.py`, `backend/app/routers/documentos.py:164-180`, `backend/app/routers/gestion.py:91-122`
- **Severidad**: 🟠 Alta
- **Dimensión**: Performance
- **Descripción**: Todos los exports Excel (`notas`, `gestión`, `pendientes`, `avance`, `cierre de cursada`) construyen el workbook con openpyxl — celda por celda, con estilos — de forma síncrona dentro del handler async. Igual que PERF-003, mientras se arma el `.xlsx` el event loop no atiende nada más. `exportar_notas_excel` además re-consulta la primera entrega con relaciones anidadas (`excel_service.py:76-87`) cuando el `get_all` anterior ya la trajo.
- **Evidencia**: `excel_service.py:37` (`async def exportar_notas_excel`) → loop de celdas 142-205 y `wb.save(excel_buffer)` en 227, sin ningún `to_thread`. `documentos.py:180` lo invoca directo en el request. No existe ningún `run_in_executor`/`asyncio.to_thread` en el backend (grep verificado).
- **Impacto**: Con cientos de filas + estilos por celda, cada export son cientos de ms a segundos de event loop bloqueado. En horario pico (varios tutores exportando), los requests se serializan detrás de los Excel.
- **Reproducción**: exportar notas de una comisión grande y medir la latencia de cualquier otro endpoint concurrente.
- **Fix propuesto**: envolver la construcción del workbook (y el `wb.save`) en `asyncio.to_thread(...)`. Es un cambio quirúrgico por servicio; no requiere tocar la lógica.
- **Esfuerzo estimado**: S

---

### [ALTA] Carga masiva de entregas: ZIP entero en RAM, CPU síncrono en el request y un commit por alumno

- **ID**: PERF-005
- **Ubicación**: `backend/app/services/entrega_service.py:669-963`, `backend/app/services/consolidacion_service.py:216-420`, `backend/app/repositories/entrega_repository.py:214-227`
- **Severidad**: 🟠 Alta
- **Dimensión**: Performance
- **Descripción**: `crear_entrega_masiva` lee el ZIP completo a memoria (`await archivo_zip.read()`, línea 732), y procesa cada alumno **secuencialmente dentro del request HTTP**: descompresión y consolidación de texto síncronas (`consolidacion_service.consolidar_zip` es `def` común, llamado sin `to_thread`), re-compresión con `zipfile` para carpetas con archivos sueltos (líneas 817-828), y por cada alumno 1-2 queries de existencia + `entrega_repo.create()` que hace **`commit` + `refresh` individual** (`entrega_repository.py:224-227`). Bonus: el `tempfile.NamedTemporaryFile(suffix=".zip", delete=False)` de la línea 817 nunca se borra — se acumulan ZIPs temporales en disco en cada carga masiva.
- **Evidencia**:
  - `entrega_service.py:732`: ZIP completo en RAM (hasta 100MB según config, ver PERF-008).
  - `entrega_service.py:759-931`: loop por alumno con `_procesar_contenido` (CPU sync) + `get_by_rubrica_alumno` + `create` (commit por fila).
  - `entrega_service.py:817`: `delete=False` sin `os.unlink` posterior.
- **Impacto**: Una comisión de 50 alumnos = 50 descompresiones + 50 consolidaciones + ~100 queries + 50 commits, todo bloqueando el event loop y con el cliente esperando (riesgo de timeout del proxy). El leak de temporales llena disco en el contenedor con el tiempo.
- **Reproducción**: subir un ZIP masivo de 50 carpetas y observar la duración del request y los archivos residuales en `/tmp` del contenedor.
- **Fix propuesto**: procesar el lote en background (202 + polling, patrón que ya existe para corrección masiva); mover consolidación/zipfile a `to_thread`; acumular las entregas y hacer un solo `commit` por lote (o por chunks); crear el ZIP intermedio en memoria (`io.BytesIO`) en lugar de `NamedTemporaryFile` con `delete=False`.
- **Esfuerzo estimado**: M

---

### [ALTA] PDFs de alumnos guardados como Base64 en columna `Text` de la tabla `entregas`

- **ID**: PERF-006
- **Ubicación**: `backend/app/models/entrega.py:71-74`, `backend/app/services/entrega_service.py:334-339`, migración `backend/alembic/versions/20260220_add_pdf_contenido_b64_to_entregas.py`
- **Severidad**: 🟠 Alta
- **Dimensión**: Performance
- **Descripción**: Las entregas PDF se persisten como Base64 dentro de la fila (`pdf_contenido_b64: Text`). Base64 infla el tamaño +33% sobre el binario, y al estar en la tabla principal la fila gigante viaja en cada `select(Entrega)` sin defer (PERF-002) y engorda el TOAST/caché de Postgres. El campo `archivo_ruta` existe y se calcula (`/uploads/entregas/...`) pero el archivo nunca se escribe a disco: la DB es el único storage.
- **Evidencia**: `entrega_service.py:338`: `pdf_b64 = base64.b64encode(contenido_bytes).decode("utf-8")` → columna `Text`. `UPLOAD_DIR` está definido en config pero no se usa para persistir entregas.
- **Impacto**: Cada PDF de 5MB ocupa ~6.7MB en la DB y se arrastra en listados, backups y réplicas. Multiplica directamente PERF-001/PERF-002. El tamaño de la DB crece con material binario que no necesita estar ahí.
- **Fix propuesto**: guardar los PDFs (y opcionalmente el consolidado grande) en filesystem/objeto (`UPLOAD_DIR` ya existe como concepto) o al menos como `BYTEA` diferido, dejando en la fila solo la ruta/hash. Como mínimo inmediato: `deferred` en la columna (ver PERF-002).
- **Esfuerzo estimado**: L (migración de datos incluida) / S si solo se difiere la columna.

---

### [ALTA] N+1 en listado de comisiones: query de tutores por comisión + carga de TODAS las entregas para contarlas

- **ID**: PERF-007
- **Ubicación**: `backend/app/services/comision_service.py:179-206`
- **Severidad**: 🟠 Alta
- **Dimensión**: Performance
- **Descripción**: `listar_comisiones` pagina las comisiones y después, **por cada una**: (a) dispara `get_tutores_for_comision(comision.id)` (1 query por comisión, línea 181) solo para hacer `len()`; (b) computa `num_entregas` con `len(comision.entregas)` (línea 188) — y `comision.entregas` es la colección `lazy="selectin"` de PERF-001, o sea que para **contar** se materializan todas las filas de entregas de cada comisión listada, con sus columnas pesadas y su historial.
- **Evidencia**: `comision_service.py:181` y `comision_service.py:187-191`.
- **Impacto**: Página de 20 comisiones = 1 query base + 20 de tutores + 20 selectin de entregas completas + N selectin de historial. Con comisiones de 200 entregas son ~4000 filas pesadas para mostrar dos numeritos.
- **Reproducción**: `GET /comisiones/?per_page=20` con echo SQL: contar los `SELECT ... FROM comision_tutor` y `SELECT ... FROM entregas`.
- **Fix propuesto**: una sola query agregada con `GROUP BY comision_id` (COUNT de tutores y COUNT de entregas via outerjoin) o dos queries `IN (...)` con `func.count()`. Nunca contar materializando la colección.
- **Esfuerzo estimado**: S

---

### [ALTA] `MAX_UPLOAD_SIZE` definido pero nunca aplicado: uploads enteros a RAM sin límite efectivo

- **ID**: PERF-008
- **Ubicación**: `backend/app/core/config.py:93`, `backend/app/services/entrega_service.py:136,732`
- **Severidad**: 🟠 Alta
- **Dimensión**: Performance
- **Descripción**: `MAX_UPLOAD_SIZE = 104857600` (100MB) existe en la config pero ningún código lo referencia (grep sin resultados fuera de config). Los endpoints de upload hacen `await archivo.read()` directo: el archivo completo va a RAM sin verificación de tamaño previa ni streaming. ⚠️ A confirmar: si el nginx de producción tiene `client_max_body_size` configurado, el impacto real queda acotado por ese límite — no se encontró esa directiva en `nginx/nginx.conf`.
- **Evidencia**: `entrega_service.py:136`: `contenido_bytes = await archivo.read()` sin chequeo; ídem 732 para la masiva. `rg MAX_UPLOAD_SIZE backend/app` → solo `config.py`.
- **Impacto**: Un upload de cientos de MB (accidental o malicioso) se materializa entero en la RAM del worker; varios concurrentes tiran el contenedor por OOM.
- **Fix propuesto**: validar `Content-Length`/tamaño acumulado contra `settings.MAX_UPLOAD_SIZE` antes/durante la lectura (lectura por chunks), y fijar `client_max_body_size` en nginx como segunda barrera.
- **Esfuerzo estimado**: S

---

### [MEDIA] Exports "get all" con `per_page=1000`: truncan silenciosamente y cargan todo en memoria

- **ID**: PERF-009
- **Ubicación**: `backend/app/services/excel_service.py:58-63`, `backend/app/services/pdf_service.py:134-139`
- **Severidad**: 🟡 Media
- **Dimensión**: Performance
- **Descripción**: Los exports simulan "traer todo" abusando de la paginación con `per_page=1000` y comentario `# Get all`. Dos problemas: (1) si una comisión/rúbrica supera 1000 entregas o correcciones, el export **omite filas sin avisar** (Excel de notas incompleto); (2) se cargan hasta 1000 objetos ORM con relaciones y columnas pesadas (PERF-002) de una, en memoria.
- **Evidencia**: `excel_service.py:62`: `per_page=1000,  # Get all`; `pdf_service.py:138` ídem.
- **Impacto**: Corrección silenciosa de datos (notas faltantes en el Excel oficial) + pico de RAM por export.
- **Fix propuesto**: método de repositorio dedicado sin límite artificial que haga streaming/iteración por chunks (`yield_per`) y seleccione solo las columnas que el export necesita.
- **Esfuerzo estimado**: S

---

### [MEDIA] N+1 de COUNTs en dashboard de tutor (una query por comisión en loop)

- **ID**: PERF-010
- **Ubicación**: `backend/app/services/dashboard_service.py:229-248`
- **Severidad**: 🟡 Media
- **Dimensión**: Performance
- **Descripción**: `get_tutor_stats` ya trae los totales por comisión con un `GROUP BY` (líneas 212-227), pero después, "para cada comision, contar pendientes manualmente": un `SELECT COUNT(*)` por comisión dentro del loop (líneas 233-238).
- **Evidencia**: `dashboard_service.py:231-238` — el propio comentario lo admite.
- **Impacto**: Tutor con 15 comisiones = 15 queries extra en cada carga del dashboard (pantalla de entrada de la app, se abre seguido).
- **Fix propuesto**: sumar el conteo de pendientes a la query agregada existente con `func.count().filter(...)` / `case()` condicional por estado. Una sola query.
- **Esfuerzo estimado**: S

---

### [MEDIA] N+1 en dashboard de gestores: `get_ultimo_snapshot` por materia y árbol por cuatrimestre en loops

- **ID**: PERF-011
- **Ubicación**: `backend/app/services/dashboard_lectura_service.py:45-60, 62-86, 98-104`, `backend/app/services/notificacion_service.py:80, 102`
- **Severidad**: 🟡 Media
- **Dimensión**: Performance
- **Descripción**: Tres loops con query adentro: `materias_configuradas` pide el último snapshot **por materia** (línea 50); `obtener_arbol` pide las materias **por cuatrimestre** (línea 69); `_ultimos_snapshots` repite el patrón por materia (línea 101) y lo usan `avance`, `avance_excel` y `detalle`. `notificacion_service` repite ambos patrones (snapshot por materia en línea 81, comisiones por tutor en línea 103).
- **Evidencia**: citadas arriba; `get_ultimo_snapshot` es 1 query con `ORDER BY ... LIMIT 1` cada vez.
- **Impacto**: Con 30 materias configuradas, cada carga del dashboard de gestores son ~30-60 queries en serie (latencia acumulada por round-trips). No es catastrófico hoy, pero es la pantalla que más crece con la adopción.
- **Fix propuesto**: query única de "último snapshot por materia" con `DISTINCT ON (materia_id) ... ORDER BY materia_id, generado_en DESC` (o window function), y armar el árbol con un solo `select` de materias `IN (cuatrimestre_ids)` agrupado en Python.
- **Esfuerzo estimado**: S

---

### [MEDIA] N+1 en detalle de comisión/materia: `get_by_id` por tutor/coordinador dentro de loops

- **ID**: PERF-012
- **Ubicación**: `backend/app/services/comision_service.py:245-255`, `backend/app/services/materia_service.py:167-171, 221-224`, validaciones en `comision_service.py:94, 325, 498` y `materia_service.py:79, 286, 428`
- **Severidad**: 🟡 Media
- **Dimensión**: Performance
- **Descripción**: `obtener_comision` itera `comision.tutores` y hace `usuario_repo.get_by_id(ct.tutor_id)` por cada uno (línea 246), cuando `ComisionTutor.tutor` es una relación que se puede eager-loadear en una query. Mismo patrón en materias con coordinadores, y en los ABMs al validar listas de IDs (un `get_active_by_id` por ID en vez de un `WHERE id IN (...)`).
- **Evidencia**: citada arriba; detectado también por scan automático de loops con `await ...repo.` adentro.
- **Impacto**: Menor en volumen (pocos tutores por comisión) pero es el patrón repetido en 6+ lugares; suma round-trips y, vía PERF-001, cada `Usuario` cargado arrastra sus 5 colecciones selectin — ahí sí duele.
- **Fix propuesto**: `selectinload(ComisionTutor.tutor)` en el query del detalle (con `load_only` de columnas del usuario) y validación de IDs por lote con `IN`.
- **Esfuerzo estimado**: S

---

### [MEDIA] Frontend manda `search` que el backend ignora: refetch inútil en cada búsqueda y filtro roto

- **ID**: PERF-013
- **Ubicación**: `frontend/src/features/entregas/services/entregas-service.ts:41-42`, `frontend/src/features/entregas/pages/EntregasPage.tsx:168,266-285`, `backend/app/routers/entregas.py:41-53`
- **Severidad**: 🟡 Media
- **Dimensión**: Performance
- **Descripción**: `EntregasPage` tiene un buscador con debounce que agrega `search` al query key y al request (`params.append('search', ...)`). Pero `GET /entregas/` **no declara ningún parámetro `search`** — FastAPI lo descarta. Resultado: cada búsqueda dispara un fetch completo de la lista que devuelve exactamente los mismos datos sin filtrar (query key distinta = cache miss garantizado), y el usuario ve la lista sin filtrar.
- **Evidencia**: firma de `listar_entregas` en `routers/entregas.py:41-53` (sin `search`); `entrega_repository.get_all` tampoco filtra por nombre de alumno.
- **Impacto**: Requests redundantes en cada tipeo (uno por debounce) + funcionalidad de búsqueda rota — el usuario pagina a mano para encontrar un alumno, generando más requests todavía.
- **Reproducción**: escribir en el buscador de Entregas y mirar Network: mismos resultados con y sin `search`.
- **Fix propuesto**: implementar `search` en el backend (`ILIKE` sobre `alumno_nombre`, que ya participa del índice único `uq_entrega_rubrica_alumno`) o filtrar client-side sin tocar el query key. Elegir uno, no ambos.
- **Esfuerzo estimado**: S

---

### [MEDIA] Casi ninguna página lazy-loaded: todo el frontend viaja en el bundle inicial

- **ID**: PERF-014
- **Ubicación**: `frontend/src/app/router.tsx:7-23`
- **Severidad**: 🟡 Media
- **Dimensión**: Performance
- **Descripción**: La regla del proyecto dice "pages lazy-loaded", pero solo `DashboardGestorPage` usa `lazy()` (por Recharts, líneas 25-31). Las otras 17 páginas — incluyendo las más pesadas: `EntregasPage` (1434 LOC), `PerfilPage` (837), `RubricasPage`, `CierreCursadaPage` — se importan estáticamente, así que el bundle inicial incluye la app completa aunque un tutor solo use 3 pantallas.
- **Evidencia**: `router.tsx:7-23`: imports estáticos de todas las páginas.
- **Impacto**: Primer load (y cada deploy que invalida el hash) descarga y parsea código de pantallas de admin/gestor que la mayoría de los roles jamás visita. En mobile/red lenta afecta el TTI del login.
- **Fix propuesto**: replicar el patrón ya existente de `DashboardGestorPage` para el resto de las páginas (route-level `lazy()` + `Suspense` en el layout). Es mecánico.
- **Esfuerzo estimado**: S

---

### [BAJA] `/sync/version` poleado cada 45s por cliente hace `MAX(updated_at)+COUNT(*)` sin índice

- **ID**: PERF-015
- **Ubicación**: `backend/app/repositories/entrega_repository.py:38-44`, `frontend/src/shared/hooks/useNovedades.ts:33-40`
- **Severidad**: 🟢 Baja
- **Dimensión**: Performance
- **Descripción**: El token de novedades es `SELECT MAX(updated_at), COUNT(id) FROM entregas` — sin índice en `updated_at` (el `TimestampMixin` de `base.py:54-62` no indexa), es un scan completo de la tabla, ejecutado cada 45 segundos por **cada** cliente con la pantalla de entregas abierta.
- **Evidencia**: citada arriba; `useNovedades.ts:36` `refetchInterval: intervalMs` (45s default).
- **Impacto**: Hoy es barato; con decenas de miles de entregas y muchos tutores conectados se vuelve un scan constante de una tabla con filas gigantes (PERF-006). ⚠️ A confirmar el volumen real de producción.
- **Fix propuesto**: índice en `entregas.updated_at` (el MAX pasa a ser lookup de índice) o mantener el token en una tabla/registro de versión actualizado por trigger o por el propio service al escribir.
- **Esfuerzo estimado**: S

---

### [BAJA] Falta índice en `comision_tutor.tutor_id` y en `entregas.created_at`

- **ID**: PERF-016
- **Ubicación**: `backend/app/models/comision.py:83-100`, `backend/app/models/base.py:54-62`, `backend/app/repositories/entrega_repository.py:152, 333-346`
- **Severidad**: 🟢 Baja
- **Dimensión**: Performance
- **Descripción**: `ComisionTutor` solo tiene el unique `(comision_id, tutor_id)` — sirve para buscar por comisión (prefijo) pero **no** por `tutor_id` solo, que es exactamente el filtro de `get_subidas_ids_by_tutor`, `contar_estados_by_tutor`, `contar_errores_by_tutor` (corrección global + progreso, poleado por el frontend) y el dashboard de tutor. Además el listado de entregas ordena por `created_at DESC` (`entrega_repository.py:152`) sin índice en esa columna.
- **Evidencia**: `comision.py:94-100` (solo `UniqueConstraint`), joins por `ComisionTutor.tutor_id` en `entrega_repository.py:338, 359, 377`.
- **Impacto**: Tablas chicas hoy → seq scans baratos. Crece linealmente con adopción. Es prevención barata, no urgencia.
- **Fix propuesto**: migración Alembic con `Index("ix_comision_tutor_tutor_id", "tutor_id")` y `Index("ix_entregas_created_at", "created_at")` (o índice compuesto `(comision_id, rubrica_id, created_at)` alineado al filtro del listado).
- **Esfuerzo estimado**: S

---

### [BAJA] `key={index}` en listas editables/mutables

- **ID**: PERF-017
- **Ubicación**: `frontend/src/features/correcciones/components/CorreccionViewEditModal.tsx:525,598`, `frontend/src/features/correcciones/components/CorreccionDetailModal.tsx:285,339`, `frontend/src/features/entregas/components/CargaEntregaModal.tsx:181,202`
- **Severidad**: 🟢 Baja
- **Dimensión**: Performance
- **Descripción**: Las listas de fortalezas y recomendaciones del modal de edición de corrección usan `key={index}` **y** permiten eliminar ítems por índice (`handleEliminarFortaleza(index)`). Al borrar el ítem N, React reutiliza los nodos de N+1 en adelante con keys corridas: re-render innecesario de toda la cola de la lista y riesgo de estado visual pegado al ítem equivocado.
- **Evidencia**: `CorreccionViewEditModal.tsx:523-542` (map con `key={index}` + botón de eliminar por índice).
- **Impacto**: Listas cortas (<20 ítems) → costo real bajo; es más un bug latente de reconciliación que un problema de velocidad.
- **Fix propuesto**: key estable (el texto del ítem si es único, o un id generado al agregar). En listas de solo lectura (`QuickActions`, dropdowns estáticos) el index como key es aceptable — no tocar.
- **Esfuerzo estimado**: S

---

### [BAJA] Invalidaciones amplias `['entregas']` en cada mutación, superpuestas con el polling de 10s

- **ID**: PERF-018
- **Ubicación**: `frontend/src/features/correcciones/hooks/useCorrecciones.ts:134,178,241,266`, `frontend/src/features/entregas/pages/EntregasPage.tsx:197-205`
- **Severidad**: 🟢 Baja
- **Dimensión**: Performance
- **Descripción**: Cada mutación de corrección invalida `{ queryKey: ['entregas'] }` completo (todas las listas de todas las combinaciones de filtros en caché, más detalles), mientras `EntregasPage` ya invalida `['entregas','list']` cada 10s durante un batch. Durante una corrección en lote, cada cambio dispara refetches de queries que el usuario no está mirando.
- **Evidencia**: citada arriba; el query key factory `entregasKeys.lists()` existe (`useEntregas.ts:328,346`) pero los hooks de correcciones no lo usan.
- **Impacto**: Requests redundantes durante los lotes; con la lista paginada y filtrada el impacto es moderado, pero suma sobre PERF-002 (cada refetch mueve filas pesadas en el backend).
- **Fix propuesto**: invalidar con las keys específicas (`entregasKeys.lists()` + el detalle afectado) y, durante batch activo, confiar solo en el polling en vez de invalidar en cada `onSuccess`.
- **Esfuerzo estimado**: S

---

## Resumen

| Severidad | Cantidad |
|-----------|----------|
| 🔴 Crítica | 3 |
| 🟠 Alta | 5 |
| 🟡 Media | 6 |
| 🟢 Baja | 4 |
| **Total** | **18** |

**El patrón de fondo**: los tres críticos son la misma enfermedad vista desde tres lados — el modelo carga TODO siempre (`selectin` + columnas gigantes en fila) y el trabajo pesado (PDF/Excel/ZIP) corre síncrono en el event loop. Arreglar PERF-001 + PERF-002 (defer de columnas + eager loading explícito) desinfla la mitad de los demás hallazgos de una.
