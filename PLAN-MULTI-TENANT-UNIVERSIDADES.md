# 📋 Handoff: Multi-tenancy — soporte para múltiples Universidades

**Proyecto:** Active-IA
**Fecha:** 2026-07-22
**Para:** implementación (feature grande, multi-fase)
**Gobernanza (JR Stack):** CRÍTICA/ALTA — toca Auth, permisos y el modelo `Usuario`. NO implementar de corrido sin checkpoints; cada fase (ver más abajo) debería pasar por revisión antes de la siguiente.

> Este doc es 100% autocontenido. Quien lo lea en una sesión nueva sin ningún contexto previo debería poder arrancar a implementar solo con esto — pero **antes de escribir código, releer los archivos citados** para confirmar que las líneas/contenido no cambiaron desde el 2026-07-22.

---

## 🎯 Problema a resolver

Hoy Active-IA es **mono-tenant implícito**: existe UNA sola universidad (TUP/TUPaD) y eso está hardcodeado en el modelo de datos sin que exista el concepto explícito de "universidad". La prueba está en `Usuario`:

```python
# backend/app/models/usuario.py:70-73
# Credenciales Moodle (password cifrado con AES-256)
moodle_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
moodle_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
moodle_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

El **link del campus Moodle** (`moodle_host`) hoy lo configura cada TUTOR en su perfil individual (`app/routers/perfil.py`, `app/schemas/perfil.py`). Eso solo funciona porque hoy todos los tutores apuntan al mismo campus. En cuanto exista una segunda universidad, cada usuario necesitaría poder tener un host distinto por universidad — y el campus en sí (el link) debería ser una propiedad de la universidad, no algo que cada tutor tipea a mano y puede tipear distinto.

Además, el **rol** (`ADMIN`/`COORDINADOR`/`TUTOR`/`GESTOR`) es un campo único y global en `Usuario.rol` (`backend/app/models/enums.py:11-17`), y se lee así en **17 archivos** (routers, services, `app/core/permissions.py`). Si un usuario va a poder ser ADMIN en una universidad y TUTOR en otra, ese campo global ya no alcanza.

### Objetivo del feature

Introducir **Universidad** como entidad tenant de primer nivel, de forma que:
1. Un usuario puede pertenecer a **N universidades**, con un **rol distinto en cada una**.
2. El **link del campus Moodle** se configura a nivel Universidad (ya no por usuario).
3. Las **credenciales Moodle** (username/password) siguen siendo por usuario, pero ahora **por (usuario, universidad)** — un mismo usuario puede tener credenciales distintas en cada campus al que pertenece.
4. Existe un **admin global** (superadmin, ve/opera todas las universidades) y un **admin por universidad** (ve solo la suya).
5. Todo el árbol de datos (Materia → Comisión → Entrega → Corrección) queda **scopeado por universidad**.

---

## ✅ Decisiones ya tomadas (con el dueño del producto, 2026-07-22)

Estas NO son para re-discutir, son la base de la implementación:

| # | Pregunta | Decisión |
|---|----------|----------|
| 1 | ¿El rol es global o por membresía? | **Por membresía.** Un usuario puede ser ADMIN de la Universidad A y TUTOR de la Universidad B al mismo tiempo. |
| 2 | ¿Existe un admin global? | **Sí.** Hay un **admin global** (superadmin, todas las universidades) y un **admin por universidad** (solo ve/administra la suya). |
| 3 | ¿Cómo elige el usuario en qué universidad está trabajando? | **Selector de workspace** (como Slack cambiando de workspace) — solo se muestra si el usuario pertenece a 2+ universidades. |
| 4 | ¿`universidad_id` se agrega solo en `Materia` o se denormaliza en cascada? | **Se denormaliza.** `universidad_id` va también en Comisión, Entrega y Corrección (no solo derivarlo vía JOIN a Materia). |
| 5 | ¿Cómo migran los datos existentes? | Se crea una Universidad semilla llamada **"Tecnicatura Universitaria en Programación a Distancia" (TUPaD)** y TODAS las materias/usuarios/datos existentes se migran a esa universidad. |
| 6 | ¿La API Key de Gemini/OpenRouter se vuelve por universidad? | **No, se queda global del usuario** (no tiene relación con el campus Moodle). |

---

## 🧩 Modelo de datos propuesto

```
┌─────────────────────────┐
│      Universidad          │  ← NUEVA
│  id                       │
│  nombre (unique)          │
│  moodle_host              │  ← se muda desde Usuario
│  activa                   │
└───────────┬───────────────┘
            │ 1:N
            │
