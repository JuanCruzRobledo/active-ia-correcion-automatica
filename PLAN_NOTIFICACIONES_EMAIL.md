# PLAN — Notificaciones automáticas por email (Resend)

> Cron semanal que envía, sin intervención humana, el detalle de actividades faltantes
> a **alumnos**, **tutores académicos** y **tutores nexo**. Reusa el sistema de
> snapshots de avance ya existente. Rama: `feat/moodle-bidireccional`.

---

## 1. Problema y objetivo

Hoy cada alumno recibe **un email por materia** con lo que le falta → spam, ruido, nadie
lo lee. Queremos **consolidar** y **automatizar** en 3 envíos semanales, todo automático:

| # | Cron (semanal) | Destinatario | Entrega | Contenido |
|---|----------------|--------------|---------|-----------|
| 1 | Notif. alumnos | Cada **alumno** | **Tabla HTML en el cuerpo** | `Comisión / Materia / Actividad` — todas sus materias en una sola tabla |
| 2 | Notif. tutores académicos | Cada **tutor académico** | **PDF adjunto** | 1 hoja por materia; dentro, tablas `Comisión / Alumno / Actividades faltantes` apiladas por comisión |
| 3 | Notif. tutores nexo | Cada **tutor nexo** | **Excel adjunto** | Alumnos de su regional, **1 hoja por materia**, columnas `Comisión / Alumno / Actividades faltantes`, ordenado por comisión. (Excel y no PDF: una regional tiene cientos de alumnos → debe ser filtrable/ordenable) |

**Volumen estimado**: 900 alumnos × 4 cuatrimestres × 4 semanas ≈ **14.400** + ~230 tutores
+ 17 nexos ≈ **~15.388 emails/mes**. Vía **Resend** (plan pago, alto límite).

---

## 2. Decisiones cerradas (con el usuario)

| # | Tema | Decisión |
|---|------|----------|
| 1 | **Regional** | Se **deriva** del grupo Moodle `R-<nombre>` del alumno. Ya se parsea en `gestion_parser.resolver_grupos_alumno` — el snapshot la calcula y la descarta (`snapshot_service.py:162`). Solo falta **persistirla**. NO se crea ABM Regional. |
| 2 | **Tutor nexo** | Tabla **`TutorNexo`** independiente (`nombre`, `email`, `regional`, `activo`). No usa login/Usuario. |
| 3 | **Tutor académico** | Es el `Usuario` rol **TUTOR** existente. Se le **agrega campo `email`**. El vínculo a comisiones ya existe (`ComisionTutor`). |
| 4 | **Actividades faltantes** | **Regla condicional según atraso** (ver §4.4). Si está **atrasado** → lista los **números de unidad** pendientes (*"Falta Unidad 4 y 5"*). Si está **al día** y solo le faltan actividades de la unidad actual → lista las **actividades concretas** de esa unidad (*"Actividad de Cierre unidad 8"*). Si no le falta nada → la materia no aparece. |
| 5 | **Fuente de datos** | **Reusa el snapshot** existente, extendido para persistir `actividades_faltantes` (JSONB). El cron de email lee de la DB — **no** re-consulta Moodle 900 veces. |
| 6 | **Resend** | Plan **pago**. Batch API (hasta 100 emails/request) + throttle + **cola persistente** (`EnvioEmailLog`) con reintentos backoff. |
| 7 | **Cadencia** | **1 schedule** configurable desde admin (día de semana + hora, default **lunes 07:00**). Los 3 envíos **en cadena** tras refrescar snapshots. Patrón clonado de `SnapshotCronConfig` + `scheduler.py`. |
| 8 | **Formatos** | **Alumno**: tabla **HTML** en el cuerpo (sin adjunto). **Tutor académico**: **PDF** adjunto (volumen acotado, sus comisiones). **Tutor nexo**: **Excel** adjunto (regional entera → cientos de alumnos, debe ser filtrable). |

---

## 3. Qué se reutiliza (NO se construye de cero)

