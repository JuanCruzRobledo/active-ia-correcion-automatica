## ADDED Requirements

### Requirement: Entidad Trabajo Práctico

El sistema SHALL modelar un `TrabajoPractico` que pertenece a una materia y agrupa uno o más ejercicios. La entidad SHALL tener título, materia, `universidad_id` denormalizado propagado desde la materia, marcas de tiempo y soporte de baja lógica. Un trabajo práctico SHALL poder existir sin ejercicios (estado intermedio durante su creación).

#### Scenario: Alta de un trabajo práctico

- **WHEN** se crea un trabajo práctico asociado a una materia
- **THEN** queda persistido con su título, su materia y el `universidad_id` de esa materia

#### Scenario: Baja lógica de un trabajo práctico

- **WHEN** se elimina un trabajo práctico
- **THEN** la fila se marca como borrada y no se elimina físicamente, quedando fuera de los listados

### Requirement: Entidad Ejercicio

El sistema SHALL modelar un `Ejercicio` que pertenece a un trabajo práctico y representa la unidad de corrección. La entidad SHALL tener orden dentro del trabajo práctico, título, enunciado en Markdown, peso relativo, `materia_id` y `universidad_id` denormalizados, marcas de tiempo y soporte de baja lógica. El `peso` SHALL ser un decimal mayor que cero, con valor por defecto 1.

#### Scenario: Alta de un ejercicio dentro de un trabajo práctico

- **WHEN** se crea un ejercicio bajo un trabajo práctico con orden, título, enunciado y peso
- **THEN** queda persistido con esos datos y con la materia y universidad heredadas del trabajo práctico

#### Scenario: Peso por defecto

- **WHEN** se crea un ejercicio sin especificar peso
- **THEN** el peso queda en 1

#### Scenario: Peso inválido

- **WHEN** se intenta crear un ejercicio con peso cero o negativo
- **THEN** el sistema rechaza la operación con un error de validación

### Requirement: El peso de los ejercicios no se valida contra un total

El sistema NO SHALL exigir que los pesos de los ejercicios de un trabajo práctico sumen ningún valor determinado, y NO SHALL calcular la nota final del trabajo práctico a partir de ellos. El peso SHALL almacenarse y devolverse como metadata para el consumidor.

#### Scenario: Trabajo práctico con pesos que no suman 100

- **WHEN** se crea un trabajo práctico con cuatro ejercicios de peso 1 cada uno
- **THEN** la operación es válida y los cuatro pesos se persisten tal cual

### Requirement: Un ejercicio es dueño de exactamente una rúbrica

El sistema SHALL vincular cada ejercicio con exactamente una rúbrica, mediante una referencia opcional y única desde la rúbrica hacia el ejercicio. Una rúbrica SHALL poder no pertenecer a ningún ejercicio (las rúbricas del flujo de Moodle). Dos rúbricas NO SHALL poder apuntar al mismo ejercicio. La rúbrica de un ejercicio SHALL usar el mismo modelo de criterios, subcriterios, penalizaciones y condiciones de desaprobación que cualquier otra rúbrica del sistema.

#### Scenario: Rúbrica vinculada a un ejercicio

- **WHEN** se crea una rúbrica para un ejercicio
- **THEN** la rúbrica queda referenciando ese ejercicio y el ejercicio puede navegarse hasta ella

#### Scenario: Rúbrica de Moodle sin ejercicio

- **WHEN** se crea una rúbrica por el flujo existente, sin ejercicio
- **THEN** la rúbrica se persiste con la referencia al ejercicio vacía, igual que antes del change

#### Scenario: Dos rúbricas para el mismo ejercicio

- **WHEN** se intenta vincular una segunda rúbrica a un ejercicio que ya tiene una
- **THEN** el sistema rechaza la operación por violación de unicidad

### Requirement: La unicidad de rúbricas por materia, tipo, número y año aplica solo fuera de los ejercicios

La restricción de unicidad de una rúbrica sobre materia, tipo, número y año SHALL aplicarse únicamente a las rúbricas que no pertenecen a un ejercicio. Las rúbricas pertenecientes a un ejercicio SHALL quedar exentas, de modo que varios ejercicios de un mismo trabajo práctico puedan tener cada uno su rúbrica con el mismo tipo, número y año.

#### Scenario: Cuatro ejercicios del mismo trabajo práctico

- **WHEN** se crean cuatro rúbricas para los cuatro ejercicios de un trabajo práctico, todas con la misma materia, tipo, número y año
- **THEN** las cuatro se persisten sin conflicto

#### Scenario: Dos rúbricas de Moodle idénticas en clave

- **WHEN** se intenta crear una segunda rúbrica sin ejercicio con la misma materia, tipo, número y año que una existente
- **THEN** el sistema la rechaza, igual que antes del change

### Requirement: Baja lógica en cascada del ejercicio y su rúbrica

Al dar de baja lógica un ejercicio, el sistema SHALL dar de baja lógica también su rúbrica, en la misma operación. Ningún registro SHALL eliminarse físicamente.

#### Scenario: Baja de un ejercicio

- **WHEN** se elimina un ejercicio que tiene rúbrica
- **THEN** el ejercicio y su rúbrica quedan ambos marcados como borrados, y ninguna fila se elimina físicamente

### Requirement: Aislamiento por universidad y control de acceso

Los trabajos prácticos y los ejercicios SHALL estar scopeados por `universidad_id`, y las consultas SHALL filtrar por la universidad activa del usuario, igual que el resto de las entidades del sistema. El acceso a un trabajo práctico o a un ejercicio SHALL verificarse por la pertenencia del usuario a la materia que los contiene.

#### Scenario: Usuario de otra universidad

- **WHEN** un usuario cuya universidad activa es distinta consulta un trabajo práctico
- **THEN** el sistema le niega el acceso, sin revelar si el recurso existe

#### Scenario: Usuario sin acceso a la materia

- **WHEN** un usuario con acceso a la universidad pero no a la materia consulta un ejercicio de esa materia
- **THEN** el sistema le niega el acceso

### Requirement: El flujo de Moodle no se altera

El vínculo entre una rúbrica y una actividad de Moodle SHALL seguir existiendo y funcionando exactamente igual, y las rúbricas del flujo de Moodle NO SHALL requerir ejercicio ni identificador externo.

#### Scenario: Rúbrica de Moodle tras el change

- **WHEN** se consulta o actualiza una rúbrica vinculada a una actividad de Moodle
- **THEN** su comportamiento es idéntico al previo al change

#### Scenario: Corrección por el flujo de Moodle

- **WHEN** se corrige una entrega importada desde Moodle
- **THEN** el flujo funciona sin cambios y sin involucrar trabajos prácticos ni ejercicios
