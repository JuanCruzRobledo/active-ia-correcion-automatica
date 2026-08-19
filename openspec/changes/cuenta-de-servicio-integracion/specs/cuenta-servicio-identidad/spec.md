## ADDED Requirements

### Requirement: Entidad de cuenta de servicio

El sistema SHALL modelar una cuenta de servicio como identidad de máquina perteneciente a una universidad, con nombre descriptivo, credencial almacenada de forma no reversible, prefijo visible de la credencial, estado activo, fecha de expiración, marca de último uso, referencia a quién la creó, marcas de tiempo y soporte de baja lógica.

#### Scenario: Alta de una cuenta de servicio

- **WHEN** un administrador crea una cuenta de servicio para una universidad
- **THEN** la cuenta queda persistida con su nombre, su universidad, su prefijo visible, su fecha de expiración y su estado activo

#### Scenario: Baja lógica de una cuenta de servicio

- **WHEN** se elimina una cuenta de servicio
- **THEN** la fila se marca como borrada y no se elimina físicamente

### Requirement: La credencial se almacena de forma no reversible

El sistema SHALL almacenar únicamente una representación no reversible de la credencial, junto con un prefijo corto en claro que permita identificarla en un listado. El sistema NO SHALL almacenar la credencial completa en claro ni ofrecer forma alguna de recuperarla después de su creación.

#### Scenario: Persistencia de la credencial

- **WHEN** se crea una cuenta de servicio y se genera su credencial
- **THEN** la base almacena su representación no reversible y su prefijo, y no la credencial completa

#### Scenario: Intento de recuperación

- **WHEN** se consulta una cuenta de servicio existente
- **THEN** la respuesta incluye el prefijo pero nunca la credencial completa

### Requirement: La credencial se entrega una sola vez

El sistema SHALL devolver la credencial completa únicamente en la respuesta de la operación que la genera, sea el alta o una rotación. Ninguna otra operación SHALL devolverla.

#### Scenario: Respuesta del alta

- **WHEN** se crea una cuenta de servicio
- **THEN** la respuesta incluye la credencial completa, por única vez

#### Scenario: Rotación de la credencial

- **WHEN** se rota la credencial de una cuenta de servicio
- **THEN** la respuesta incluye la credencial nueva y la anterior deja de ser válida de inmediato

#### Scenario: Consulta posterior

- **WHEN** se lista o consulta la cuenta después de su creación
- **THEN** la credencial completa no aparece en ninguna respuesta

### Requirement: Alcance explícito por materia y por permiso

Una cuenta de servicio SHALL declarar explícitamente sobre qué materias puede operar y qué permisos tiene. El sistema NO SHALL derivar su alcance de ningún rol de usuario. Una operación sobre una materia fuera de su alcance, o que requiera un permiso que no tiene, SHALL rechazarse con 403.

#### Scenario: Operación dentro del alcance

- **WHEN** una cuenta de servicio con permiso de escritura sobre una materia publica un trabajo práctico de esa materia
- **THEN** la operación se permite

#### Scenario: Materia fuera del alcance

- **WHEN** una cuenta de servicio intenta operar sobre una materia que no tiene asignada
- **THEN** el sistema responde 403 sin revelar si el recurso existe

#### Scenario: Permiso no otorgado

- **WHEN** una cuenta de servicio sin permiso de corrección intenta disparar una corrección sobre una materia que sí tiene asignada
- **THEN** el sistema responde 403

### Requirement: Expiración obligatoria de la cuenta de servicio

Toda cuenta de servicio SHALL tener una fecha de expiración. Una cuenta expirada NO SHALL autenticar, aunque su estado siga siendo activo.

#### Scenario: Alta sin fecha de expiración

- **WHEN** se intenta crear una cuenta de servicio sin fecha de expiración
- **THEN** el sistema rechaza la operación con un error de validación

#### Scenario: Cuenta expirada

- **WHEN** se presenta la credencial de una cuenta cuya fecha de expiración ya pasó
- **THEN** la autenticación falla, aunque la cuenta figure como activa

### Requirement: Clave de proveedor de IA propia y cifrada

Una cuenta de servicio SHALL poder almacenar su propia clave de proveedor de IA, cifrada con el mismo mecanismo reversible que usan las claves de los usuarios. Las correcciones disparadas por esa cuenta SHALL usar su clave y NO SHALL consumir la de ningún usuario humano.

#### Scenario: Corrección disparada por una cuenta de servicio

- **WHEN** una cuenta de servicio con clave de IA propia dispara una corrección
- **THEN** la corrección usa la clave de la cuenta de servicio

#### Scenario: Cuenta de servicio sin clave de IA

- **WHEN** una cuenta de servicio sin clave de IA propia intenta disparar una corrección
- **THEN** el sistema responde con un error que indica que falta configurar la clave, y no usa la de ningún usuario

#### Scenario: Almacenamiento de la clave

- **WHEN** se configura la clave de IA de una cuenta de servicio
- **THEN** se almacena cifrada y nunca en texto plano

### Requirement: Auditoría atribuible a la cuenta de servicio

Toda acción realizada por una cuenta de servicio SHALL registrarse en la auditoría identificando a la cuenta de servicio como actor, de forma distinguible de una acción realizada por un usuario humano. El sistema SHALL actualizar la marca de último uso de la cuenta en cada autenticación exitosa.

#### Scenario: Acción de una cuenta de servicio

- **WHEN** una cuenta de servicio publica un trabajo práctico
- **THEN** la actividad registrada identifica a la cuenta de servicio como actor, y no a un usuario

#### Scenario: Marca de último uso

- **WHEN** una cuenta de servicio se autentica con éxito
- **THEN** su marca de último uso se actualiza