- **`PDFService` (reportlab)** — `backend/app/services/pdf_service.py`, ya en prod. Motor de PDF listo.
- **`APScheduler` + `SnapshotCronConfig`** — `core/scheduler.py`. Patrón de cron configurable desde DB.
- **Snapshots de avance** — `snapshot_service.py` ya trae alumnos de Moodle **con email** y el **completion por actividad** de cada uno.
- **`gestion_parser`** — ya deriva `(regional, comisión)` de los grupos Moodle (formato validado en spike T0).
- **`dashboard_excel.py` (openpyxl)** — molde directo para el **Excel del tutor nexo** (1 hoja por materia). Patrón "función pura → bytes".
- **`MateriaRepository.get_configuradas_dashboard()`**, `AvanceRepository.get_ultimo_snapshot()`.

---

## 4. Cambios de modelo de datos

### 4.1 Modificaciones a tablas existentes
- **`Usuario`** → `+ email: str | None` (String(150), nullable, index). Para tutores académicos.
- **`AvanceAlumno`** →
  - `+ regional: str | None` (String(120)) — dejar de descartar la que ya se parsea.
  - `+ actividades_faltantes: JSONB` — lista de `{cmid, nombre, unidad}` (la de cierre incompleta por unidad ≤ unidad_actual).

### 4.2 Tablas nuevas
- **`TutorNexo`**: `id`, `nombre`, `email` (unique), `regional` (String, matchea el nombre derivado de `R-…`), `activo`, timestamps. Soft delete (regla del proyecto).
- **`EnvioEmailLog`** (auditoría + cola): `id`, `tanda_id` (UUID de la corrida), `tipo` (enum), `destinatario_email`, `destinatario_ref` (str: moodle_user_id / tutor_id / regional), `asunto`, `estado` (enum), `resend_id` (str|None), `error` (text|None), `intentos` (int), `creado_en`, `enviado_en`.
- **`NotificacionCronConfig`** (singleton id=1, como `SnapshotCronConfig`): `usuario_id` (FK — credenciales Moodle para refrescar snapshots), `dia_semana` (0-6), `hora`, `minuto`, `activo`, `remitente` (str|None).

### 4.3 Enums nuevos (`models/enums.py`)
- `TipoNotificacionEnum`: `ALUMNO`, `TUTOR_ACADEMICO`, `TUTOR_NEXO`.
- `EstadoEnvioEnum`: `PENDIENTE`, `ENVIADO`, `ERROR`, `OMITIDO`.

### 4.4 Regla de "actividades faltantes" (condicional según atraso)

Por cada **materia** del alumno, con `U = materia.unidad_actual`:

1. Para cada unidad `n ∈ 1..U`: reunir sus actividades (con completion tracking) y marcar
   la unidad como **incompleta** si tiene ≥1 actividad en `state == 0`.
2. `unidades_pendientes = [n ∈ 1..U que están incompletas]`.
3. **Presentación**:
   - `unidades_pendientes` **vacío** → no le falta nada → **la materia se omite** de su email.
     (Si TODAS sus materias quedan vacías, el alumno **no recibe email**.)
   - Existe alguna pendiente **anterior** a `U` (`atrasado = any(n < U)`) → **modo `UNIDADES`**:
     se reporta `unidades_pendientes` como números → *"Falta Unidad 4 y 5"*.
   - La **única** pendiente es `U` (al día, solo le faltan actividades de la unidad en curso)
     → **modo `ACTIVIDADES`**: se listan las **actividades incompletas de `U`** con su nombre
     real de Moodle → *"Actividad de Cierre unidad 8"*.

> El cálculo es el mismo para los 3 destinatarios; cambia solo el agrupamiento/formato.
> Persistir en `AvanceAlumno.actividades_faltantes` (JSONB) la estructura ya resuelta:
> `{ "modo": "UNIDADES"|"ACTIVIDADES", "unidades": [4,5], "actividades": [{cmid, nombre, unidad}] }`
> — así el render solo formatea, sin volver a calcular.

