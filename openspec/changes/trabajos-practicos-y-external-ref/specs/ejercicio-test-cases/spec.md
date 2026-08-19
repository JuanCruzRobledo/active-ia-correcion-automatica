## ADDED Requirements

### Requirement: Los casos de prueba se almacenan como parte del enunciado del ejercicio

Un ejercicio SHALL poder almacenar una lista de casos de prueba, donde cada caso tiene un identificador, un nombre, un tipo y una marca de visibilidad pública. El tipo SHALL ser uno de `stdin_stdout`, `pytest_assert` o `junit_assert`. Los casos SHALL almacenarse como contexto del enunciado. El sistema NO SHALL ejecutar código del alumno ni los casos de prueba, en ninguna circunstancia.

#### Scenario: Ejercicio con casos de prueba

- **WHEN** se crea un ejercicio con dos casos de prueba de tipo `stdin_stdout`
- **THEN** los casos quedan persistidos junto al ejercicio

#### Scenario: Ejercicio sin casos de prueba

- **WHEN** se crea un ejercicio con la lista de casos vacía
- **THEN** la operación es válida y el ejercicio se persiste sin casos

#### Scenario: Tipo de caso desconocido

- **WHEN** se intenta guardar un caso con un tipo distinto de los tres admitidos
- **THEN** el sistema rechaza la operación con un error de validación

#### Scenario: Caso sin identificador o sin nombre

- **WHEN** se intenta guardar un caso sin identificador o sin nombre
- **THEN** el sistema rechaza la operación con un error de validación

### Requirement: Los casos ocultos no almacenan salida esperada ni aserción

Cuando un caso de prueba esté marcado como no público, el sistema NO SHALL almacenar su salida esperada ni su aserción. Si una operación de escritura incluye salida esperada o aserción en un caso no público, el sistema SHALL rechazar la operación con un error de validación que identifique el caso infractor, en lugar de descartar el dato en silencio.

#### Scenario: Caso oculto correcto

- **WHEN** se guarda un caso con visibilidad no pública que trae solo identificador, nombre y tipo
- **THEN** el caso se persiste con esos campos y sin salida esperada ni aserción

#### Scenario: Caso oculto con salida esperada

- **WHEN** se intenta guardar un caso no público que incluye salida esperada
- **THEN** el sistema rechaza la operación con un error de validación que nombra el caso, y no persiste nada

#### Scenario: Caso oculto con aserción

- **WHEN** se intenta guardar un caso no público que incluye una aserción
- **THEN** el sistema rechaza la operación con un error de validación que nombra el caso

#### Scenario: Caso público con salida esperada

- **WHEN** se guarda un caso público de tipo `stdin_stdout` con entrada y salida esperada
- **THEN** el caso se persiste con ambos campos

### Requirement: Los casos de aserción usan el campo de aserción y no entrada y salida

Un caso de tipo `pytest_assert` o `junit_assert` SHALL expresar su contenido en el campo de aserción, y NO SHALL usar los campos de entrada y salida esperada. Un caso de tipo `stdin_stdout` SHALL usar entrada y salida esperada, y NO SHALL usar el campo de aserción.

#### Scenario: Caso de aserción público

- **WHEN** se guarda un caso público de tipo `pytest_assert` con su aserción
- **THEN** el caso se persiste con la aserción y sin entrada ni salida esperada

#### Scenario: Caso de aserción con entrada y salida

- **WHEN** se intenta guardar un caso de tipo `junit_assert` con entrada y salida esperada
- **THEN** el sistema rechaza la operación con un error de validación

#### Scenario: Caso de entrada y salida con aserción

- **WHEN** se intenta guardar un caso de tipo `stdin_stdout` con una aserción
- **THEN** el sistema rechaza la operación con un error de validación

### Requirement: Unicidad del identificador de caso dentro del ejercicio

Los identificadores de los casos de prueba SHALL ser únicos dentro de un mismo ejercicio.

#### Scenario: Dos casos con el mismo identificador

- **WHEN** se intenta guardar un ejercicio con dos casos que comparten identificador
- **THEN** el sistema rechaza la operación con un error de validación
