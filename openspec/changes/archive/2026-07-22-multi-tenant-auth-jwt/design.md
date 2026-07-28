## Context

Active-IA arrastra el rol del usuario en el JWT desde el login. Hoy (`app/core/security.py:73-116`):

```python
def create_access_token(user_id, username, rol, expires_delta=None) -> str:
    payload = {"user_id": user_id, "username": username, "rol": rol, "exp": ..., "iat": ...}
```

y el `AuthService.authenticate` (`app/services/auth_service.py:101-119`) lo llena con `user.rol.value` y devuelve `UserInfo(rol=user.rol, ...)`.

La **Fase 0** (`multi-tenant-modelo-datos`, archivada) ya dejó en la base, con backfill hecho:

- Tabla `universidades` (`id`, `nombre` unique, `moodle_host` nullable, `activa`). Modelo `app/models/universidad.py`.
- Tabla `usuario_universidad` (`usuario_id`, `universidad_id`, `rol: RolEnum` **scopeado a la membresía**, `moodle_username`, `moodle_password_encrypted`, `activo`, `UniqueConstraint(usuario_id, universidad_id)`). Modelo `app/models/usuario_universidad.py`. La relationship `Usuario.universidades` existe pero con `lazy="raise"` (nada la lee aún en Fase 0).
- `usuarios.es_superadmin` (Boolean, NOT NULL, default false). **`usuarios.rol` y `usuarios.moodle_*` SIGUEN EXISTIENDO** (convivencia; se borran en Fase 6).
- Backfill: cada usuario tiene exactamente 1 membresía activa en TUPaD con su `rol` viejo copiado.

Contratos verificados sobre el código (2026-07-22):

- `get_current_user` (`app/core/dependencies.py:58-124`) solo lee `payload["user_id"]`, carga el `Usuario` vía `UsuarioRepository.get_by_id_light` y valida `activo`. **No lee `rol` del token.** `get_current_user_optional` (líneas 158-221) igual.
- `AuthService` ya cumple ARCH-001: no ejecuta SQLAlchemy directo, usa `UsuarioRepository`. El repo tiene `get_by_username`, `get_by_id`, etc., pero **ningún** método para traer membresías `usuario_universidad`.
- JWT con `python-jose` (HS256, `settings.SECRET_KEY`). `ACCESS_TOKEN_EXPIRE_DAYS` default 7.

**Gobernanza: CRÍTICA** (auth/JWT). El patrón del proyecto es **proponer artefactos y esperar aprobación humana línea por línea antes de escribir código**. Este change entrega solo artefactos OpenSpec.

## Goals / Non-Goals

**Goals:**

- Que el JWT porte `universidad_activa_id`, el `rol` **de esa membresía** y `es_superadmin`, en lugar del `rol` global del usuario.
- Nueva firma de `create_access_token` y campos documentados en `decode_token`.
- Un dependency `get_universidad_activa` que resuelva la universidad activa del token y **valide membresía activa**.
- Login en dos pasos: `POST /auth/login` (con ramas), `POST /auth/select-universidad`, `POST /auth/switch-universidad`.
- Schemas nuevos para la selección de universidad y la respuesta intermedia de login.
- Retrocompatibilidad definida para los tokens viejos ya emitidos.
- Mantener ARCH-001: la resolución de membresías y la emisión de tokens viven en el `AuthService`, leyendo membresías vía repositorio.

**Non-Goals (fases posteriores, NO en este change):**