> Migraciones Alembic **siempre dentro de Docker** (`docker compose -f docker-compose.local.yml`),
> nunca alembic suelto — regla dura del proyecto.

---

## 5. Arquitectura (Clean — Router → Service → Repository)

### 5.1 Lógica pura (testeable sin DB ni red)
- **`avance_mapper.calcular_actividades_faltantes(completion_statuses, secciones, cabeceras, unidad_actual)`** → dict `{modo, unidades, actividades}` siguiendo la **regla condicional de §4.4** (mide completitud **por unidad**, no solo la "unidad alcanzada" actual). Extender `calcular_avance_alumno` para devolverla también.
- **`notificacion_render.py`** (puro):
  - `construir_html_alumno(nombre, filas)` → `str` (tabla HTML inline + estilos inline para clientes de correo).
  - `construir_pdf_tutor_academico(tutor, materias_con_comisiones)` → `bytes` (reportlab, 1 página/materia).
  - `construir_excel_tutor_nexo(regional, materias_con_comisiones)` → `bytes` (**openpyxl**, 1 **hoja** por materia; reusa patrón de `dashboard_excel.py`).

### 5.2 Servicios
- **`EmailService`** (wrapper Resend): `enviar_batch(items)` con throttle (semáforo + tasa configurable), reintentos backoff ante 429/5xx, y **registro en `EnvioEmailLog`**. Lee `RESEND_API_KEY` de config.
- **`NotificacionService`** (orquestador):
  - `_destinatarios_alumnos()` — cruza los **últimos snapshots de todas las materias**, agrupa por `moodle_user_id`, arma filas `Comisión/Materia/Actividad`. Omite alumnos sin email (loguea).
  - `_destinatarios_tutores_academicos()` — por cada `Usuario` TUTOR con email → sus comisiones (`ComisionTutor`) → materias → alumnos de esas comisiones desde el último snapshot.
  - `_destinatarios_tutores_nexo()` — por cada `TutorNexo` activo → alumnos cuyo `regional` coincide, agrupados por materia (1 hoja Excel por materia).
  - `ejecutar_corrida_semanal(usuario_id)` — genera `tanda_id`; **(1)** `SnapshotService.generar_todas_para_usuario` (refresca datos) → **(2)** alumnos → **(3)** tutores académicos → **(4)** nexos. Idempotente por `tanda_id` (no re-envía lo ya `ENVIADO`).

### 5.3 Repositorios
- **`notificacion_repository.py`**: lecturas de agregación (avance por alumno / por comisiones / por regional sobre los últimos snapshots) + CRUD de `EnvioEmailLog`.
- **`tutor_nexo_repository.py`**: CRUD `TutorNexo` (soft delete).
- Reusar `avance_repository`, `materia_repository`, `usuario_repository`.

### 5.4 Routers
- **`tutores_nexo.py`** — ABM admin de `TutorNexo`.
- **`usuarios.py`** — agregar `email` a schema y endpoints.
- **`notificaciones.py`** — `GET/PUT /notificaciones/cron-config`; `POST /notificaciones/enviar-prueba` (a un email de test, sin tocar a todos); `POST /notificaciones/disparar` (manual, para QA); `GET /notificaciones/historial` (paginado de `EnvioEmailLog`); `GET /notificaciones/preview/{tipo}` (devuelve HTML / PDF / Excel de muestra **sin enviar**).

### 5.5 Scheduler
- Extender `core/scheduler.py`: job `"notificacion_semanal"` con `CronTrigger(day_of_week, hour, minute)`; `reprogramar_notificacion_desde_config()`; arrancar en startup junto al de snapshots.

