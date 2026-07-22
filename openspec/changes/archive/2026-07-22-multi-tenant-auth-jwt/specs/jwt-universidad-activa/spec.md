## ADDED Requirements

### Requirement: El JWT porta la universidad activa, el rol de esa membresía y el flag superadmin

El sistema SHALL emitir el JWT de acceso con un payload que incluya, además de `user_id`, `username`, `exp` e `iat`: `universidad_activa_id` (int, la universidad en la que el usuario está operando), `rol` (string del `RolEnum` correspondiente al rol del usuario **en esa universidad activa** — NO el rol global `usuarios.rol`) y `es_superadmin` (bool). El claim `rol` SHALL conservar su nombre de clave pero su valor SHALL provenir de la membresía activa (`usuario_universidad.rol`), no de `usuarios.rol`.

Los claims `universidad_activa_id` y `rol` SHALL poder ser `null` ÚNICAMENTE en el modo superadmin sin universidad elegida; en cualquier login o selección de un usuario no-superadmin SHALL ir poblados.

#### Scenario: Login de usuario con una universidad emite token con universidad y rol de esa membresía

- **WHEN** un usuario no-superadmin con exactamente una membresía activa (rol TUTOR en la universidad U) inicia sesión
- **THEN** el JWT emitido SHALL contener `universidad_activa_id` = id de U
- **THEN** el claim `rol` del JWT SHALL ser `"TUTOR"` (el rol de la membresía), aunque `usuarios.rol` tuviera otro valor
- **THEN** el claim `es_superadmin` SHALL ser `false`

#### Scenario: El claim rol refleja la membresía, no el rol global

- **WHEN** un usuario tiene `usuarios.rol = ADMIN` (viejo, global) pero su membresía activa en la universidad seleccionada es `COORDINADOR`
- **THEN** el claim `rol` del JWT SHALL ser `"COORDINADOR"`

#### Scenario: Token de superadmin sin universidad elegida

- **WHEN** un superadmin inicia sesión y aún no elige universidad
- **THEN** el JWT SHALL contener `es_superadmin = true`, `universidad_activa_id = null` y `rol = null`

### Requirement: Nueva firma de create_access_token y campos documentados en decode_token

El sistema SHALL modificar `create_access_token` en `app/core/security.py` para dejar de recibir el rol global del usuario y pasar a recibir la universidad activa, el rol de la membresía y el flag superadmin. La firma SHALL ser `create_access_token(user_id, username, *, rol: str | None, universidad_activa_id: int | None, es_superadmin: bool, expires_delta=None)`, con los tres campos multi-tenant como argumentos **keyword-only** para que ninguna llamada posicional desactualizada compile con el argumento equivocado. `decode_token` SHALL mantener su firma (devuelve el dict del payload) y su docstring SHALL documentar los nuevos claims y que pueden faltar en tokens viejos.

#### Scenario: create_access_token exige los campos multi-tenant como keyword-only

- **WHEN** se llama a `create_access_token` con `rol`/`universidad_activa_id`/`es_superadmin` pasados posicionalmente (estilo viejo)
- **THEN** la llamada SHALL fallar (TypeError), forzando a actualizar el caller

#### Scenario: decode_token expone los nuevos claims

- **WHEN** se decodifica un token emitido por la nueva `create_access_token`
- **THEN** el dict devuelto SHALL exponer `universidad_activa_id`, `rol` y `es_superadmin` junto con `user_id` y `username`

### Requirement: Retrocompatibilidad de tokens emitidos antes de este cambio

El sistema SHALL seguir aceptando para autenticación los JWT emitidos antes de este change (que no traen `universidad_activa_id` ni `es_superadmin`). La autenticación base (`get_current_user`) SHALL seguir funcionando con esos tokens porque solo depende de `user_id`. No SHALL forzarse un re-login masivo: los tokens viejos expiran naturalmente según `ACCESS_TOKEN_EXPIRE_DAYS`. La resolución de universidad activa para un token sin `universidad_activa_id` se define en la capability `dependency-universidad-activa`.

#### Scenario: Un token viejo sigue autenticando

- **WHEN** se presenta un JWT válido emitido antes de este change (sin `universidad_activa_id` ni `es_superadmin`) a un endpoint que solo requiere `get_current_user`
- **THEN** el usuario SHALL quedar autenticado normalmente (el token no se rechaza por faltarle los claims nuevos)

#### Scenario: No se invalidan las sesiones existentes al desplegar

- **WHEN** se despliega este change
- **THEN** los tokens ya emitidos NO SHALL ser invalidados; siguen válidos hasta su expiración natural