- Tocar `app/core/permissions.py` y sus `require_*`/`verificar_acceso_*`; el bypass real de `es_superadmin` en permisos (Fase 2). En Fase 1 los guards siguen leyendo `usuario.rol` global (convivencia) — con una sola universidad, idéntico comportamiento.
- Refactor de los services que leen `moodle_*` del usuario (Fase 3).
- Scoping de queries por `universidad_id` (Fase 4).
- Frontend / selector de workspace (Fase 5) — este change entrega SOLO el backend de los dos pasos.
- Borrar `usuarios.rol`/`moodle_*` (Fase 6).
- API key Gemini/OpenRouter: sigue global del usuario (decisión de producto #6), no se toca.

## Decisions

### D1 — Nuevo payload del JWT

El payload pasa a:

```python
{
  "user_id": int,
  "username": str,
  "rol": str | None,               # rol EN la universidad activa (RolEnum.value), NO Usuario.rol
  "universidad_activa_id": int | None,
  "es_superadmin": bool,
  "exp": ..., "iat": ...,
}
```

- `rol` sigue existiendo con el **mismo nombre de clave** (minimiza el blast radius: cualquier lector futuro del token sigue encontrando `rol`), pero su **significado** cambia: es el rol de la membresía activa, no el global. En Fase 1 nadie lo lee desde el token para autorizar (permissions.py sigue con `usuario.rol`); se deja poblado para que Fase 2 lo consuma.
- `universidad_activa_id` y `es_superadmin` son nuevos.
- `rol` y `universidad_activa_id` son `None` únicamente en el **modo superadmin-sin-universidad-elegida** (ver D6/Open Questions). En el flujo normal siempre van poblados.

**Alternativa considerada:** renombrar `rol`→`rol_membresia` para dejar explícito el cambio de semántica. Descartada: rompería innecesariamente a cualquier consumidor del claim y complica la retrocompat; el cambio de semántica se documenta en el spec.

### D2 — Firma de `create_access_token`

```python
def create_access_token(
    user_id: int,
    username: str,
    *,
    rol: str | None,
    universidad_activa_id: int | None,
    es_superadmin: bool,
    expires_delta: timedelta | None = None,
) -> str:
```

- Se elimina el parámetro posicional `rol: str` actual y se reemplaza por los tres campos multi-tenant como **keyword-only** (`*`), para que ninguna llamada vieja posicional compile silenciosamente con el argumento equivocado — cualquier caller desactualizado falla ruidoso en los tests.
- `decode_token` **no cambia de firma** (sigue devolviendo el dict crudo); solo se actualiza su docstring para documentar `universidad_activa_id`, `rol` (de la membresía) y `es_superadmin`, y que pueden faltar en tokens viejos (ver D5).

**Alternativa considerada:** un objeto `TokenClaims` tipado que envuelva el payload. Bueno a futuro, pero excede la Fase 1 y tocaría a todos los lectores de `decode_token`; se difiere.

### D3 — Dependency `get_universidad_activa`

Nuevo dependency en `app/core/dependencies.py`, **sin tocar** `get_current_user`/`get_current_user_optional`. Depende de `get_current_user` (reusa toda la validación de usuario ya existente) y del token:

```python
async def get_universidad_activa(
    credentials = Depends(security),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContextoUniversidad:   # {universidad_id, rol, es_superadmin, universidad}
```

Comportamiento:

1. Decodifica el token y lee `universidad_activa_id`.
2. Si falta (`None`) → **retrocompat / superadmin sin universidad**: ver D5 y D6.
3. Si viene: valida vía repositorio que exista una membresía **activa** `(current_user.id, universidad_activa_id)`. Si no existe o `activo=false` → **403** ("No sos miembro activo de esta universidad" / "Tu acceso a esta universidad fue revocado").
4. Devuelve un contexto ligero (dataclass/Pydantic interno) con `universidad_id`, el `rol` de la membresía y `es_superadmin`, para que el endpoint que lo pida no tenga que re-resolver.

Este dependency es **opt-in por endpoint**: en Fase 1 no se aplica a los endpoints existentes (eso es Fase 2/4). Se entrega listo para que las fases siguientes lo usen, y se cubre con tests.

**Nota:** el `rol` de membresía se toma de la **base** (re-validado contra `usuario_universidad`), no del claim del token, para que revocar/cambiar una membresía tenga efecto sin esperar la expiración del token. El claim `rol` del token queda como dato informativo/compatibilidad.

### D4 — Schemas nuevos (`app/schemas/auth.py`)

- `UniversidadDisponible`: `{ id: int, nombre: str, rol: RolEnum }` — una opción del selector.
- `SeleccionarUniversidadRequest`: `{ universidad_id: int }` — body de `select`/`switch`.
- Respuesta de login en dos formas (unión discriminada por `requiere_seleccion`):
  - **Directa** (0/1 universidad resuelta, o superadmin): la actual `TokenResponse` extendida con la universidad activa dentro de `UserInfo`.
  - **Selección requerida**: `{ requiere_seleccion: true, universidades: list[UniversidadDisponible] }`, **sin** `access_token` todavía.
- `UserInfo`: `rol` pasa a ser el rol en la universidad activa (`RolEnum | None`; `None` solo en superadmin-sin-universidad). Se agrega `universidad_activa_id: int | None` y `es_superadmin: bool`.

Para no romper el `response_model` fijo del endpoint, `POST /auth/login` usa un modelo unión (`LoginResponse = TokenResponse | SeleccionRequeridaResponse`) o `response_model=None` con retorno tipado — se decide en apply; el spec fija el contrato de datos, no la mecánica Pydantic.

### D5 — Retrocompatibilidad de tokens viejos

Los JWT emitidos antes de este change **no** traen `universidad_activa_id`/`es_superadmin`. Decisión:

- **Siguen siendo válidos para autenticación** (`get_current_user` solo usa `user_id` → no se rompe ninguna sesión activa). No se fuerza un re-login masivo.
- Para `get_universidad_activa` (dependency nuevo, aún no montado en endpoints en Fase 1): si el token no trae `universidad_activa_id`, hace **fallback de auto-resolución**: si el usuario tiene **exactamente 1** membresía activa, la usa (equivale al caso "1 universidad" del login); si tiene 0 o 2+, responde **409/403** "Reautenticá para elegir universidad" (`requiere_reautenticacion`). Con el estado post-Fase-0 (todos con 1 sola membresía en TUPaD) este fallback resuelve el 100% de los tokens viejos sin fricción.
- No se cambia `ACCESS_TOKEN_EXPIRE_DAYS`: los tokens viejos expiran naturalmente (≤7 días) y a partir de ahí todos portan el nuevo claim. No hace falta invalidación explícita ni versionado del token en esta fase.

**Alternativa considerada:** bumpear una versión de claim (`ver`) e invalidar todo token sin ella. Descartada por innecesaria: el fallback de 1-membresía cubre el período de convivencia y evita desloguear a todos.

### D6 — Superadmin (ver Open Questions 1 y 2 para la decisión humana)

El backend contempla que un superadmin pueda no tener filas en `usuario_universidad`. La forma del token y del flujo depende de dos preguntas abiertas que **el humano decide en el checkpoint**; el design deja la recomendación y una implementación por defecto que se puede confirmar o cambiar sin re-arquitectura:

- **Token "modo superadmin"**: `es_superadmin=true`, `universidad_activa_id=None`, `rol=None` mientras el superadmin no elija una universidad para operar. Al elegir una (vía `select`/`switch`), el token pasa a llevar esa `universidad_activa_id` y un `rol` **sintético** `ADMIN` para esa universidad (recomendación de la OQ2), incluso si no tiene membresía real.
- `get_universidad_activa`, para un superadmin, **no exige membresía**: acepta cualquier `universidad_activa_id` que exista y esté `activa` (bypass de la validación de membresía, coherente con que Fase 2 le dará bypass total de permisos).

### D7 — Repositorio de membresías (ARCH-001)

Se agrega a `UsuarioRepository` (o a un `UsuarioUniversidadRepository` nuevo si se prefiere aislar) un método:

```python
async def get_membresias_activas(self, usuario_id: int) -> list[UsuarioUniversidad]:
    # SELECT ... JOIN universidades WHERE usuario_id=? AND usuario_universidad.activo AND universidades.activa
```

que carga la `Universidad` asociada (para exponer `nombre` en `UniversidadDisponible`). El `AuthService` lo consume; **nunca** ejecuta el SELECT directo. Se agrega también `get_membresia(usuario_id, universidad_id)` para validar en `select`/`switch`/`get_universidad_activa`. La relationship `Usuario.universidades` es `lazy="raise"`, así que estas cargas se hacen con `select(...).options(selectinload(...))` explícito en el repo, no navegando el objeto.

## Flujo de los 3 endpoints

### `POST /auth/login` (username, password)

Tras validar credenciales / lockout (lógica actual intacta), resolver `membresias = get_membresias_activas(user.id)` y ramificar:

| Condición | Resultado | Token |
|---|---|---|
| `es_superadmin = true` | **200** token modo superadmin | `universidad_activa_id=None`, `rol=None`, `es_superadmin=true` (ver OQ1: se puede pedir que además elija) |
| `es_superadmin = false` y `len(membresias) == 0` | **403** "Usuario sin universidad asignada. Contactá al administrador." | — (no se emite) |
| `es_superadmin = false` y `len(membresias) == 1` | **200** login normal | token con esa `universidad_activa_id` + su `rol` en ella |
| `es_superadmin = false` y `len(membresias) >= 2` | **200** respuesta intermedia `{requiere_seleccion: true, universidades: [{id,nombre,rol}...]}` | — (aún no se emite token) |

Errores previos sin cambios: **401** credenciales inválidas, **403** cuenta deshabilitada/bloqueada.

### `POST /auth/select-universidad` (universidad_id)

Segundo paso tras un login que devolvió `requiere_seleccion`. Requiere identificar al usuario del paso 1 — **decisión de apply** entre: (a) un token de transición corto emitido en el login (recomendado; `scope=seleccion`, sin `universidad_activa_id`, expiración corta), o (b) re-enviar credenciales. El spec fija el contrato de validación, no el portador de identidad.

- Valida que exista membresía **activa** `(usuario, universidad_id)`. Si no → **403** "No sos miembro activo de esa universidad".
- Superadmin: acepta cualquier universidad `activa` aunque no tenga membresía (rol sintético ADMIN — OQ2).
- Éxito → **200** emite el **token final** con `universidad_activa_id` + rol de membresía + `es_superadmin`, y el `UserInfo` correspondiente.

### `POST /auth/switch-universidad` (universidad_id)

Cambia la universidad activa de una sesión **ya autenticada** (`Depends(get_current_user)`).

- Valida membresía **activa** `(current_user, universidad_id)`. Si no → **403**.
- Superadmin: cualquier universidad `activa` (rol sintético ADMIN — OQ2).
- Éxito → **200** re-emite el token con la nueva `universidad_activa_id` + rol. El token anterior sigue técnicamente válido hasta expirar (JWT stateless); es aceptable en Fase 1 (no hay blacklist), se documenta como trade-off.

## Risks / Trade-offs

- **[Cambio de semántica del claim `rol` sin renombrarlo]** → un lector podría asumir que es el rol global. Mitigación: en Fase 1 el único emisor/lector nuevo es el `AuthService`/`get_universidad_activa`; `permissions.py` sigue con `usuario.rol` (objeto, no token). Se documenta en el spec.
- **[Firma de `create_access_token` cambia]** → todo caller debe actualizarse. Mitigación: keyword-only fuerza fallo ruidoso en tests; el único caller productivo hoy es `AuthService.authenticate`.
- **[JWT stateless: el token viejo sigue válido tras `switch`]** → una sesión podría seguir operando con la universidad anterior hasta expirar. Mitigación: aceptable en Fase 1 (con 1 universidad no se nota); una blacklist/rotación se evalúa si Fase 2+ lo requiere.
- **[Superadmin con rol sintético ADMIN]** → le da poder de ADMIN en una universidad donde no es miembro. Mitigación: es exactamente la intención del superadmin (bypass global); el gating real vive en Fase 2. Queda como OQ para confirmación.
- **[Token de transición para `select`]** → si se opta por él, es un nuevo tipo de token de vida corta. Mitigación: expiración corta y `scope` explícito; se cubre con tests. Alternativa (re-enviar credenciales) evita el token pero empeora UX.
- **[`lazy="raise"` en `Usuario.universidades`]** → navegar la relationship sin `selectinload` explícito rompe. Mitigación: el repo usa carga explícita; es una red de seguridad, no un problema.
- **[Fallback de retrocompat con 2+ membresías]** → un token viejo de un usuario multi-universidad (no existe hoy post-Fase-0, pero podría crearse manualmente) caería en `requiere_reautenticacion`. Mitigación: es el comportamiento correcto (no adivinar la universidad); se documenta.

## Migration Plan

No hay migración de base de datos en esta fase (la estructura la trajo Fase 0). El "despliegue" es de código:

1. Cambiar `create_access_token` y actualizar su único caller (`AuthService.authenticate`) en el mismo commit (evita un estado intermedio roto).
2. Agregar `decode_token` docs, el dependency, los schemas, el método de repo y los endpoints.
3. Tokens viejos: sin acción — expiran en ≤7 días; el fallback de D5 los cubre mientras tanto.
4. **Rollback**: revertir el commit restaura la firma vieja y el login de un paso; los tokens nuevos (con claims extra) siguen siendo decodificables por el código viejo (claims extra se ignoran), así que un rollback no invalida sesiones. Sí se perdería la universidad activa hasta el próximo login — aceptable.

## Open Questions

**RESUELTAS (checkpoint 2026-07-22, decisión del dueño del producto).** Ambas Open Questions se cerraron con la recomendación por defecto de D6. Se dejan documentadas con la decisión final para trazabilidad; la implementación (apply) las sigue al pie de la letra.

1. **Superadmin sin ninguna membresía en `usuario_universidad`: ¿opera igual o debe elegir una universidad explícitamente?**
   - **DECISIÓN: opera igual.** El login de un superadmin devuelve **200** con token "modo superadmin" (`universidad_activa_id=None`, `rol=None`, `es_superadmin=true`) aun sin membresías, y `get_universidad_activa` **no** le exige membresía. Puede además elegir/switchear a cualquier universidad activa cuando quiera operar dentro de una (para acciones scopeadas). El caso "0 universidades activas = 403" aplica SOLO a no-superadmins.
   - Motivo: el superadmin es global por definición; obligarlo a tener una membresía "de mentira" en cada universidad ensuciaría `usuario_universidad` y contradice el sentido del flag.

2. **Superadmin y el flujo de selección/switch: ¿usa los mismos `select`/`switch` pudiendo elegir CUALQUIER universidad? ¿El token lleva un `rol` sintético o un modo especial?**
   - **DECISIÓN: mismos endpoints, universo ampliado + `rol` sintético `ADMIN`.** El superadmin usa `select-universidad`/`switch-universidad` igual que todos, pero la validación de membresía se **omite solo para superadmin** (puede elegir cualquier universidad `activa`, no solo las suyas). El token resultante lleva `universidad_activa_id` + `rol="ADMIN"` **sintético** para esa universidad + `es_superadmin=true`.
   - `es_superadmin` sigue siendo la **fuente de verdad** del bypass; el `rol` sintético es solo para dar **uniformidad al claim** (siempre presente cuando hay universidad activa), lo que simplifica el consumo en Fase 2.