### 5.6 Config
- `core/config.py`: `+ RESEND_API_KEY`, `+ EMAIL_REMITENTE` (default `onboarding@resend.dev`), `+ EMAIL_RATE_POR_SEGUNDO` (throttle).
- **Variables de entorno — DOS mecanismos distintos según entorno:**
  - **LOCAL (desarrollo, T0–T9)**: `.env` de la **raíz** (gitignored) → inyectado al backend por `docker-compose.local.yml` vía `environment: ${VAR}` (ya agregadas las 3 líneas). Levantar con `docker compose -f docker-compose.local.yml up -d backend`.
  - **PRODUCCIÓN**: deploy por **EasyPanel** (GitHub `main` + Build Path `/backend` + `backend/Dockerfile`, **sin docker-compose**). La `RESEND_API_KEY` (y `EMAIL_REMITENTE` si no se usa el default) se cargan **a mano en el panel "Environment" del servicio backend de EasyPanel**. `pydantic` las lee del entorno del contenedor igual que `DATABASE_URL`. Los `docker-compose.*.yml` **NO** intervienen en el backend de prod.
- `.env.example` (raíz): documentar las 3 vars nuevas (sin valores reales) — sirve de referencia para cargar en EasyPanel.
- **Sin dependencia nueva**: el envío usa `httpx` (ya instalado) contra `https://api.resend.com/emails`, mismo canal validado en T0. NO se agrega la lib `resend`.

### 5.7 Frontend
- Feature **`tutores-nexo/`** — ABM (types, service, hooks, form modal, page). Patrón `admin-crud-page`.
- **`UsuarioForm`** — agregar input `email`.
- Feature **`notificaciones/`** — pantalla config del cron (día/hora/usuario/activo) + historial de envíos (tabla con estado/error) + botón **"Enviar prueba"** + **preview** (HTML/PDF/Excel según tipo).
- `Sidebar` + `helpContent` + rutas. Tokens semánticos + dark mode (ya establecido).

---

## 6. Plan de tareas (TDD donde cuenta)

