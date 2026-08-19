## ADDED Requirements

### Requirement: Autenticación mediante credencial de servicio

El sistema SHALL aceptar la credencial de una cuenta de servicio presentada en el encabezado de autorización como credencial portadora, resolverla a la cuenta correspondiente comparando su representación no reversible, y construir con ella un contexto de ejecución con la universidad y el alcance de esa cuenta. La comparación SHALL realizarse en tiempo constante.

#### Scenario: Credencial válida

- **WHEN** se presenta la credencial de una cuenta de servicio activa y no expirada
- **THEN** la petición se autentica y opera con la universidad y el alcance de esa cuenta

#### Scenario: Credencial inválida

- **WHEN** se presenta una credencial que no corresponde a ninguna cuenta de servicio
- **THEN** el sistema responde 401 sin indicar si el prefijo existe

#### Scenario: Credencial de una cuenta desactivada

- **WHEN** se presenta la credencial de una cuenta de servicio cuyo estado activo es falso
- **THEN** el sistema responde 401

#### Scenario: Credencial de una cuenta dada de baja

- **WHEN** se presenta la credencial de una cuenta de servicio dada de baja lógica
- **THEN** el sistema responde 401

#### Scenario: Credencial expirada

- **WHEN** se presenta la credencial de una cuenta cuya fecha de expiración ya pasó
- **THEN** el sistema responde 401

#### Scenario: Credencial rotada

- **WHEN** se presenta una credencial que fue reemplazada por una rotación
- **THEN** el sistema responde 401

### Requirement: La revocación es inmediata

Al desactivar, dar de baja o rotar la credencial de una cuenta de servicio, la credencial anterior SHALL dejar de autenticar a partir de la siguiente petición, sin requerir ninguna acción adicional ni afectar la sesión de ningún usuario humano.

#### Scenario: Desactivación durante el uso

- **WHEN** se desactiva una cuenta de servicio que está realizando peticiones
- **THEN** la siguiente petición con esa credencial responde 401

#### Scenario: Sesiones humanas no afectadas

- **WHEN** se revoca una cuenta de servicio
- **THEN** ninguna sesión de usuario humano se interrumpe

### Requirement: Una cuenta de servicio no satisface verificaciones de rol humano

Un contexto de cuenta de servicio NO SHALL satisfacer ninguna verificación de rol de usuario humano, incluidas las de administrador, coordinador, tutor y gestor. Sus capacidades SHALL derivarse exclusivamente de su lista explícita de permisos y de su alcance de materias.

#### Scenario: Verificación de rol administrador

- **WHEN** una cuenta de servicio intenta acceder a un recurso que requiere rol de administrador
- **THEN** el sistema responde 403, aunque la cuenta tenga permisos de escritura sobre materias

#### Scenario: Verificación de rol coordinador

- **WHEN** una cuenta de servicio intenta acceder a un recurso que requiere rol de coordinador y que no está entre sus permisos explícitos
- **THEN** el sistema responde 403

#### Scenario: Operación cubierta por sus permisos

- **WHEN** una cuenta de servicio con permiso de escritura de trabajos prácticos opera sobre una materia de su alcance
- **THEN** la operación se permite

### Requirement: Aislamiento por universidad de la cuenta de servicio

Una cuenta de servicio SHALL operar exclusivamente dentro de su universidad. Cualquier acceso a un recurso de otra universidad SHALL rechazarse sin revelar si el recurso existe.

#### Scenario: Recurso de otra universidad

- **WHEN** una cuenta de servicio intenta operar sobre una materia de otra universidad
- **THEN** el sistema rechaza la operación sin revelar si la materia existe

### Requirement: La credencial no aparece en los registros

El sistema NO SHALL registrar la credencial de servicio en ningún log, incluidos los de error y las trazas de excepción.

#### Scenario: Petición autenticada con credencial de servicio

- **WHEN** se procesa una petición autenticada con credencial de servicio y se emiten registros
- **THEN** ningún registro contiene la credencial

#### Scenario: Error durante una petición autenticada

- **WHEN** una petición autenticada con credencial de servicio produce un error y se registra la traza
- **THEN** la traza no contiene la credencial

### Requirement: Los permisos humanos existentes no se modifican

La incorporación de la autenticación por cuenta de servicio NO SHALL cambiar ninguna verificación de permisos aplicable a usuarios humanos. En particular, el rol tutor SHALL seguir sin poder leer los criterios de una rúbrica.

#### Scenario: Lectura de criterios de rúbrica con rol tutor

- **WHEN** un usuario con rol tutor consulta el detalle de una rúbrica
- **THEN** el sistema responde 403, igual que antes del change

#### Scenario: Permisos de coordinador y administrador

- **WHEN** un coordinador o un administrador realizan las operaciones que ya podían realizar
- **THEN** el comportamiento es idéntico al previo al change
