# frontend-login-dos-pasos Specification

## Purpose
TBD - created by archiving change multi-tenant-frontend-workspace. Update Purpose after archive.
## Requirements
### Requirement: El cliente distingue las dos respuestas posibles del login

El cliente SHALL tratar la respuesta de `POST /auth/login` como una unión discriminada por el campo `requiere_seleccion`. SHALL persistir token y usuario en almacenamiento local ÚNICAMENTE cuando la respuesta trae `access_token`. Cuando la respuesta indica que se requiere selección, el cliente NO SHALL escribir `auth_token` ni `auth_user`.

#### Scenario: Login que resuelve directo

- **WHEN** el backend responde con `access_token`, `token_type` y `user`
- **THEN** el cliente persiste el token y el usuario, y navega al destino habitual

#### Scenario: Login que requiere selección

- **WHEN** el backend responde con `requiere_seleccion: true`, la lista `universidades` y un `token_transicion`
- **THEN** el cliente NO persiste sesión
- **AND** NO intenta leer `user` de la respuesta
- **AND** presenta la pantalla de selección de universidad

#### Scenario: No se escribe un token inválido

- **WHEN** la respuesta no trae `access_token`
- **THEN** el valor almacenado en `auth_token` NO cambia y en ningún caso queda el literal `"undefined"`

### Requirement: Selección de universidad como segundo paso del login

Cuando el login requiere selección, el cliente SHALL mostrar las universidades disponibles con el rol del usuario en cada una, y al elegir una SHALL llamar a `POST /auth/select-universidad` enviando el `token_transicion` y la universidad elegida. Con el token final recibido SHALL completar el inicio de sesión.

#### Scenario: Selección exitosa

- **WHEN** el usuario elige una universidad de la lista
- **THEN** el cliente llama a `POST /auth/select-universidad` con `token_transicion` y `universidad_id`
- **AND** al recibir el token final persiste la sesión y navega al destino habitual

#### Scenario: Cada opción muestra su rol

- **WHEN** se renderiza la lista de universidades
- **THEN** cada opción muestra el nombre de la universidad y el rol del usuario en esa universidad

#### Scenario: Token de transición vencido

- **WHEN** el usuario tarda más que la vigencia del token de transición y luego elige una universidad
- **THEN** el backend responde 401 y el cliente vuelve al formulario de login con un mensaje que invita a reintentar

#### Scenario: Volver atrás sin elegir

- **WHEN** el usuario decide volver al formulario de login sin elegir universidad
- **THEN** el cliente descarta el `token_transicion` y no queda sesión iniciada

### Requirement: El usuario sin universidad asignada recibe un mensaje claro

El cliente SHALL surfacear el 403 de "usuario sin universidad asignada" como un mensaje accionable en la pantalla de login, distinguible de un error de credenciales.

#### Scenario: Usuario sin membresías

- **WHEN** el backend responde 403 con el detalle de usuario sin universidad asignada
- **THEN** el cliente muestra ese mensaje del backend y NO deja al usuario en un estado de sesión a medias