┌───────────▼───────────────┐        ┌──────────────────────────┐
│   UsuarioUniversidad       │  ← NUEVA (N:M con atributos)       │
│  id                        │        │        Usuario            │
│  usuario_id (FK)   ────────┼───────▶│  id                       │
│  universidad_id (FK)       │        │  username (sigue GLOBAL   │
│  rol (RolEnum, POR ESTA    │        │            único)         │
│       membresía)           │        │  es_superadmin  ← NUEVO   │
│  moodle_username           │        │  gemini_api_key_*         │
│  moodle_password_encrypted │        │  openrouter_api_key_*     │
│  activo                    │        │  correction_provider      │
│  UNIQUE(usuario_id,        │        │  (SIN rol, SIN moodle_*)  │
│         universidad_id)    │        └──────────────────────────┘
└────────────────────────────┘
```

```
Universidad (1) ──── (N) Materia.universidad_id           ← NUEVO FK
Materia (1)     ──── (N) Comision.universidad_id           ← NUEVO FK (denormalizado)
Comision (1)    ──── (N) Entrega.universidad_id            ← NUEVO FK (denormalizado)
Entrega (1)     ──── (N) Correccion.universidad_id         ← NUEVO FK (denormalizado)
```

### Detalle por tabla

**`universidades`** (nueva)
- `id`, `nombre` (String, unique), `moodle_host` (String, nullable — puede crearse la universidad antes de tener el campus configurado), `activa` (bool), timestamps.

**`usuario_universidad`** (nueva, junction table con atributos — mismo patrón que `CoordinadorMateria`/`ComisionTutor`)
- `id`, `usuario_id` FK → `usuarios.id`, `universidad_id` FK → `universidades.id`
- `rol`: `RolEnum` (ADMIN/COORDINADOR/TUTOR/GESTOR) — **scopeado a esta universidad**
- `moodle_username`, `moodle_password_encrypted` (mismo cifrado AES-256 que hoy)
- `activo`: bool
- `UniqueConstraint(usuario_id, universidad_id)`

**`usuarios`** (modificado)
- ➖ Se elimina `rol` (pasa a `UsuarioUniversidad.rol`)
- ➖ Se eliminan `moodle_username`, `moodle_password_encrypted`, `moodle_host` (pasan a `UsuarioUniversidad`/`Universidad`)
- ➕ Se agrega `es_superadmin: bool` (default `False`) — bypasea el scoping de universidad en todos los checks
- Se mantienen igual: `gemini_api_key_encrypted`, `openrouter_api_key_encrypted`, `gemini_api_key_valid`, `openrouter_api_key_valid`, `gemini_api_key_paga`, `correction_provider` (decisión 6)
- `username` **sigue siendo único global** (un usuario = una identidad, que luego se vincula a N universidades)

**`materias`** (modificado)
- ➕ `universidad_id` FK → `universidades.id`, NOT NULL (tras backfill)
- ⚠️ `codigo` **deja de ser unique global** (`backend/app/models/materia.py:37-42`) y pasa a `UniqueConstraint(universidad_id, codigo)` — dos universidades podrían tener ambas una materia con código "PROG1".

**`comisiones`, `entregas`, `correcciones`** (modificados)
- ➕ `universidad_id` FK NOT NULL en cada una (denormalizado, decisión 4). Debe coincidir siempre con el `universidad_id` de su Materia/Comisión padre — validarlo en la capa de servicio al crear el registro, no hace falta constraint cross-table en DB.

**⚠️ A revisar con la misma lógica de decisión 4** (no fueron mencionadas explícitamente por el usuario, pero cuelgan de Materia igual que Comisión): `Rubrica`, `Unidad`, `ExamenMateria`, y cualquier tabla de `cierre_cursada.py`/`avance.py`/`componente_unidad.py` que hoy tenga `materia_id`. Recomendación: aplicar el mismo criterio (denormalizar `universidad_id`) por consistencia, pero confirmarlo como parte de la Fase 0 antes de escribir la migración completa.

---

## 🔐 Auth / JWT — el corazón del cambio

Hoy el JWT se arma así (`backend/app/core/security.py:73-116`):

```python
def create_access_token(user_id: int, username: str, rol: str, ...) -> str:
    payload = {"user_id": user_id, "username": username, "rol": rol, "exp": ..., "iat": ...}
