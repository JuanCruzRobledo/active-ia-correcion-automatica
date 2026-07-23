## ADDED Requirements

### Requirement: Listado de universidades propias

El sistema SHALL exponer `GET /universidades/mias`, que devuelve las universidades donde el usuario autenticado tiene membresía activa, cada una con el rol del usuario en ella. Para un superadmin SHALL devolver todas las universidades activas, con rol `ADMIN` sintético (coherente con la decisión de Fase 1).

El endpoint SHALL requerir sólo autenticación: NO SHALL exigir universidad activa, porque es precisamente el endpoint que alimenta el selector antes de que exista una.

#### Scenario: Usuario con una sola membresía

- **WHEN** un usuario con membresía activa en una única universidad llama a `GET /universidades/mias`
- **THEN** el sistema devuelve 200 con una lista de un elemento, con `id`, `nombre` y el `rol` de esa membresía

#### Scenario: Usuario con varias membresías

- **WHEN** un usuario con membresías activas en dos universidades llama al endpoint
- **THEN** el sistema devuelve las dos, cada una con el rol correspondiente a esa membresía
- **AND** los roles pueden diferir entre universidades

#### Scenario: Membresía inactiva excluida

- **WHEN** un usuario tiene una membresía con `activo = false`
- **THEN** esa universidad NO aparece en la respuesta

#### Scenario: Superadmin ve todas

- **WHEN** un superadmin llama al endpoint
- **THEN** el sistema devuelve todas las universidades con `activa = true`, sin importar si tiene membresía en ellas

#### Scenario: Sin universidad activa en el token

- **WHEN** un superadmin en modo global (token con `universidad_activa_id = null`) llama al endpoint
- **THEN** el sistema responde 200 y NO responde 409

#### Scenario: Sin autenticación

- **WHEN** se llama al endpoint sin token
- **THEN** el sistema responde 401

### Requirement: Administración de universidades restringida a superadmin

El sistema SHALL exponer un ABM de universidades bajo `/universidades` cuyas operaciones de listado completo, creación, edición y baja SHALL estar restringidas a usuarios con `es_superadmin = true`. Un ADMIN de universidad NO SHALL poder administrar universidades.

#### Scenario: Superadmin lista todas las universidades

- **WHEN** un superadmin llama a `GET /universidades`
- **THEN** el sistema devuelve la lista paginada, incluyendo las inactivas cuando se pide `include_inactive=true`

#### Scenario: ADMIN de universidad rechazado

- **WHEN** un usuario cuyo rol en su universidad activa es `ADMIN`, pero con `es_superadmin = false`, llama a `GET /universidades`
- **THEN** el sistema responde 403

#### Scenario: Superadmin crea una universidad

- **WHEN** un superadmin envía `POST /universidades` con `nombre` y opcionalmente `moodle_host`
- **THEN** el sistema crea la universidad con `activa = true` y responde 201 con el recurso creado

#### Scenario: Nombre duplicado

- **WHEN** un superadmin intenta crear una universidad con un `nombre` que ya existe
- **THEN** el sistema responde 409

#### Scenario: Superadmin edita una universidad

- **WHEN** un superadmin envía `PUT /universidades/{id}` modificando `nombre`, `moodle_host` o `activa`
- **THEN** el sistema persiste los cambios y responde 200 con el recurso actualizado

#### Scenario: Universidad inexistente

- **WHEN** un superadmin opera sobre un `id` que no existe
- **THEN** el sistema responde 404

### Requirement: La baja de una universidad es siempre lógica

El sistema SHALL implementar `DELETE /universidades/{id}` como baja lógica (`activa = false`), NUNCA como borrado físico. Una universidad dada de baja SHALL conservar todos sus datos asociados.

#### Scenario: Baja lógica

- **WHEN** un superadmin llama a `DELETE /universidades/{id}`
- **THEN** el sistema marca `activa = false` y responde 204
- **AND** la fila sigue existiendo en la base

#### Scenario: Los datos asociados sobreviven

- **WHEN** se da de baja una universidad que tiene materias y comisiones
- **THEN** esas materias y comisiones NO se borran ni se modifican

#### Scenario: La universidad dada de baja desaparece del selector

- **WHEN** un usuario con membresía en una universidad `activa = false` llama a `GET /universidades/mias`
- **THEN** esa universidad NO aparece en la respuesta
