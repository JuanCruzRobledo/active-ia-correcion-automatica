# HANDOFF — Integración Active-IA ↔ AI-Native

> **Para retomar el desarrollo en otra máquina sin perder contexto.**
> Última actualización: 2026-08-24 · Rama: `feat/integracion-ai-native` (pusheada)
>
> Leé las secciones 1, 2 y **5** antes de tocar una línea. La 5 es la que evita
> que se deshagan decisiones que costaron encontrar.

---

## 1. Arranque rápido

```bash
git checkout feat/integracion-ai-native
git pull

# Backend
cd backend
pip install -r requirements.txt
python -m pytest -q            # esperado: 2040 passed, 10 skipped

# Postgres local (para migraciones; los tests corren sobre SQLite)
docker compose -f docker-compose.local.yml up -d postgres
```

**Alembic necesita tres variables o no arranca** (el guard SEC-003 aborta con
`DEBUG=False` y secretos placeholder):

```bash
cd backend
export PYTHONPATH=. DEBUG=True \
  DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/active_ia_db"
alembic current      # esperado: 329ab4696e88 (head)
```

### Contexto del proyecto

- `CLAUDE.md` — reglas duras del proyecto (Clean Architecture, soft delete, máx
  500 LOC/archivo, permisos por endpoint).
- `CHANGES-AI-NATIVE.md` — roadmap de los 8 changes, con grafo de dependencias.
- `openspec/changes/<nombre>/` — cada change con `proposal.md`, `design.md`,
  `specs/` y `tasks.md`. **El `design.md` explica el PORQUÉ de cada decisión.**
- El pedido original del cliente: `active-ia-pedido-de-cambios.md` (lo mandaron
  ellos; no está en el repo, pedilo si hace falta).
- `Pedido-AI-Native-2026-08-20.pdf` — lo que hay que mandarles (ver §7).

---

## 2. Estado actual

Rama `feat/integracion-ai-native`, 6 commits sobre `origin/main`, **2040 tests
passing**.

| # | Change | Tasks | Estado |
|---|--------|:-----:|--------|
| 8 | `fix-detalle-entrega-500` | 15/20 | ✅ código listo |
| 3 | `trabajos-practicos-y-external-ref` | 39/42 | ✅ código listo |
| 4 | `api-escritura-trabajos-practicos` | 37/41 | ✅ código listo |
| 5 | `correccion-por-ejercicio-con-tests` | 41/50 | ✅ código listo |
| 2 | `motor-anti-falsos-positivos` | 27/48 | 🟡 bloques 1-4 de 6 |
| 1 | `nota-deterministica-penalizaciones` | 2/39 | ⏸ gate del coordinador |
| 6 | `cuenta-de-servicio-integracion` | 0/55 | ⏸ gate de aprobación |
| 7 | `anonimizacion-datos-alumno` | 0/46 | ⏸ gate de aprobación |

**La integración ya funciona de punta a punta**: el cliente puede publicar un TP
con sus ejercicios y rúbricas, y pedir que se corrija ejercicio por ejercicio
mandando el resultado de su sandbox.

### Endpoints nuevos

```
POST   /api/v1/trabajos-practicos/
PUT    /api/v1/trabajos-practicos/by-ref/{external_ref}      201 crea / 200 actualiza
GET    /api/v1/trabajos-practicos/by-ref/{external_ref}
POST   /api/v1/correcciones/ejercicios/{ejercicio_ref}/corregir
```

### Migraciones aplicadas

| Revisión | Qué |
|---|---|
| `56a1724602e2` | `trabajos_practicos`, `ejercicios`, `materias.external_ref`, `rubricas.ejercicio_id`, índice parcial de rúbricas |
| `329ab4696e88` | `comisiones.external_ref`, `materias.comision_integracion_id` |

---

## 3. Qué sigue, en orden

### Se puede hacer YA, sin esperar a nadie

1. **Bloques 5 y 6 del `motor-anti-falsos-positivos`** — restricciones de cátedra
   (bug 6) y frontend. Es lo único de código que no depende de nadie.

### Necesita aprobación tuya ANTES de escribir código

2. **`cuenta-de-servicio-integracion`** 🔴 CRÍTICA — su `tasks.md` arranca con un
   gate: aprobar las 7 decisiones del `design.md` y cerrar 4 open questions
   (vencimiento por defecto, si el permiso de corrección va separado del de
   escritura, límite de tasa, y **por qué canal se entrega la credencial**).
3. **`anonimizacion-datos-alumno`** 🔴 CRÍTICA — aprobar la decisión de fondo
   (anonimizar en vez de borrar) y 3 open questions.

### Necesita al coordinador