| T | Tarea | TDD | Verificación |
|---|-------|-----|--------------|
| **T0** ✅ | **Spike Resend + regionales reales** — `backend/scripts/spike_notificaciones_email.py`. **HECHO 2026-06-07**: (A) Resend sandbox OK (email aceptado, id devuelto). (B) Sobre curso 41: **826/826 alumnos con regional y comisión parseadas, 0 sin regional, 17 regionales distintas** (Villa María, Mendoza, Rosario, Córdoba, …) — coincide con las 17 esperadas. Parseo de regional/comisión validado sin fugas. | — | ✅ Email llegó · ✅ 17 regionales, 0 sin regional |
| **T1** ✅ | Modelos + enums + **migración**. **HECHO 2026-06-07**: enums TipoNotificacion/EstadoEnvio; Usuario.email; AvanceAlumno.regional + actividades_faltantes (JSONB); tablas tutores_nexo, envio_email_logs, notificacion_cron_config. Migración `42773c735505` (drift moodle_sync limpiado). Aplicada en Docker. | — | ✅ upgrade OK · 3 tablas + 2 enums + 3 columnas · modelos importan |
| **T2** ✅ | `avance_mapper.calcular_actividades_faltantes` (regla §4.4) + `calcular_avance_alumno` extendido + `snapshot_service` persiste `regional` + `actividades_faltantes`. **HECHO 2026-06-07** TDD: RED (ImportError) → GREEN (30/30 mapper, 6/6 snapshot) → triangulación 5 casos. Suite unit: 274 passed (3 errores de colección AJENOS pre-existentes: CriterioSchema/rubrica). | **Sí** (puro) | ✅ 30/30 mapper · 6/6 snapshot · casos atrasado/al-día/completo/nada/reprobada |
| **T3** ✅ | `EmailService` (Resend vía **httpx**, reintentos backoff 429/5xx, throttle en `enviar_lote`, opera mutando `EnvioEmailLog`). **HECHO 2026-06-07** TDD: RED→GREEN 7/7. Config RESEND_API_KEY/EMAIL_REMITENTE/EMAIL_RATE_POR_SEGUNDO en config.py. Suite unit: 281 passed. | **Sí** (mock `_post_resend`) | ✅ 7/7: éxito, 429→retry, 4xx no-retry, 5xx agota, idempotente, sin-key, adjuntos base64 |
| **T4** ✅ | `notificacion_render`: `formatear_faltantes` (texto §4.4) + **PDF** tutor académico (reportlab, 1 página/materia, tabla por comisión) + **Excel** tutor nexo (openpyxl, 1 hoja/materia, nombres sanitizados ≤31). **HECHO 2026-06-07** TDD 11/11. Suite unit: 292 passed. | Parcial | ✅ 11/11: formatear (6 casos), PDF %PDF válido, Excel n°hojas=n°materias + header + sanitización |
| **T5** ✅ | `notificacion_render.construir_html_alumno` (tabla HTML inline Comisión/Materia/Actividad, estilos inline, escape, mensaje "al día" si vacío). **HECHO 2026-06-07** TDD 6 casos. notificacion_render: 17/17. | **Sí** (puro) | ✅ 17/17: nombre+headers, 1 fila/materia, contenido, escape anti-inyección, estilos inline, sin-filas |
| **T6** ✅ | `notificacion_agg` (agregación PURA: alumno/comisión/regional, matchea tutor por `comision==moodle_group_code`, nexo por regional) + `NotificacionService` (carga repos, `ejecutar_corrida_semanal` idempotente por tanda) + repos `tutor_nexo` y `notificacion` (EnvioEmailLog) + `avance_repo.get_alumnos_de_snapshot`. **HECHO 2026-06-07** TDD: 10 agg + 4 service. Suite unit: 312 passed. ⚠️ `moodle_group_code` se carga a mano → comisión sin código no matchea (riesgo operativo, no de código). | **Sí** | ✅ 14/14: agrupación, omisión sin-email/sin-faltantes, idempotencia, 3 tandas, refrescar on/off |
| **T7** ✅ | CRUD `TutorNexo` (schema+service+router `/tutores-nexo` admin, registrado en main.py) + `email` en `Usuario` (UsuarioBase/Update/Response + usuario_service crear/actualizar). **HECHO 2026-06-07** 5 tests service. Suite unit: 317 passed; router registrado OK. | Parcial | ✅ 5/5: crear, 404, actualizar parcial, eliminar soft, email inválido |
| **T8** ✅ | Scheduler `notificacion_semanal` (CronTrigger day_of_week+hora, reprograma en caliente, enganchado al lifespan) + `NotificacionConfigService` + router `/notificaciones` (cron-config GET/PUT, disparar?refrescar, enviar-prueba, historial, preview/{tipo}). **HECHO 2026-06-07** 4 tests config. Suite unit: 321 passed; app levanta con rutas+scheduler OK. **Backend 100% funcional.** | Parcial | ✅ 4/4 config (defaults, activar sin-usuario→400, sin-moodle→400, OK persiste); rutas+scheduler verificados |
| **T9** ✅ | Frontend. **HECHO 2026-06-07**. Bloque 1: feature `tutores-nexo` (ABM admin) + `email` en UsuarioForm/types + ruta/sidebar/help. Bloque 2: feature `notificaciones` (config cron día/hora/usuario/remitente + enviar-prueba + preview HTML/PDF/Excel + disparar + historial) + ruta/sidebar/help. | — | ✅ `tsc -b` + `vite build` verde; eslint limpio en archivos nuevos (único error es deuda PRE-EXISTENTE de UsuarioForm:92, ajena) |
| **T10** | **Prueba end-to-end** con destinatarios de prueba (corrida completa contra dominio sandbox). | — | Los 3 emails llegan con contenido correcto; `EnvioEmailLog` consistente |

---

## 7. Throttling y entregabilidad (Resend, plan pago)