```

El `rol` va **hardcodeado en el token en el momento del login**. Con multi-tenancy esto ya no alcanza: el rol depende de QUÉ universidad está activa.

### Flujo de login propuesto

```
POST /auth/login (username, password)
         │
         ▼
  Resolver membresías activas del usuario (UsuarioUniversidad.activo=true)
         │
    ┌────┴─────────────────────────────────┐
    │                                       │
 es_superadmin=True              es_superadmin=False
    │                                       │
    ▼                                       ▼
 Token con modo "superadmin"      ¿Cuántas universidades tiene?
 (puede elegir CUALQUIER              │
  universidad para operar,     ┌──────┼──────┐
  ver "Decisiones abiertas"    │      │      │
  #2 más abajo)                0      1      2+
                                │      │      │
                             Error  Login   Response intermedio:
                             (sin   normal,  {requiere_seleccion: true,
                             uni)   token ya  universidades: [...]}
                                    con esa   → usuario elige →
                                    uni activa POST /auth/select-universidad
                                    + su rol   → emite el token final
                                    en ella    con universidad_activa_id + rol
```

### Cambios concretos

- **`app/core/security.py`**: `create_access_token` pasa a recibir `universidad_activa_id` y el `rol` **de esa membresía específica** (no `Usuario.rol`, que ya no existe), más un flag `es_superadmin`.
- **`app/schemas/auth.py`**: `UserInfo` pierde `rol` como campo fijo del usuario y pasa a reflejar el rol en la universidad activa; se agrega un nuevo request/response para el paso de selección de universidad (`SeleccionarUniversidadRequest`, con lista de universidades disponibles en el `LoginResponse` cuando aplica).
- **`app/core/dependencies.py`** (`get_current_user`, `get_current_user_optional`, líneas 55 y 155): siguen devolviendo el `Usuario`, pero hay que agregar una forma de resolver la universidad activa desde el token (nuevo dependency, ej. `get_universidad_activa`).
- **Endpoint nuevo**: `POST /auth/switch-universidad` (o similar) — re-emite el token con otra `universidad_activa_id`, validando que el usuario sea efectivamente miembro activo de esa universidad.
- **`app/core/permissions.py`** (17 puntos de uso de `RolEnum` en el repo, TODOS en este archivo o consumiéndolo): cada función (`require_admin`, `require_coordinador`, `require_tutor`, `require_gestor`, las combinadas, y los `verificar_acceso_*` que hoy hacen `if usuario.rol == RolEnum.ADMIN`) deja de leer `usuario.rol` y pasa a comparar contra el rol resuelto para la universidad activa del request — con un bypass total si `usuario.es_superadmin`.

---

## 🗄️ Migración de datos existentes

**Orden sugerido (Alembic, puede ser 1 o varias revisiones — recomendado varias, ver Fases):**

1. Crear tabla `universidades`.
2. Crear tabla `usuario_universidad`.
3. Agregar `universidad_id` **nullable** a `materias`, `comisiones`, `entregas`, `correcciones` (y las que se confirmen en la nota de arriba).
4. Agregar `usuarios.es_superadmin` (default `false`).
5. **Seed**: insertar la fila de Universidad `"Tecnicatura Universitaria en Programación a Distancia"` (nombre corto sugerido: `TUPaD`). El `moodle_host` real hay que sacarlo de la base de producción (revisar qué valor tienen hoy los usuarios en `usuario.moodle_host` — debería ser el mismo para todos, confirmarlo antes de asumirlo).
6. **Backfill**: `UPDATE materias SET universidad_id = <id_tupad>` → propagar a `comisiones` (vía `materia_id`), `entregas` (vía `comision_id`), `correcciones` (vía `entrega_id`).
7. **Backfill de membresías**: por cada `Usuario` existente, crear 1 fila en `usuario_universidad` con `universidad_id=<id_tupad>`, `rol=<el que tenía en usuario.rol>`, `moodle_username=<el que tenía>`, `moodle_password_encrypted=<el que tenía>`, `activo=true`.
8. **Decisión operativa manual** (no automatizable, no asumir nada acá — ver Decisiones abiertas #3): decidir a mano qué usuarios ADMIN existentes reciben `es_superadmin=true`.
9. Recién con todo backfilleado: pasar `universidad_id` a NOT NULL en las 4 tablas y agregar el `UniqueConstraint(universidad_id, codigo)` en `materias` (reemplazando el unique global de `codigo`).
10. **En una migración/PR aparte y posterior** (no en el mismo paso, dejar convivencia por seguridad — ver Fases): eliminar `usuarios.rol`, `usuarios.moodle_username`, `usuarios.moodle_password_encrypted`, `usuarios.moodle_host`.

---

## 🔧 Archivos a tocar (mapeados durante el análisis, 2026-07-22)

### Modelos
- ➕ `app/models/universidad.py` (nuevo)
- ➕ `app/models/usuario_universidad.py` (nuevo)
- `app/models/usuario.py` (`usuario.py:37-141`) — sacar `rol`/`moodle_*`, agregar `es_superadmin`, relationship a `UsuarioUniversidad`
- `app/models/materia.py` (`materia.py:36-46`) — agregar `universidad_id`, cambiar unique de `codigo`
- `app/models/comision.py`, `app/models/entrega.py`, `app/models/correccion.py` — agregar `universidad_id`
- Revisar: `app/models/rubrica.py`, `app/models/unidad.py`, `app/models/examen_materia.py`, `app/models/cierre_cursada.py`, `app/models/avance.py`, `app/models/componente_unidad.py`, `app/models/moodle_sync.py`

### Core (auth/permisos)
- `app/core/security.py` (`create_access_token`, `decode_token`)
- `app/core/dependencies.py` (`get_current_user`, `get_current_user_optional`)
- `app/core/permissions.py` (**archivo entero** — todas las funciones `require_*` y `verificar_acceso_*`)

### Schemas
- `app/schemas/auth.py`, `app/schemas/perfil.py`, `app/schemas/usuario.py`

### Repositories
- `app/repositories/usuario_repository.py`

### Services (leen `moodle_host`/`moodle_username`/`moodle_password` del usuario — 14 archivos detectados)
`app/services/moodle_service.py`, `gestion_service.py`, `cierre_cursada_service.py`, `por_entregar_service.py`, `moodle_import_service.py`, `snapshot_service.py`, `unidad_service.py`, `usuario_service.py`, `moodle_grade_service.py`, `rubrica_service.py`, `comision_service.py`, `materia_service.py`

### Routers
`app/routers/perfil.py`, `usuarios.py`, `materias.py`, `comisiones.py`, `rubricas.py`, `auth.py` — y sumar un router nuevo `universidades.py` (CRUD, solo superadmin)

### Migraciones
- Nueva(s) revisión(es) en `backend/alembic/versions/`

### Frontend (⚠️ NO explorado todavía en este análisis — hacerlo como primer paso de la Fase 5, no asumir nada de su estructura interna)
- Selector de workspace (componente nuevo, se muestra post-login si hay 2+ universidades)
- `features/auth` — manejar el login en 2 pasos
- `features/perfil` — credenciales Moodle pasan a estar scopeadas por universidad activa
- Pantalla nueva de administración de Universidades (solo superadmin)
- `shared/services/api` — verificar cómo viaja el token y si hace falta mandar algo adicional al cambiar de universidad

---

## 📐 Fases sugeridas (para no romper todo en un solo PR)

| Fase | Contenido | Riesgo | Nota |
|------|-----------|--------|------|
| 0 | Modelo de datos + migración completa (tablas nuevas, columnas nuevas, seed TUPaD, backfill) | Bajo — todo sigue funcionando igual porque hay 1 sola universidad | Confirmar antes las tablas de la lista "a revisar" |
| 1 | Auth/JWT: nuevo payload con `universidad_activa_id`, endpoint de selección/switch | Medio | Con 1 sola universidad el selector no se nota (auto-selecciona) |
| 2 | Refactor completo de `permissions.py` y sus 17 puntos de uso | **Alto** (CRÍTICO, es auth) | Requiere tests de regresión de permisos antes de tocar nada |
| 3 | Refactor de los 14 archivos que leen moodle_host/username/password del usuario → pasan a leerlo desde `UsuarioUniversidad`/`Universidad` de la universidad activa | Medio-Alto | Blast radius grande, ir archivo por archivo con tests |
| 4 | Scoping real de queries: Materia/Comisión/Entrega/Corrección filtran por `universidad_id` en repositories/services | Alto | Acá es donde se rompe el aislamiento si algo queda sin filtrar |
| 5 | Frontend: selector de workspace, pantalla CRUD de Universidades, perfil con moodle por universidad | Medio | Explorar frontend antes de tocar |
| 6 | Cleanup: recién acá borrar `usuarios.rol`/`moodle_*` viejos | Bajo, pero solo después de verificar en producción que nada los usa | |

Dado que el proyecto usa OpenSpec (`openspec/`), lo natural es partir esto en **varios `changes` de OPSX** (uno por fase, o agrupando 0+1, 2+3, 4, 5+6) en vez de un change gigante — mejor trazabilidad y checkpoints reales por fase.

---

## ❓ Decisiones abiertas para quien implemente

1. Si un superadmin no pertenece a ninguna fila de `usuario_universidad`, ¿puede igual operar (viendo todas) o necesita elegir explícitamente una universidad para trabajar?
2. El superadmin, ¿ve un dashboard con TODAS las universidades mezcladas, o también usa el selector de workspace pero con la opción de elegir cualquiera (no solo las suyas)?
3. Migración: **qué usuarios ADMIN existentes reciben `es_superadmin=true`** — es una decisión de negocio, tomarla a mano antes de correr el backfill, no asumir "todo ADMIN pasa a superadmin".
4. ¿`usuarios.rol`/`moodle_*` se borran en la misma migración que se crean las tablas nuevas, o conviven un tiempo como deprecated hasta verificar en producción? Recomendado: convivir hasta después de la Fase 4.
5. `Materia.moodle_course_id` y `Comision.moodle_group_id/code`: ¿necesitan alguna validación cruzada contra el `moodle_host` de su universidad al sincronizar? Revisar `moodle_service.py` en detalle en la Fase 3.
6. Frontend: no explorado — la sesión que implemente Fase 5 debe hacer su propia exploración de `features/auth` y `features/perfil` antes de tocar nada ahí.

---

## 🎓 Referencias

- `backend/app/models/usuario.py` — modelo actual con `rol`/`moodle_*` globales
- `backend/app/models/materia.py`, `comision.py`, `entrega.py`, `correccion.py` — cadena de entidades a scopear
- `backend/app/models/enums.py:11-17` — `RolEnum`
- `backend/app/core/permissions.py` — TODOS los guards de rol (archivo completo a refactorizar)
- `backend/app/core/security.py:73-116` — construcción actual del JWT
- `backend/app/core/dependencies.py:55,155` — `get_current_user`
- `backend/app/schemas/perfil.py`, `backend/app/schemas/auth.py` — schemas afectados
- `CLAUDE.md` (raíz del proyecto) — Clean Architecture, reglas de Routers/Services/Repositories a respetar durante la implementación