4. **`nota-deterministica-penalizaciones`** 🟠 ALTA — hay que correr
   `backend/scripts/diagnostico_nota_deterministica.py` contra un dump de
   producción y revisar el impacto. Ese script **ya está escrito y es read-only**.
   Dos preguntas que solo el coordinador contesta: ¿los descuentos van sobre la
   misma base o en cascada? ¿la nota puede bajar de 0?

---

## 4. Cómo trabajar en este repo (convenciones aprendidas)

- **Strict TDD**: red de seguridad (correr los tests que tocan el archivo) → RED →
  GREEN → triangular → refactor. Está en el `CLAUDE.md` global.
- **Commits**: `<tipo>(<scope>): <descripción en español>`. Scopes reales del
  repo: `correcciones`, `entregas`, `rubricas`, `api`, `multi-tenant`, `docs`.
- **Migraciones**: `docker compose -f docker-compose.local.yml` + las 3 env vars
  de §1. Probar siempre `upgrade → downgrade → upgrade`.
- **Los `tasks.md` se marcan a medida que se avanza**, y cuando algo NO se hace
  se escribe por qué en la propia línea (hay varios ejemplos ya).

### Trampas del entorno (perdí tiempo con las tres)

1. **`test_upload_size_limits.py` falla con `MemoryError`** cuando la máquina está
   cargada (Docker + browser + varias corridas). Es ambiental, no una regresión:
   pasa aislado. Nadie de este trabajo lo tocó.
2. **`npm run lint` tiene 70 problemas preexistentes** (66 errores, 4 warnings).
   No lo uses como gate binario: compará contra el baseline.
3. **Reemplazar texto con `\n` desde un heredoc de Python falla seguido** por el
   escapado. Para editar código con escapes, usá la herramienta de edición
   exacta, no `str.replace` desde un script.

---

## 5. Decisiones de arquitectura que NO hay que deshacer

**Esta es la sección importante.** Cada una costó encontrarla, y varias parecen
arbitrarias hasta que se entiende el porqué.

### 5.1 Un ejercicio es dueño de una `Rubrica` existente

El documento del cliente dibuja `ejercicio → rubrica` como si la rúbrica fuera
una estructura nueva. **No lo es.** La `Rubrica` de Active-IA ya tiene criterios
jerárquicos, subcriterios con peso, penalizaciones y condiciones de
desaprobación — es más expresiva que lo que manda el cliente.

Por eso el motor de corrección, el PDF, el historial y el frontend **no se
tocaron**. Duplicar el modelo de rúbrica habría significado duplicar los cuatro.

### 5.2 El índice de rúbricas es PARCIAL, y eso es el corazón del #3

`uq_rubrica_materia_tipo_numero_anio` era un `UniqueConstraint` total. Cuatro
ejercicios del mismo TP comparten `(materia_id, tipo, numero, anio)` → el
constraint rechazaba de la segunda rúbrica en adelante. **Hacía imposible el
nivel de ejercicio.**

Ahora es índice único parcial sobre `ejercicio_id IS NULL`: las rúbricas de
Moodle conservan idéntica unicidad, las de ejercicio quedan exentas.

### 5.3 `sqlite_where` además de `postgresql_where`

La convención del repo era solo `postgresql_where`, y sus propios tests admiten
que "el efecto real solo se ve contra Postgres". Pero la suite corre sobre
SQLite: sin `sqlite_where`, el índice se crea **total** en los tests y el caso
que justifica todo el change no se verifica de verdad.

### 5.4 `Materia.trabajos_practicos` NO lleva `lazy="selectin"`

Se lo puse por consistencia con sus hermanas y **rompió 25 tests**. Con
`selectin`, cada carga de una materia en toda la app dispara un SELECT extra
contra una tabla que ningún camino de Moodle lee. Este repo ya tiene media docena
de tickets PERF por exactamente eso.

### 5.5 `foreign_keys` explícito en `Materia.comisiones` / `Comision.materia`

Desde que `Materia` ganó `comision_integracion_id` hay **dos FKs** entre
`materias` y `comisiones`, y SQLAlchemy no puede inferir el join. Además
`use_alter=True` en esa FK, porque cierra un ciclo y sin eso no se pueden ordenar
las tablas para CREATE/DROP.

### 5.6 El `rubrica_id` de un ejercicio es estable de por vida

Los ejercicios se emparejan por `external_ref`, **nunca** por orden ni por
título. Las `Entrega` y las `Correccion` cuelgan de `rubrica_id`: si un push lo
rotara, las correcciones ya hechas quedarían colgando de una rúbrica que el
cliente ya no asocia a ese ejercicio. No da una nota floja — **corrige otra
cosa**, y nadie se entera.

Tiene tres tests, uno por cada forma de romperlo (republicar, reordenar,
renombrar).

### 5.7 `Rubrica` NO tiene `deleted_at`