- **Batch API**: hasta 100 emails distintos por request → 14.400 alumnos ≈ **144 requests**.
- **Throttle** configurable (`EMAIL_RATE_POR_SEGUNDO`) + `asyncio.Semaphore`; backoff exponencial ante `429`/`5xx`.
- **Cola persistente**: cada destinatario se inserta `PENDIENTE` en `EnvioEmailLog`; el worker marca `ENVIADO`/`ERROR` con `resend_id`. Permite **reanudar** una corrida caída sin duplicar (idempotencia por `tanda_id` + estado).
- **Modo sandbox vs producción**:
  - **Desarrollo (T0–T9)**: `from: onboarding@resend.dev`, envíos solo a la casilla propia. **No requiere dominio verificado.** Suficiente para construir y probar todo.
  - **Producción (T10 + real)**: requiere **`active-ia.com` verificado** en Resend (registros DKIM/SPF/DMARC en GoDaddy). Cuando el dominio despierte, basta con cambiar `EMAIL_REMITENTE` en `.env` → cero código. Hasta entonces, los envíos masivos a alumnos reales quedan bloqueados por Resend (a propósito).

---

## 8. Riesgos y bordes

| Riesgo | Mitigación |
|--------|-----------|
| Alumno **sin email** en Moodle | Omitir + registrar `OMITIDO` en log |
| Alumno **sin grupo `R-`** (`Sin regional`) | No entra al PDF del nexo; se loguea para revisión |
| Tutor **sin email** cargado | Omitir + log; visible en historial |
| Mismo alumno en **varias materias** | Se agrupa por `moodle_user_id` (id global de Moodle) en el email del alumno |
| **Rate limit** Resend | Throttle + backoff + cola reanudable |
| Cron corre y **falla a mitad** | `tanda_id` + estado por destinatario → reanuda sin duplicar |
| **Privacidad** (datos de alumnos a tutores) | Es la función del tutor; sin datos sensibles extra. PDFs no se persisten en disco |
| Snapshot **desactualizado** | La corrida refresca snapshots ANTES de enviar (paso 1 de `ejecutar_corrida_semanal`) |

---

## 9.bis EXTENSIÓN — TP + Autoevaluación + Cierre por unidad (2026-06-07)

> Pedido del usuario: cada unidad pasa a tener **3 componentes** trackeados por separado,
> configurados **manualmente** por unidad. El reporte marca las **deudas** de cada uno.

### Decisiones
- **3 componentes por unidad** (cada uno = un cmid de Moodle, configurable, opcional):
  - **TP** (`assign`): estados Moodle 0 no entregado / 1 entregado / 2 aprobado / 3 desaprobado.
  - **Autoevaluación** (`quiz`): hecha / no.
  - **Actividad de cierre** (`feedback`): hecha / no.
- **Identificación: MANUAL** por unidad (en el ABM se elige cada cmid de la lista real de Moodle).
- **TP en deuda** ⟺ `state ∈ {0 (no entregado), 3 (desaprobado)}`. OK = {1 entregado, 2 aprobado}.
- **Autoeval/Cierre en deuda** ⟺ `state == 0` (no realizada). OK = {1,2,3}.
- **Avance/estado** (dashboard): unidad **alcanzada** = la más alta con **≥1** de los 3 componentes
  realizado (state ∈ {1,2,3}). Estado por delta vs `unidad_actual` (igual que hoy).
- **Reporte de deudas** (email/Excel): por cada unidad `1..unidad_actual`, listar lo que debe:
  *"TP Unidad 3 (desaprobado)", "Autoevaluación Unidad 5", "Cierre Unidad 8"*.

### Modelo de datos
- **`Unidad`**: `+ moodle_tp_cmid`, `+ moodle_autoeval_cmid`, `+ moodle_cierre_cmid` (Integer, nullable).
- **`AvanceAlumno.actividades_faltantes`** (JSONB) → nuevo formato:
  `{ "deudas": [ {"unidad": int, "tipo": "TP"|"AUTOEVAL"|"CIERRE", "estado": str} ] }`
  (None / sin deudas → no se reporta).

### Cálculo (`avance_mapper`)
- Por unidad, leer el state de cada cmid configurado.
- `unidad_alcanzada` = max unidad con ≥1 componente en {1,2,3}.
- `deudas` = por unidad ≤ unidad_actual, agregar TP (si 0/3), AUTOEVAL (si 0), CIERRE (si 0),
  solo de los componentes que estén configurados.
