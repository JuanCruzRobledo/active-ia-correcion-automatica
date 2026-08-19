## ADDED Requirements

### Requirement: Un criterio puede declararse dependiente de la ejecución

Un criterio de rúbrica SHALL poder declarar que su cumplimiento requiere que el programa se ejecute. La marca SHALL ser opcional y su valor por defecto SHALL ser negativo, de modo que las rúbricas existentes conserven su comportamiento sin ninguna modificación ni backfill.

#### Scenario: Criterio marcado como dependiente de ejecución

- **WHEN** se crea una rúbrica con un criterio declarado como dependiente de la ejecución
- **THEN** la rúbrica se valida y persiste con esa marca

#### Scenario: Rúbrica existente sin la marca

- **WHEN** se corrige contra una rúbrica cuyos criterios no declaran dependencia de ejecución
- **THEN** el comportamiento es idéntico al previo al change

### Requirement: Los criterios dependientes de ejecución se cierran en cero cuando el código no compila

Cuando la solicitud de corrección indique que el código no compila, el sistema SHALL forzar en el backend, de forma determinística, que todo criterio declarado como dependiente de la ejecución quede con puntaje cero y estado de error, con un feedback que cite el mensaje del compilador. El forzado SHALL aplicarse antes de la suma de criterios, integrado a la cadena de cálculo determinístico de la nota. El sistema NO SHALL delegar esta regla al motor de IA.

#### Scenario: Código que no compila con criterios de ejecución

- **WHEN** se corrige un código que no compila, contra una rúbrica con dos criterios dependientes de ejecución
- **THEN** esos dos criterios quedan en cero con estado de error, su feedback cita el error del compilador, y la nota lo refleja

#### Scenario: El motor asignó puntaje a un criterio de ejecución

- **WHEN** el código no compila y el motor devolvió puntaje positivo para un criterio dependiente de ejecución
- **THEN** el sistema descarta ese puntaje y lo fuerza a cero

#### Scenario: Criterios no dependientes de ejecución

- **WHEN** el código no compila y la rúbrica tiene además criterios de diseño no dependientes de ejecución
- **THEN** esos criterios se evalúan normalmente y conservan el puntaje que el motor les asignó

### Requirement: Compilar y fallar los tests no fuerza ningún criterio

Cuando la solicitud indique que el código compila, el sistema NO SHALL forzar en cero ningún criterio, cualquiera sea la cantidad de casos pasados. El resultado de la ejecución SHALL informarse al motor como hecho, y la ponderación SHALL quedar a su juicio.

#### Scenario: Compila y no pasa ningún caso

- **WHEN** se corrige un código que compila y no pasa ninguno de sus seis casos
- **THEN** ningún criterio se fuerza en cero y el motor evalúa con el resultado de ejecución a la vista

### Requirement: Sin resultado de ejecución no se fuerza ningún criterio

Cuando la solicitud no incluya resultado de ejecución, el sistema NO SHALL forzar en cero ningún criterio por dependencia de ejecución, aunque la rúbrica declare la marca.

#### Scenario: Corrección sin tests sobre una rúbrica con criterios de ejecución

- **WHEN** se corrige sin resultado de ejecución contra una rúbrica que declara criterios dependientes de ejecución
- **THEN** ningún criterio se fuerza y la corrección procede como cualquier otra

### Requirement: Los criterios forzados en cero quedan exentos de la verificación de evidencia

Un criterio forzado en cero por no compilar NO SHALL degradarse ni anotarse por evidencia no verificable.

#### Scenario: Criterio forzado sin evidencia citable

- **WHEN** un criterio dependiente de ejecución se fuerza en cero por no compilar y no tiene evidencia citable
- **THEN** el criterio no recibe ninguna degradación ni anotación adicional por evidencia
