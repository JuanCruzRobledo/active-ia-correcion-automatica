## ADDED Requirements

### Requirement: El listado de usuarios está acotado a la universidad activa

El sistema SHALL devolver, en el listado y la búsqueda de usuarios, únicamente usuarios con membresía activa en la universidad activa del solicitante. Un usuario de otra universidad NO SHALL aparecer, ni siquiera en los totales de paginación.

Un superadmin sin universidad activa SHALL ver todos los usuarios.

#### Scenario: Cada universidad ve sólo los suyos

- **WHEN** un ADMIN de la universidad A lista usuarios
- **THEN** la respuesta contiene únicamente usuarios con membresía activa en A
- **AND** el total refleja ese conteo, no el global

#### Scenario: Aislamiento simétrico

- **WHEN** un ADMIN de la universidad B lista usuarios
- **THEN** no aparece ninguno de los usuarios exclusivos de A

#### Scenario: Membresía inactiva excluida

- **WHEN** un usuario tiene su membresía en la universidad activa marcada como inactiva
- **THEN** no aparece en el listado de esa universidad

#### Scenario: Usuario con dos membresías

- **WHEN** un usuario tiene membresía activa en A y en B
- **THEN** aparece en el listado de ambas

#### Scenario: Superadmin en modo global

- **WHEN** un superadmin sin universidad activa lista usuarios
- **THEN** ve los usuarios de todas las universidades

### Requirement: El filtro por rol usa el rol de la membresía

El sistema SHALL resolver el filtro por rol del listado de usuarios contra el rol de la membresía en la universidad activa, no contra un rol global del usuario.

#### Scenario: El mismo usuario con roles distintos

- **WHEN** una persona es TUTOR en la universidad A y COORDINADOR en la B, y se filtra por TUTOR estando activo en A
- **THEN** aparece en el resultado

#### Scenario: El mismo usuario no aparece bajo el rol de la otra universidad

- **WHEN** se filtra por TUTOR estando activo en la universidad B, donde esa persona es COORDINADOR
- **THEN** no aparece en el resultado

### Requirement: Las notificaciones no cruzan universidades

El sistema SHALL acotar la selección de tutores destinatarios de notificaciones a la universidad correspondiente. Un tutor de otra universidad NO SHALL recibir notificaciones que no le corresponden.

#### Scenario: Destinatarios acotados

- **WHEN** se preparan las notificaciones para la universidad A
- **THEN** la lista de destinatarios contiene sólo tutores con membresía activa en A

### Requirement: El alta de usuario crea la membresía en la universidad activa

El sistema SHALL crear, al dar de alta un usuario, tanto el usuario como su membresía en la universidad activa con el rol indicado, de forma atómica. Si la creación de la membresía falla, el usuario NO SHALL quedar creado.

Un solicitante sin universidad activa SHALL recibir 400, con un mensaje que indique que debe elegir una universidad.

#### Scenario: Alta exitosa

- **WHEN** un ADMIN de la universidad A crea un usuario con rol TUTOR
- **THEN** el usuario queda creado
- **AND** queda con membresía activa en A con rol TUTOR
- **AND** aparece en el listado de usuarios de A

#### Scenario: El usuario nuevo no aparece en otra universidad

- **WHEN** se lista usuarios en la universidad B tras el alta anterior
- **THEN** el usuario recién creado no aparece

#### Scenario: Atomicidad

- **WHEN** la creación de la membresía falla
- **THEN** no queda ningún usuario creado

#### Scenario: Superadmin en modo global

- **WHEN** un superadmin sin universidad activa intenta crear un usuario
- **THEN** el sistema responde 400 indicando que debe elegir una universidad

### Requirement: El cambio de rol afecta a la membresía activa

El sistema SHALL aplicar el cambio de rol de un usuario sobre su membresía en la universidad activa del solicitante, dejando intactas sus membresías en otras universidades.

#### Scenario: Cambio acotado

- **WHEN** un ADMIN de la universidad A cambia el rol de una persona de TUTOR a COORDINADOR
- **THEN** su membresía en A pasa a COORDINADOR
- **AND** su membresía en B conserva el rol que tenía

#### Scenario: Usuario de otra universidad

- **WHEN** se intenta cambiar el rol de un usuario que no tiene membresía activa en la universidad activa
- **THEN** el sistema responde 404

### Requirement: El usuario deja de tener rol y credenciales Moodle globales

El sistema NO SHALL conservar en la entidad usuario un rol global ni credenciales de Moodle globales. El rol SHALL vivir únicamente en la membresía, y las credenciales de Moodle únicamente en la membresía; el campus, únicamente en la universidad.

#### Scenario: El rol se informa desde la membresía

- **WHEN** una persona consulta su perfil estando activa en una universidad
- **THEN** el rol informado es el de su membresía en esa universidad

#### Scenario: El rol del perfil sigue a la universidad activa

- **WHEN** esa persona cambia a otra universidad donde tiene otro rol y vuelve a consultar su perfil
- **THEN** el rol informado es el de la nueva universidad

#### Scenario: No queda rastro del rol global

- **WHEN** se inspecciona el esquema de la tabla de usuarios
- **THEN** no existen las columnas de rol ni de credenciales Moodle del usuario