Se da de baja con `activa = False` (`RubricaRepository.soft_delete`). Hay **dos
convenciones de baja lógica** conviviendo en el repo, y la cascada del ejercicio
es la costura donde se tocan. Se usa la de cada entidad; unificarlas es un change
aparte.

### 5.8 Los casos ocultos mal formados se RECHAZAN, no se limpian

Si llega un caso `es_publico: false` con `salida_esperada`, se responde 422
nombrando el ejercicio y el caso. Falla cuando el docente publica (barato) y no
con un alumno esperando. Y descartar en silencio dejaría al cliente creyendo que
su contrato se respeta mientras se le limpia el payload.

### 5.9 Evidencia: cita falsa DEGRADA, omisión solo se MIDE

**La decisión más delicada de todo el trabajo** (`correccion_evidencia.py`).

- Citó algo que no está en el código → afirmación falsa y comprobable → se
  degrada (mitad del peso, `WARNING`).
- **No citó nada → se mide, NO se degrada.**

Si degradáramos por omisión y el modelo dejara de emitir el campo —cambio de
versión, prompt más largo, lo que sea— **todas las notas se cortarían a la mitad,
en silencio y de golpe**. Un desastre causado por nosotros, no por los alumnos.

Degradar solo la cita falsa deja un hueco (el motor puede esquivar la
verificación omitiendo el campo), pero ese hueco es **medible** (`sin_cita` lo
cuenta, el log lo grita) y se arregla en el prompt. Entre un agujero medible y un
desastre silencioso, el agujero medible.

Y **degrada, no anula**: es una heurística textual, no un parser. Puede dar falso
negativo, y anular por un falso negativo desaprobaría a alguien por un error
nuestro.

### 5.10 `depende_de_ejecucion` es determinístico, NO va en el prompt

El cliente pidió: "con `compila: false`, no cierren criterios del tipo 'el
programa funciona'". Ponerlo en el prompt sería repetir **exactamente el bug 2**,
donde la rúbrica pedía una penalización del 30% y el motor aplicó 0%. De este
motor ya está medido que no honra reglas declaradas en su propia rúbrica.

Vive en `correccion_ejecucion.py`. Necesita un dato que solo la rúbrica tiene:
cuál criterio requiere que el programa corra. **Default `False`** — si nadie
marca, la garantía no aplica (y el log lo dice).

Lo que NO se fuerza importa igual: `compila: true` con `0/6` no fuerza nada. Es
la distinción que el cliente agregó el 19/08 — no compilar es un punto y coma,
compilar y fallar todo es un programa que corre y hace otra cosa.

### 5.11 `Materia.comision_integracion_id` — el hueco que el pedido no vio

`entregas.comision_id` es `NOT NULL` y AI-Native no tiene comisiones. Su
documento no lo menciona porque no ve nuestro modelo. Sin esto el endpoint no
puede persistir nada.

Se resolvió con una FK de configuración (un admin la setea una vez por materia) +
un `comision_external_ref` **opcional** en el cuerpo. **El contrato que su
cliente ya implementó no cambia.**

Alternativa descartada: volver nullable `entregas.comision_id`. Tabla caliente,
con índices y scoping multi-tenant; esa nullabilidad se paga para siempre.

### 5.12 Reuso de entrega, no 409

Si el alumno ya tenía entrega para ese ejercicio, se reusa y la corrección
anterior va al historial (CRUD-003, ya existía). Para el cliente, reintentar es
la misma llamada en vez de una rama nueva.

### 5.13 El autogenerate de Alembic arrastra drift — migraciones a mano

`alembic revision --autogenerate` en este repo trae, además de tus cambios, drift
preexistente entre los modelos y la base. **Dos de esas operaciones son
peligrosas**: recrea el FK de `moodle_sync` SIN su `ondelete='SET NULL'`, y
elimina el único `uq_universidades_nombre`.

Las dos migraciones de este trabajo se escribieron **a mano**. Ese drift es un
hallazgo aparte y merece su propio change.

### 5.14 `test_authz_cobertura` y el patrón B

Ese test exige que todo endpoint de correcciones/entregas/documentos invoque un
guard de pertenencia. `corregir_ejercicio` está en su allowlist **con
justificación escrita**: el guard corre en el service porque el recurso se
identifica por referencia externa opaca y hay que resolverlo para saber su
materia. Ponerlo en el router obligaría a resolver dos veces.

**Si agregás un endpoint y ese test falla, no lo metas en la allowlist sin
justificar.** Ese test existe porque hubo un bug real de 20 endpoints con guard
vacío (SEC-001/002/004).

---

## 6. Hallazgos de causa raíz (para no re-investigar)

