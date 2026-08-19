## ADDED Requirements

### Requirement: Administración de cuentas de servicio restringida a administradores

Las operaciones de alta, listado, modificación, rotación de credencial, desactivación y baja de cuentas de servicio SHALL requerir rol de administrador sobre la universidad activa. Ninguna cuenta de servicio SHALL poder administrar cuentas de servicio.

#### Scenario: Alta por un administrador

- **WHEN** un administrador crea una cuenta de servicio en su universidad
- **THEN** la operación se permite

#### Scenario: Alta por un coordinador

- **WHEN** un coordinador intenta crear una cuenta de servicio
- **THEN** el sistema responde 403

#### Scenario: Autoadministración desde una cuenta de servicio

- **WHEN** una cuenta de servicio intenta crear o modificar cuentas de servicio
- **THEN** el sistema responde 403

### Requirement: Alta de cuenta de servicio con alcance y expiración

El alta SHALL recibir el nombre descriptivo, la lista de materias del alcance, la lista de permisos y la fecha de expiración, y SHALL generar la credencial devolviéndola en la respuesta por única vez. Las materias del alcance SHALL pertenecer a la universidad activa.

#### Scenario: Alta completa

- **WHEN** un administrador crea una cuenta de servicio con nombre, dos materias, permisos de escritura y corrección, y fecha de expiración
- **THEN** la cuenta se crea y la respuesta incluye la credencial completa por única vez

#### Scenario: Materia de otra universidad en el alcance

- **WHEN** se intenta asignar al alcance una materia de otra universidad
- **THEN** el sistema rechaza la operación

#### Scenario: Alta sin permisos declarados

- **WHEN** se intenta crear una cuenta de servicio sin ningún permiso
- **THEN** el sistema rechaza la operación con un error de validación

### Requirement: Rotación de la credencial

El sistema SHALL permitir rotar la credencial de una cuenta de servicio existente, generando una credencial nueva, invalidando la anterior de inmediato y devolviendo la nueva por única vez. La rotación NO SHALL modificar el alcance, los permisos ni la clave de proveedor de IA de la cuenta.

#### Scenario: Rotación exitosa

- **WHEN** un administrador rota la credencial de una cuenta de servicio
- **THEN** la respuesta trae la credencial nueva, la anterior deja de autenticar, y el alcance y los permisos se conservan

### Requirement: Modificación del alcance y los permisos

El sistema SHALL permitir modificar la lista de materias y la lista de permisos de una cuenta de servicio existente. Los cambios SHALL aplicarse a partir de la siguiente petición de esa cuenta.

#### Scenario: Quitar una materia del alcance

- **WHEN** se quita una materia del alcance de una cuenta de servicio
- **THEN** la siguiente operación de esa cuenta sobre esa materia responde 403

#### Scenario: Agregar un permiso

- **WHEN** se agrega el permiso de corrección a una cuenta que no lo tenía
- **THEN** la siguiente petición de corrección de esa cuenta se permite

### Requirement: Listado de cuentas de servicio sin exponer credenciales

El listado de cuentas de servicio SHALL mostrar nombre, prefijo de la credencial, alcance, permisos, estado, fecha de expiración y marca de último uso. NO SHALL exponer la credencial completa ni su representación no reversible.

#### Scenario: Listado

- **WHEN** un administrador lista las cuentas de servicio de su universidad
- **THEN** ve el prefijo y los metadatos de cada una, y ninguna credencial completa

#### Scenario: Cuentas de otra universidad

- **WHEN** un administrador lista las cuentas de servicio
- **THEN** no aparecen cuentas de otras universidades

### Requirement: Configuración de la clave de proveedor de IA

El sistema SHALL permitir configurar y reemplazar la clave de proveedor de IA de una cuenta de servicio. La clave SHALL almacenarse cifrada y NO SHALL devolverse en ninguna respuesta de lectura.

#### Scenario: Configuración de la clave

- **WHEN** un administrador configura la clave de IA de una cuenta de servicio
- **THEN** la clave queda almacenada cifrada y la respuesta no la devuelve

#### Scenario: Lectura de la cuenta

- **WHEN** se consulta una cuenta de servicio que tiene clave de IA configurada
- **THEN** la respuesta indica que hay una clave configurada, sin exponerla

### Requirement: Pantalla de administración de cuentas de servicio

El frontend SHALL ofrecer una pantalla de administración de cuentas de servicio para administradores, que permita el alta, la rotación, la modificación del alcance y la desactivación, y que muestre la credencial recién generada de forma explícita y por única vez, advirtiendo que no podrá recuperarse.

#### Scenario: Alta desde la interfaz

- **WHEN** un administrador crea una cuenta de servicio desde la pantalla
- **THEN** la credencial se muestra una sola vez, con la advertencia de que no podrá recuperarse

#### Scenario: Consulta posterior desde la interfaz

- **WHEN** el administrador vuelve a abrir la cuenta creada
- **THEN** ve el prefijo y los metadatos, y no la credencial
