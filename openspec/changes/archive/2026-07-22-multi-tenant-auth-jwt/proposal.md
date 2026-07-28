## Why

Hoy el JWT hardcodea el rol del usuario en el momento del login (`create_access_token(user_id, username, rol)` en `app/core/security.py:73-116`, leyendo `Usuario.rol` global). La Fase 0 del feature multi-tenant ya introdujo en la base de datos la tabla `usuario_universidad` (membresía con **rol scopeado por universidad**), la tabla `universidades` y el flag `usuarios.es_superadmin`, pero **nadie los lee todavía**. Para que el rol dependa de QUÉ universidad está activa, el token tiene que dejar de portar el rol global y pasar a portar la **universidad activa + el rol en ESA membresía**, y el login tiene que resolver a qué universidad entra el usuario (una sola → directo; varias → selección en dos pasos).

> **Fase 1 de 6.** Segundo change de un feature multi-tenant grande, partido en un change por fase. **Depende de la Fase 0** (`multi-tenant-modelo-datos`, ya implementada y archivada en `openspec/changes/archive/2026-07-22-multi-tenant-modelo-datos/`): las tablas `universidades`/`usuario_universidad` y `usuarios.es_superadmin` ya existen con backfill hecho (cada usuario tiene 1 membresía en TUPaD con su rol viejo copiado). **Este change SOLO toca auth/JWT y el flujo de login.** NO toca `app/core/permissions.py` (Fase 2 — los guards `require_*` siguen leyendo `usuario.rol` global por convivencia, y con una sola universidad todo sigue funcionando), NI los services de Moodle (Fase 3), NI el scoping real de queries por `universidad_id` (Fase 4), NI el frontend (Fase 5), NI el cleanup de campos viejos (Fase 6).

## What Changes

- **`app/core/security.py` — nuevo payload del JWT**: `create_access_token` deja de recibir `rol` (que salía de `Usuario.rol`) y pasa a recibir `universidad_activa_id: int | None`, el `rol` **de esa membresía específica** y `es_superadmin: bool`. El payload gana `universidad_activa_id`, `rol` (de la membresía activa, no del usuario) y `es_superadmin`. `decode_token` sigue devolviendo el dict crudo; se documentan los nuevos campos y su opcionalidad.
- **`app/schemas/auth.py` — schemas del login en dos pasos**: `UserInfo.rol` deja de reflejar `Usuario.rol` y pasa a reflejar el rol en la universidad activa (mismo tipo `RolEnum`, nueva semántica). Nuevos schemas: `UniversidadDisponible` (`{id, nombre, rol}`), `SeleccionarUniversidadRequest` (`universidad_id`), y una **respuesta intermedia** de login (`requiere_seleccion: true` + `universidades: [...]`) cuando el usuario tiene 2+ membresías activas. La respuesta de token gana la universidad activa.
- **`app/core/dependencies.py` — nuevo dependency `get_universidad_activa`**: `get_current_user`/`get_current_user_optional` siguen devolviendo el `Usuario` sin cambios. Se agrega un dependency que resuelve `universidad_activa_id` desde el token y **valida que el usuario sea miembro activo** de esa universidad (`UsuarioUniversidad.activo=true`), devolviendo el contexto (universidad + rol de membresía). Falla 403 si el token no trae universidad o si la membresía dejó de estar activa.
- **`app/routers/auth.py` + `AuthService` — flujo de login en dos pasos** (la lógica vive en el service, no en el router; ARCH-001): 
  - `POST /auth/login`: resuelve membresías activas y ramifica — superadmin, 0 / 1 / 2+ universidades (ver `design.md`).
  - `POST /auth/select-universidad` (nuevo): tras un login que pidió selección, valida membresía activa y emite el token final con `universidad_activa_id` + rol.
  - `POST /auth/switch-universidad` (nuevo): re-emite el token con otra `universidad_activa_id`, validando membresía activa.
- **`app/repositories/usuario_repository.py`** (a confirmar en apply): método nuevo para traer las membresías activas de un usuario (con la universidad cargada), consumido por el `AuthService` — ningún service ejecuta SQLAlchemy directo (ARCH-001).
- **Retrocompatibilidad de tokens viejos**: los JWT ya emitidos (sin `universidad_activa_id`) siguen siendo válidos para `get_current_user` (que solo lee `user_id`); el design define la estrategia para el nuevo dependency `get_universidad_activa` cuando el token no trae universidad (ver `design.md`).

## Capabilities

### New Capabilities

- `jwt-universidad-activa`: El contrato del JWT multi-tenant — el payload porta `universidad_activa_id`, `rol` (de la membresía activa) y `es_superadmin`; la nueva firma de `create_access_token`/`decode_token`; y la regla de retrocompatibilidad de los tokens viejos sin universidad.
- `login-seleccion-universidad`: El flujo de login en dos pasos — resolución de membresías activas, ramas por cantidad de universidades y por `es_superadmin`, y los endpoints `POST /auth/login`, `POST /auth/select-universidad` y `POST /auth/switch-universidad` con sus validaciones y errores. Incluye los schemas del paso de selección.
- `dependency-universidad-activa`: El dependency `get_universidad_activa` que resuelve la universidad activa desde el token y valida la membresía activa del usuario en ella, exponiendo el contexto (universidad + rol de membresía) a los endpoints.

### Modified Capabilities

<!-- Ninguna a nivel de requisitos de spec. En particular, `autorizacion-por-pertenencia`
     (los guards require_*/verificar_acceso_* de permissions.py) queda DELIBERADAMENTE
     intacta: su refactor para leer el rol de la membresía activa es la Fase 2. En Fase 1
     los guards siguen leyendo `usuario.rol` global (convivencia), por lo que sus requisitos
     no cambian. El cambio de semántica de `UserInfo.rol` y de la forma de la respuesta de
     login pertenece a la nueva capability `login-seleccion-universidad`, no a una existente. -->

## Impact

**Backend — Core (auth):**
- `app/core/security.py` — `create_access_token` (nueva firma), `decode_token` (nuevos campos documentados)
- `app/core/dependencies.py` — nuevo dependency `get_universidad_activa` (sin tocar `get_current_user`/`get_current_user_optional`)

**Backend — Schemas:**
- `app/schemas/auth.py` — `UserInfo` (semántica de `rol`), nuevos `UniversidadDisponible`, `SeleccionarUniversidadRequest`, respuesta intermedia de login

**Backend — Routers / Services / Repositories:**
- `app/routers/auth.py` — endpoints `select-universidad` y `switch-universidad` nuevos; `login` modificado
- `app/services/auth_service.py` — resolución de membresías + emisión de token (2 pasos)
- `app/repositories/usuario_repository.py` — método para membresías activas (a confirmar en apply)

**Tests:**
- Tests de token (payload con universidad/rol/superadmin), de cada rama del login, de select/switch validando membresía, y de retrocompatibilidad de tokens viejos

**Fuera de alcance (fases posteriores, NO en este change):**
- `permissions.py` y sus puntos de uso (Fase 2) · services de Moodle (Fase 3) · scoping real de queries por `universidad_id` (Fase 4) · frontend / selector de workspace (Fase 5) · borrado de `usuarios.rol`/`moodle_*` (Fase 6)

**Decisiones abiertas que requieren decisión humana en el checkpoint** (ver `design.md` → Open Questions): el manejo del **superadmin sin membresías** y su recorrido por el flujo de selección/switch.