- Si una unidad no tiene ningún cmid configurado → se ignora (no genera deudas ni avance).

### ABM (backend + frontend)
- Backend: endpoint que liste las **actividades de Moodle de una unidad** (su rango de secciones,
  con cmid, nombre, modname) para poblar los selectores; PUT que guarde los 3 cmids por unidad.
- Frontend: en la config de unidades, por cada unidad, 3 selectores (TP / Autoeval / Cierre)
  con las actividades reales de esa unidad.

### Render
- `formatear_faltantes` → formatea las deudas: *"TP Unidad 3 (desaprobado), Autoevaluación Unidad 5, Cierre Unidad 8"*.
- HTML alumno / PDF tutor / Excel nexo: muestran las deudas (idealmente separando TP / Autoeval / Cierre).

### Tareas
| T | Tarea | TDD |
|---|-------|-----|
| **E1** ✅ | `Unidad` + 3 cmids (moodle_tp/autoeval/cierre_cmid) + migración `23e454a59b3f` (drift limpiado, aplicada). JSONB de `actividades_faltantes` cambia de contenido (sin migración). **HECHO 2026-06-07**. | — |
| **E2** ✅ | `avance_mapper` reescrito: `calcular_deudas_y_alcance` (3 componentes por cmid), nueva firma `calcular_avance_alumno(statuses, unidades_config, *, unidad_actual)`. snapshot_service ajustado (ya no usa secciones/cabeceras). TDD reescrito. | **Sí** |
| **E3** ✅ | Backend ABM: `GET /unidades/{id}/actividades` (lista actividades Moodle de la unidad) + `PUT /unidades/{id}/componentes` (guarda 3 cmids); UnidadResponse +cmids. Snapshot persiste deudas (JSONB). | Parcial |
| **E4** ✅ | `formatear_faltantes` reescrito (deudas agrupadas por unidad: "Unidad 3: TP (desaprobado), Autoevaluación · Unidad 5: Cierre"). HTML/PDF/Excel sin cambio (reciben string). TDD. | **Sí** |
| **E5** ✅ | Frontend: `UnidadComponentesEditor` (3 `Select` por unidad, carga actividades on-demand) + botón ⚙ por unidad en la config + indicador "n/3 comp.". types/service/hooks. Build verde. | — |
| **E7** ✅ | **TP por CALIFICACIÓN, no por seguimiento.** Muchos assign tienen `completion=0` (sin seguimiento de finalización) pero SÍ tienen nota "Aprobado/Desaprobado" → el TP daba falso "no entregado" (caso real: GALO, Prog3 C7, U4). Fix: `MoodleService.get_grade_items` (lee `gradereport_user_get_grade_items` → `{cmid: gradeformatted}`); `avance_mapper.estado_tp(texto)` → `aprobado`/`desaprobado`/`sin_nota` (chequea "desaprob" antes que "aprob"); `calcular_deudas_y_alcance/_actividades_faltantes/_avance_alumno` reciben `notas_tp` y miden el TP por nota (deuda si ≠ aprobado; alcance si aprobado **o** desaprobado). Autoeval/Cierre siguen por seguimiento. `snapshot_service` llama `get_grade_items` por alumno. TDD: mapper reescrito (`estado_tp` parametrizado + TP sin-nota/aprobado/desaprobado + integración) y snapshot mockea `get_grade_items`. Suite unit: **315 passed** (3 errores AJENOS). | **Sí** |
| **E6** ⏳ | Código listo. **Falta (usuario)**: configurar los 3 cmids por unidad en el ABM, **regenerar snapshots**, y disparar corrida QA. | — |

⚠️ **Carga manual**: hay que configurar 3 cmids × ~10 unidades × cada materia (1 sola vez).

### 9.bis F — Componentes DINÁMICOS por unidad (N de cualquier tipo, fuente elegible)

