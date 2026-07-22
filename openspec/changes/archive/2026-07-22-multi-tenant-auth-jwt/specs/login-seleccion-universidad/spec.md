## ADDED Requirements

### Requirement: Resolución de membresías activas en el login

El sistema SHALL, tras validar credenciales exitosamente en `POST /auth/login` (manteniendo intacta la lógica actual de bloqueo por intentos fallidos y de cuenta deshabilitada), resolver las membresías **activas** del usuario (`usuario_universidad.activo = true` y `universidades.activa = true`) a través de un método de repositorio (nunca SQL crudo en el service, regla ARCH-001) y ramificar el resultado según sea superadmin y según la cantidad de membresías. La lógica de resolución y emisión de token SHALL vivir en el `AuthService`, no en el router.

#### Scenario: Usuario no-superadmin con exactamente una universidad hace login normal

- **WHEN** un usuario no-superadmin con una única membresía activa se autentica correctamente
- **THEN** el sistema SHALL responder 200 con un `access_token` cuyo JWT lleva `universidad_activa_id` de esa universidad y `rol` de esa membresía
- **THEN** la respuesta NO SHALL pedir selección de universidad

#### Scenario: Usuario no-superadmin sin universidades es rechazado

- **WHEN** un usuario no-superadmin sin ninguna membresía activa se autentica con credenciales correctas
- **THEN** el sistema SHALL responder 403 indicando que el usuario no tiene universidad asignada
- **THEN** NO SHALL emitirse ningún `access_token`

#### Scenario: Usuario con dos o más universidades recibe respuesta intermedia de selección

- **WHEN** un usuario no-superadmin con dos o más membresías activas se autentica correctamente
- **THEN** el sistema SHALL responder 200 con `requiere_seleccion = true` y una lista `universidades` donde cada elemento tiene `id`, `nombre` y `rol` (el rol del usuario en esa universidad)
- **THEN** la respuesta intermedia NO SHALL contener todavía un `access_token` final

### Requirement: Endpoint de selección de universidad tras un login que la requiere

El sistema SHALL exponer `POST /auth/select-universidad` que recibe `universidad_id` y, para el usuario identificado del paso de login, valida que exista una membresía **activa** en esa universidad y emite el token final. Si el usuario no es miembro activo de la universidad elegida, SHALL responder 403. Un superadmin SHALL poder seleccionar cualquier universidad activa aunque no tenga membresía en ella.

#### Scenario: Selección válida emite el token final

- **WHEN** un usuario que recibió `requiere_seleccion` elige una universidad en la que tiene membresía activa
- **THEN** el sistema SHALL responder 200 con un `access_token` cuyo JWT lleva `universidad_activa_id` de la elegida y `rol` de esa membresía

#### Scenario: Selección de una universidad donde no es miembro activo es rechazada

- **WHEN** el usuario elige una `universidad_id` en la que no tiene membresía, o su membresía está inactiva
- **THEN** el sistema SHALL responder 403 y NO SHALL emitir token

#### Scenario: Un superadmin puede seleccionar cualquier universidad activa

- **WHEN** un superadmin selecciona una universidad activa en la que no tiene membresía
- **THEN** el sistema SHALL responder 200 con un token que lleva esa `universidad_activa_id`, `es_superadmin = true` y un `rol` sintético ADMIN para esa universidad

### Requirement: Endpoint de cambio de universidad activa en sesión autenticada

El sistema SHALL exponer `POST /auth/switch-universidad` que, para un usuario **ya autenticado** (`get_current_user`), recibe `universidad_id`, valida membresía **activa** en esa universidad y re-emite el token con la nueva universidad activa y el rol correspondiente. Si no es miembro activo, SHALL responder 403. Un superadmin SHALL poder cambiar a cualquier universidad activa aunque no tenga membresía en ella.

#### Scenario: Switch válido re-emite el token con la nueva universidad

- **WHEN** un usuario autenticado con membresía activa en la universidad V hace switch a V
- **THEN** el sistema SHALL responder 200 con un nuevo `access_token` cuyo JWT lleva `universidad_activa_id` = V y el `rol` de la membresía en V

#### Scenario: Switch a una universidad sin membresía activa es rechazado

- **WHEN** un usuario autenticado (no superadmin) hace switch a una universidad en la que no tiene membresía activa
- **THEN** el sistema SHALL responder 403 y el token vigente NO SHALL cambiar

#### Scenario: Un superadmin puede switchear a cualquier universidad activa

- **WHEN** un superadmin hace switch a una universidad activa en la que no tiene membresía
- **THEN** el sistema SHALL responder 200 con un token con esa `universidad_activa_id`, `es_superadmin = true` y `rol` sintético ADMIN

### Requirement: Schemas del login en dos pasos y semántica de UserInfo

El sistema SHALL definir en `app/schemas/auth.py` los schemas del flujo: `UniversidadDisponible` (`id`, `nombre`, `rol: RolEnum`), `SeleccionarUniversidadRequest` (`universidad_id: int`) y una respuesta de login que sea o bien el token con información de usuario, o bien la respuesta intermedia `{requiere_seleccion: true, universidades: [...]}`. `UserInfo.rol` SHALL reflejar el rol del usuario **en la universidad activa** (tipo `RolEnum | None`, `None` solo en superadmin sin universidad elegida) en lugar del rol global, y `UserInfo` SHALL incluir `universidad_activa_id` y `es_superadmin`.

#### Scenario: UserInfo devuelve el rol de la universidad activa

- **WHEN** el login resuelve la universidad activa U con rol COORDINADOR para el usuario
- **THEN** el `UserInfo` de la respuesta SHALL tener `rol = COORDINADOR`, `universidad_activa_id` = U y `es_superadmin = false`

#### Scenario: La respuesta intermedia lista las universidades disponibles con su rol

- **WHEN** el login determina que se requiere selección
- **THEN** la respuesta SHALL contener `universidades`, una lista de `UniversidadDisponible` con `id`, `nombre` y `rol` por cada membresía activa