| Bug del cliente | Causa real | Estado |
|---|---|---|
| **1** — descuenta por archivos que SÍ están | `Entrega.archivos_incluidos` existía en la base y **nunca llegaba al prompt** (cero referencias en `correccion_service.py` y `app/integrations/`) | ✅ arreglado |
| **2** — no aplica las penalizaciones | **No es desobediencia del modelo.** El backend decidió no aplicarlas: el docstring de `_penalizaciones_validas` dice *"no alteran la nota, son solo auditoría/display"*. El descuento vivía solo en el prompt | ⏸ módulo puro listo (`correccion_nota.py`), sin cablear, esperando el gate |
| **3** — el desglose no cierra con subcriterios | Misma causa: la invariante estaba declarada como instrucción de prompt y nunca se imponía | ⏸ igual que el 2 |
| **4 y 5** — presencia vs. vínculo, hardcodeo | Reconocimiento léxico sin verificación | 🟡 reducido (evidencia + reglas de juicio), **no eliminado**. La eliminación real la da el #5 con tests ejecutados |
| **6** — recomienda lo que la cátedra prohíbe | La rúbrica **no tiene dónde declarar una prohibición** | ❌ bloque 5 del #2, pendiente |
| `GET /entregas/{id}` → 500 | Dos defectos encadenados: acceso a `entrega.subido_por.id` sin chequear + schema con campos obligatorios sobre columnas nullable | ✅ arreglado |

### Hallazgos colaterales, sin arreglar

- **`verificar_acceso_rubrica` filtra existencia entre universidades**: un recurso
  de otra universidad da 403 y uno inexistente 404. Los guards nuevos de TP y
  ejercicio ya scopean por `universidad_id` y dan el mismo 404; el de rúbrica no
  se tocó (fuera de alcance).
- **`EntregaDetail` del frontend declara `correccion: CorreccionInfo | null`**,
  campo que el backend no devuelve. Inerte hoy porque nadie lo consume.
- **Este endpoint cayó tres veces por la misma clase de error** (campo obligatorio
  sobre columna nullable). Vale un change de barrido general de schemas.

---

## 7. Lo que hay que pedirle a AI-Native

Está todo en `Pedido-AI-Native-2026-08-20.pdf` (4 páginas, listo para mandar,
faltan completar dos datos: la fecha estimada y cuándo tienen la cuenta de
servicio).

Las tres que traban:

1. **La personería, por escrito.** Confirmaron de palabra que se puede continuar,
   pero el gate del #5 (task 8.1) pide el respaldo escrito: bloquea el despliegue
   con datos de alumnos reales, no la construcción.
2. **Que marquen `depende_de_ejecucion`** al publicar sus rúbricas. Sin eso, la
   garantía de `compila: false` **no aplica** — está construida y probada, pero
   necesita ese dato.
3. **Que confirmen el contrato** de escritura contra su doble HTTP
   (`tests/e2e/smoke/test_smoke_activeia_doble.py`, del lado de ellos) antes del
   deploy.

Y una corrección que hay que darles: **su §7.3 asume que el 409 de entregas keyea
por `(comision_id, rubrica_id, alumno_nombre)`. El índice real es
`(rubrica_id, alumno_nombre)`**, sin `comision_id`. La conclusión operativa que
sacaron es correcta; el dato, no.

---

## 8. Pendientes operativos (no son código)

- [ ] Marcar `depende_de_ejecucion` en las rúbricas del piloto.
- [ ] Configurar `Materia.comision_integracion_id` en las materias del piloto.
- [ ] Correr el diagnóstico del #1 contra un dump de producción.
- [ ] Cargar las restricciones de cátedra de Programación 1 (cuando esté el
      bloque 5 del #2).
- [ ] Reproducir los casos control del motor con una API key real y reportar el
      resultado **incluidos los que sigan fallando**.
- [ ] Definir el canal de entrega de la credencial de servicio (no mail, no chat).
- [ ] Declararle al cliente que la anonimización cubrirá la base viva, **no los
      respaldos históricos**.

---

## 9. Aparte: el fix de escalas de Moodle

`fix/escalas-moodle-por-campus` → **PR #30, mergeado el 2026-08-20**. No es parte
de la integración, pero sí del mismo período y conviene saberlo:

`MOODLE_SCALE_MAP` era global e indexado solo por `scale_id`, pero los `scale_id`
son **por instancia de Moodle** y cada universidad tiene la suya. El `5` de TUPaD
es "Aprobado/Desaprobado"; el `5` de FRM es "No satisfactorio / Satisfactorio /
Supera lo esperado". Un TP de FRM calificado contra la escala 5 mandaba **índice 1
para el que aprobaba**, que ahí significa "No satisfactorio". Invertido y en
silencio, sin que ningún guard saltara.

Ahora el mapa es por `(host, scale_id)`. Pendiente: `campustest` es el campus de
**prueba** — el de producción de FRM va a necesitar su propia entrada, y hasta
entonces falla con error claro en vez de calificar mal.
