# frontend-universidad-activa Specification

## Purpose
TBD - created by archiving change multi-tenant-frontend-workspace. Update Purpose after archive.
## Requirements
### Requirement: Contexto reactivo de universidad activa

El cliente SHALL exponer un contexto de tenant (`TenantProvider` / `useTenant()`) como fuente única de `universidad_activa_id`, `rol` y `es_superadmin`, derivada de la sesión vigente. Los componentes que hoy leen el rol desde el usuario almacenado SHALL leerlo del contexto. El contexto SHALL ser reactivo: un cambio de universidad SHALL propagarse sin recargar la página.

#### Scenario: El rol proviene de la membresía activa

- **WHEN** un usuario es TUTOR en la universidad A y COORDINADOR en la B, y su universidad activa es la B
- **THEN** `useTenant().rol` devuelve `COORDINADOR`

#### Scenario: Propagación sin recarga

- **WHEN** el usuario cambia de universidad
- **THEN** los componentes suscritos al contexto reflejan el nuevo rol y la nueva universidad sin que se recargue la página

#### Scenario: Sesión sin universidad activa

- **WHEN** la sesión vigente no tiene universidad activa
- **THEN** `useTenant().universidadActivaId` es `null` y `rol` es `null`

### Requirement: El gating de navegación contempla al superadmin

El menú de navegación SHALL mostrar los items cuyo rol requerido coincide con el rol de la universidad activa, y SHALL mostrar TODOS los items cuando `es_superadmin` es verdadero, aunque `rol` sea `null`.

#### Scenario: Superadmin ve el menú completo

- **WHEN** un superadmin con `rol = null` abre la aplicación
- **THEN** la navegación muestra todos los items, no solamente los que no declaran roles

#### Scenario: Rol nulo sin superadmin

- **WHEN** un usuario no superadmin tiene `rol = null`
- **THEN** la navegación muestra únicamente los items que no declaran roles

#### Scenario: El menú sigue al rol de la universidad activa

- **WHEN** un usuario es TUTOR en la universidad A y COORDINADOR en la B, y cambia de A a B
- **THEN** el menú pasa a mostrar los items de COORDINADOR

### Requirement: Selector de universidad en la aplicación

El cliente SHALL ofrecer un selector de universidad accesible desde el layout, poblado con `GET /universidades/mias`. Para un superadmin SHALL incluir además una opción de modo global rotulada "Todas las universidades".

#### Scenario: Opciones del selector

- **WHEN** un usuario con membresía en dos universidades abre el selector
- **THEN** ve ambas universidades y cuál es la activa

#### Scenario: El superadmin tiene el modo global

- **WHEN** un superadmin abre el selector
- **THEN** ve todas las universidades activas más la opción "Todas las universidades"

#### Scenario: Usuario con una sola universidad

- **WHEN** un usuario no superadmin tiene una única membresía activa
- **THEN** el selector no ofrece alternativas de cambio

### Requirement: El cambio de universidad invalida la caché de datos

Al cambiar de universidad, el cliente SHALL llamar a `POST /auth/switch-universidad`, reemplazar la sesión con el token devuelto, **invalidar la totalidad de la caché de datos del servidor** y navegar al dashboard. Ningún dato obtenido bajo la universidad anterior SHALL permanecer visible ni reutilizarse.

#### Scenario: Cambio exitoso

- **WHEN** el usuario elige otra universidad en el selector
- **THEN** el cliente llama a `POST /auth/switch-universidad` con esa universidad
- **AND** reemplaza el token de sesión por el devuelto
- **AND** invalida toda la caché de datos del servidor
- **AND** navega a `/dashboard`

#### Scenario: No se filtran datos entre universidades

- **WHEN** el usuario venía de ver un listado de materias de la universidad A y cambia a la B
- **THEN** ese listado NO se muestra con los datos de A
- **AND** los datos se vuelven a pedir bajo el contexto de B

#### Scenario: Superadmin pasa a modo global

- **WHEN** un superadmin elige "Todas las universidades"
- **THEN** el cliente obtiene un token con `universidad_activa_id = null`
- **AND** invalida la caché y navega al dashboard

#### Scenario: Cambio rechazado

- **WHEN** el backend rechaza el cambio porque el usuario no tiene membresía activa en la universidad elegida
- **THEN** el cliente conserva la sesión anterior intacta y muestra el error
- **AND** NO invalida la caché

### Requirement: Errores de contexto de universidad con mensaje accionable

El cliente SHALL distinguir el 409 de "sin universidad activa" y el 424 de "sin credenciales de Moodle" del tratamiento genérico de esos códigos, mostrando en cada caso un mensaje que indique qué hacer.

#### Scenario: Operación sin universidad activa

- **WHEN** una operación falla con 409 porque la sesión no tiene universidad activa
- **THEN** el cliente muestra un mensaje que invita a elegir una universidad, y NO el mensaje genérico de conflicto o recurso duplicado

#### Scenario: Falta de credenciales de Moodle

- **WHEN** una operación contra Moodle falla con 424
- **THEN** el cliente muestra un mensaje que indica que faltan las credenciales de Moodle para la universidad activa y remite al perfil

### Requirement: Las credenciales de Moodle son por universidad y el campus es de sólo lectura

El perfil SHALL permitir editar únicamente `moodle_username` y la contraseña, que corresponden a la membresía en la universidad activa. El campus (`moodle_host`) SHALL mostrarse como dato de sólo lectura de la universidad activa y NO SHALL enviarse al guardar.

#### Scenario: El formulario no pide el campus

- **WHEN** el usuario abre el formulario de credenciales de Moodle en el perfil
- **THEN** el campus se muestra como información, no como campo editable
- **AND** el formulario no exige completarlo para poder guardar

#### Scenario: El guardado no envía el campus

- **WHEN** el usuario guarda sus credenciales de Moodle
- **THEN** la petición envía sólo usuario y contraseña

#### Scenario: Las credenciales acompañan a la universidad activa

- **WHEN** el usuario cambia de universidad y vuelve al perfil
- **THEN** ve las credenciales y el campus correspondientes a la nueva universidad activa

#### Scenario: Universidad activa sin campus configurado

- **WHEN** la universidad activa no tiene `moodle_host` cargado
- **THEN** el perfil lo indica explícitamente y advierte que las operaciones contra Moodle no van a funcionar

