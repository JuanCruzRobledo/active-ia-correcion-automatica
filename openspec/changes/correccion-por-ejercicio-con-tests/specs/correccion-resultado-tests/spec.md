## ADDED Requirements

### Requirement: El resultado de la ejecución se acepta como parte de la solicitud de corrección

El sistema SHALL aceptar, junto con el código a corregir, un bloque con el resultado de la ejecución de los tests que contenga: si el código compila, el error de compilación cuando corresponda, el total de casos, la cantidad de casos pasados, y el detalle por caso con su identificador, si pasó, la entrada, la salida esperada y la salida obtenida. El bloque SHALL ser opcional.

#### Scenario: Solicitud con resultado de ejecución

- **WHEN** se corrige un ejercicio incluyendo el resultado de la ejecución de cuatro casos, todos pasados
- **THEN** el resultado se acepta y se incorpora a la corrección

#### Scenario: Solicitud sin resultado de ejecución

- **WHEN** se corrige un ejercicio sin incluir resultado de ejecución
- **THEN** la corrección procede sin esa información, sin error

### Requirement: El estado de compilación es un dato propio y no se deduce

El sistema SHALL tratar la marca de compilación como un dato independiente de la cantidad de casos pasados, y NO SHALL inferirla a partir de que ningún caso haya pasado. Un código que no compila y un código que compila pero falla todos los casos SHALL producir devoluciones distintas.

#### Scenario: No compila

- **WHEN** el resultado indica que el código no compila, con cero de seis casos pasados y un error de compilación
- **THEN** la corrección refleja un error de compilación y usa el mensaje del compilador en la devolución

#### Scenario: Compila y falla todo

- **WHEN** el resultado indica que el código compila, con cero de seis casos pasados
- **THEN** la corrección refleja que el programa corre pero produce un comportamiento distinto al pedido, sin mencionar un error de compilación

### Requirement: El resultado de la ejecución se transmite al motor como hecho establecido

Cuando la solicitud incluya el resultado de la ejecución, el prompt de corrección SHALL renderizarlo como sección propia, previa a los criterios, e SHALL instruir explícitamente que ese resultado proviene de una ejecución real, que constituye un hecho establecido y no una sugerencia, y que el motor no debe volver a deducir si el programa funciona.

#### Scenario: Sección de resultado de ejecución en el prompt

- **WHEN** se construye el prompt con un resultado de ejecución
- **THEN** el prompt incluye la sección con la marca de compilación, el conteo de casos y el detalle por caso, junto con la instrucción de tratarlo como hecho establecido

#### Scenario: Prompt sin resultado de ejecución

- **WHEN** se construye el prompt sin resultado de ejecución
- **THEN** la sección no aparece y el prompt es el que corresponde al camino sin tests

### Requirement: El error de compilación está disponible para la devolución

Cuando el código no compile, el sistema SHALL poner el mensaje del compilador a disposición del motor para que lo use en la devolución al alumno.

#### Scenario: Devolución de un código que no compila

- **WHEN** se corrige un código que no compila, con el error del compilador en la solicitud
- **THEN** el mensaje del compilador está disponible en el prompt y puede citarse en la devolución

### Requirement: Acotamiento del tamaño del resultado de ejecución

El sistema SHALL acotar el tamaño del resultado de ejecución que envía al motor. Cuando haya que recortar, SHALL priorizar los casos que fallaron sobre los que pasaron, y SHALL indicar en el prompt que el detalle fue recortado.

#### Scenario: Resultado con muchos casos y salidas largas

- **WHEN** el resultado de ejecución excede el tamaño admitido
- **THEN** se envían primero los casos fallados, el detalle se recorta y el prompt indica que hubo recorte

#### Scenario: Resultado dentro del límite

- **WHEN** el resultado de ejecución no excede el tamaño admitido
- **THEN** se envía completo, sin indicación de recorte

### Requirement: El resultado de la ejecución se conserva con la corrección

El sistema SHALL persistir el resultado de la ejecución recibido junto con la corrección, de modo que una corrección pueda auditarse a posteriori sabiendo con qué evidencia de ejecución fue producida.

#### Scenario: Auditoría de una corrección con tests

- **WHEN** se consulta una corrección producida con resultado de ejecución
- **THEN** el resultado de ejecución con el que se produjo está disponible

#### Scenario: Corrección sin resultado de ejecución

- **WHEN** se consulta una corrección producida sin resultado de ejecución
- **THEN** el campo correspondiente está vacío y la corrección se lee sin error
