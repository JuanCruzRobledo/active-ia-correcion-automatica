## ADDED Requirements

### Requirement: Identificador externo en materia, trabajo práctico y ejercicio

Las entidades `Materia`, `TrabajoPractico` y `Ejercicio` SHALL aceptar un identificador externo (`external_ref`) provisto por el sistema cliente, almacenado como cadena opaca de hasta 64 caracteres. El sistema NO SHALL interpretar su contenido ni asumir un formato particular. En `Materia` el identificador SHALL ser opcional; en `TrabajoPractico` y `Ejercicio` SHALL ser obligatorio.

#### Scenario: Materia sin identificador externo

- **WHEN** existe una materia creada por el flujo de Moodle, sin identificador externo
- **THEN** la materia sigue siendo válida y operable igual que antes del change

#### Scenario: Trabajo práctico sin identificador externo

- **WHEN** se intenta crear un trabajo práctico sin identificador externo
- **THEN** el sistema rechaza la operación con un error de validación

#### Scenario: Identificador con formato arbitrario

- **WHEN** se guarda un identificador externo que no es un UUID
- **THEN** el sistema lo acepta y lo almacena tal cual, sin interpretarlo

### Requirement: Unicidad del identificador externo

El identificador externo de una materia SHALL ser único dentro de su universidad. El identificador externo de un trabajo práctico y el de un ejercicio SHALL ser únicos dentro de su materia. La unicidad SHALL considerar únicamente los registros no dados de baja, de modo que el identificador de un registro eliminado pueda reutilizarse.

#### Scenario: Identificador duplicado dentro de la misma materia

- **WHEN** se intenta crear un segundo ejercicio con un identificador externo ya usado por otro ejercicio vigente de la misma materia
- **THEN** el sistema rechaza la operación por violación de unicidad

#### Scenario: Mismo identificador en materias distintas

- **WHEN** dos materias distintas tienen cada una un ejercicio con el mismo identificador externo
- **THEN** ambas operaciones son válidas

#### Scenario: Reutilización tras baja lógica

- **WHEN** se crea un trabajo práctico con el identificador externo de otro que fue dado de baja
- **THEN** la operación es válida

#### Scenario: Identificador de materia duplicado en la misma universidad

- **WHEN** se intenta asignar a una materia un identificador externo que ya tiene otra materia de la misma universidad
- **THEN** el sistema rechaza la operación

### Requirement: Resolución de entidades por identificador externo

El sistema SHALL poder resolver una materia, un trabajo práctico y un ejercicio a partir de su identificador externo, sin requerir el identificador interno. La resolución de un trabajo práctico y de un ejercicio SHALL acotarse a la materia correspondiente y a la universidad activa. La resolución SHALL ignorar los registros dados de baja.

#### Scenario: Resolver un ejercicio por su identificador externo

- **WHEN** se busca un ejercicio por su identificador externo dentro de una materia
- **THEN** se obtiene el ejercicio vigente correspondiente

#### Scenario: Identificador inexistente

- **WHEN** se busca por un identificador externo que no corresponde a ningún registro vigente
- **THEN** la resolución no devuelve resultado

#### Scenario: Registro dado de baja

- **WHEN** se busca por el identificador externo de un ejercicio dado de baja
- **THEN** la resolución no lo devuelve

#### Scenario: Resolución acotada a la universidad activa

- **WHEN** se busca por un identificador externo que existe en otra universidad
- **THEN** la resolución no devuelve resultado

### Requirement: El identificador externo convive con el identificador de Moodle

El identificador de actividad de Moodle en la rúbrica SHALL conservarse sin cambios de tipo, semántica ni comportamiento. El identificador externo SHALL ser un mecanismo de cruce independiente, y una misma rúbrica NO SHALL requerir ambos.

#### Scenario: Rúbrica de Moodle tras el change

- **WHEN** se consulta una rúbrica vinculada por identificador de actividad de Moodle
- **THEN** ese vínculo sigue funcionando exactamente igual que antes

#### Scenario: Rúbrica de ejercicio sin identificador de Moodle

- **WHEN** se crea la rúbrica de un ejercicio
- **THEN** no se requiere identificador de actividad de Moodle y el cruce se hace por el identificador externo del ejercicio