Reemplaza el modelo rígido de 3 cmids fijos por **N componentes dinámicos** por unidad.
Cada componente: `tipo` (TP/QUIZ/AUTOEVALUACION/CIERRE, solo etiqueta) + `moodle_cmid` +
`fuente` (**SEGUIMIENTO** por completion | **CALIFICACION** por nota). La lógica del
avance depende de la FUENTE, no del tipo. Caso disparador: Organización Empresarial
(varios quizzes + 1 autoeval, **sin TP ni cierre**) → se modela con los componentes que
tenga, sin casos especiales.

| T | Tarea | TDD |
|---|-------|-----|
| **F1** ✅ | Modelo `ComponenteUnidad` (unidad_id FK ON DELETE CASCADE, tipo, moodle_cmid, fuente, orden) + enums `TipoComponenteEnum`/`FuenteComponenteEnum`. Migración `d6352d492298` escrita a mano: crea enums + tabla, **convierte los 3 cmids existentes a filas** (TP→CALIFICACION, autoeval/cierre→SEGUIMIENTO) y dropea las columnas. Aplicada en Docker: 35 TP + 35 autoeval + 30 cierre migrados. | — |
| **F2** ✅ | `avance_mapper` reescrito a componentes dinámicos: `_evaluar_componente` (por fuente) → (realizado, deuda). Deuda CALIFICACION ≠ aprobado ("desaprobado"/"no entregado"); SEGUIMIENTO state 0 → "pendiente". `formatear_faltantes` aprende QUIZ y generaliza "(desaprobado)". TDD: 44/44 (mapper+render), casos nuevos quiz/seg, quiz/calif, varios del mismo tipo, unidad sin TP ni cierre. | **Sí** |
| **F3** ✅ | `snapshot_service` arma `unidades_config` desde `u.componentes` (fuente como string). `actividad_actual_desaprobada` = algún componente por calificación de la unidad alcanzada desaprobado. Test ajustado. | Parcial |
| **F4** ✅ | ABM backend: schema `ComponenteUnidadInput/Response`, `UnidadComponentesUpdate{componentes:[...]}`, `UnidadResponse.componentes`. `set_componentes_unidad` reemplaza el set (delete-orphan). `listar_actividades_unidad` ahora incluye actividades **evaluables sin seguimiento** (assign/quiz/feedback/…) con flag `tiene_seguimiento` (arregla el "no me salen los assign" de E7). Suite unit: **320 passed** + 3 ajenos. Backend arranca OK. | Parcial |
| **F5** ✅ | Frontend: `UnidadComponentesEditor` lista dinámica (agregar/quitar filas tipo+fuente+actividad), aviso si elegís actividad sin seguimiento midiéndola por seguimiento. types/service/hooks + indicador "n componentes". `npm run build` verde, eslint limpio. | — |
| **F6** ⏳ | Verificación. **Decisión cerrada**: CALIFICACIÓN con nota numérica = "tiene nota → realizado" (`estado_tp` ahora devuelve 'aprobado' ante cualquier nota presente; solo "-"/vacío es sin_nota; "desaprob" sigue ganando). Tests 323 passed. **Falta (usuario)**: configurar los componentes de Organización Empresarial (quizzes + autoeval, sin TP/cierre) en el ABM, regenerar snapshot y verificar contra la verdad. | — |

---

## 9. Definición de "hecho"

- [ ] Los 3 crons envían el contenido correcto al destinatario correcto, sin intervención.
- [ ] Config de día/hora/usuario editable desde el admin; reprogramación en caliente.
- [ ] Historial de envíos consultable (estado + error por destinatario).
- [ ] Preview de PDF/HTML sin enviar; botón "enviar prueba" a un email de test.
- [ ] `pytest` verde (sin romper los 4 errores de colección preexistentes, ajenos).
- [ ] Frontend: `tsc -b` + `eslint` + `build` en verde, con dark mode/tokens.
- [ ] Sin secretos en el repo (RESEND_API_KEY solo en `.env`, gitignored).
