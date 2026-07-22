## ADDED Requirements

### Requirement: Dependency que resuelve y valida la universidad activa del token

El sistema SHALL agregar en `app/core/dependencies.py` un dependency `get_universidad_activa` que resuelve la universidad activa a partir del claim `universidad_activa_id` del token y valida que el usuario autenticado sea **miembro activo** de esa universidad (`usuario_universidad.activo = true` y `universidades.activa = true`), consultando vía repositorio (nunca SQL crudo). SHALL exponer al endpoint un contexto con `universidad_id`, el `rol` de la membresía (releído de la base, no del claim) y `es_superadmin`. Los dependencies existentes `get_current_user` y `get_current_user_optional` NO SHALL modificarse, y este nuevo dependency NO SHALL montarse todavía en los endpoints existentes (eso es de fases posteriores); se entrega listo para consumir y cubierto por tests.

#### Scenario: Miembro activo obtiene el contexto de universidad

- **WHEN** un usuario presenta un token con `universidad_activa_id` = U y tiene membresía activa en U con rol TUTOR
- **THEN** `get_universidad_activa` SHALL devolver un contexto con `universidad_id` = U, `rol` = TUTOR y `es_superadmin` = false

#### Scenario: El rol se relee de la base, no del claim

- **WHEN** el token trae `rol = ADMIN` para la universidad U pero la membresía activa del usuario en U figura en la base como COORDINADOR
- **THEN** el contexto devuelto SHALL tener `rol = COORDINADOR` (la base es la fuente de verdad; el claim es informativo)

#### Scenario: Membresía revocada es rechazada

- **WHEN** un usuario presenta un token con `universidad_activa_id` = U pero su membresía en U pasó a `activo = false` (o la universidad a `activa = false`)
- **THEN** `get_universidad_activa` SHALL responder 403 (acceso a esa universidad revocado)

### Requirement: Fallback de universidad activa para tokens sin el claim

El sistema SHALL, cuando `get_universidad_activa` recibe un token sin `universidad_activa_id` (token viejo previo a este change), intentar auto-resolver: si el usuario tiene **exactamente una** membresía activa, SHALL usarla como universidad activa; si tiene cero o dos o más, SHALL responder un error que indique que debe reautenticarse para elegir universidad (sin adivinar). Para un superadmin sin `universidad_activa_id`, el dependency SHALL operar en modo superadmin sin exigir membresía (según la decisión de las Open Questions del design).

#### Scenario: Token viejo de usuario con una sola universidad se auto-resuelve

- **WHEN** un usuario con exactamente una membresía activa presenta un token viejo sin `universidad_activa_id`
- **THEN** `get_universidad_activa` SHALL resolver esa única universidad como activa y devolver su contexto

#### Scenario: Token viejo de usuario con múltiples universidades exige reautenticación

- **WHEN** un usuario con dos o más membresías activas presenta un token viejo sin `universidad_activa_id`
- **THEN** `get_universidad_activa` SHALL responder un error que pide reautenticarse para elegir universidad (no elige una arbitrariamente)

### Requirement: Bypass de membresía para superadmin en el dependency

El sistema SHALL permitir que, para un usuario con `es_superadmin = true`, `get_universidad_activa` acepte cualquier `universidad_activa_id` que corresponda a una universidad **activa**, sin exigir una fila de membresía en `usuario_universidad`. El contexto devuelto para un superadmin SHALL indicar `es_superadmin = true`.

#### Scenario: Superadmin accede a una universidad activa sin ser miembro

- **WHEN** un superadmin presenta un token con `universidad_activa_id` = W (universidad activa) sin tener membresía en W
- **THEN** `get_universidad_activa` SHALL devolver el contexto de W con `es_superadmin = true` en lugar de responder 403
