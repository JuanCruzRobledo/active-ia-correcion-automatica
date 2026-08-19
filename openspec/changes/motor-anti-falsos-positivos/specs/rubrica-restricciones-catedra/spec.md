## ADDED Requirements

### Requirement: La rúbrica declara las restricciones de la cátedra

Una rúbrica SHALL poder declarar una lista de restricciones dentro de su metadata, donde cada restricción tiene un identificador, una descripción de la construcción, librería o enfoque restringido, y un alcance que SHALL ser `prohibido_en_codigo` o `no_recomendar`. La lista SHALL ser opcional: una rúbrica sin restricciones SHALL validarse y corregir exactamente como antes del change. El shape de cada restricción SHALL validarse, rechazando entradas sin identificador, sin descripción o con un alcance desconocido.

#### Scenario: Rúbrica con restricciones válidas

- **WHEN** se crea una rúbrica cuya metadata declara una restricción con identificador, descripción y alcance `no_recomendar`
- **THEN** la rúbrica se valida y persiste con esa restricción

#### Scenario: Rúbrica sin restricciones

- **WHEN** se crea o actualiza una rúbrica sin declarar restricciones
- **THEN** la rúbrica se valida y persiste igual que antes del change

#### Scenario: Restricción con alcance desconocido

- **WHEN** se declara una restricción con un alcance distinto de `prohibido_en_codigo` y `no_recomendar`
- **THEN** el sistema rechaza la operación con un error de validación

#### Scenario: Restricción incompleta

- **WHEN** se declara una restricción sin descripción o sin identificador
- **THEN** el sistema rechaza la operación con un error de validación

### Requirement: El motor no recomienda lo que la cátedra veda

El prompt de corrección SHALL renderizar las restricciones declaradas en la rúbrica como una restricción dura sobre la salida: el motor NO SHALL proponer en `recomendaciones` ni en el feedback de ningún criterio una construcción, librería o enfoque declarado como restringido, aunque constituya una buena práctica general.

#### Scenario: Construcción vedada por la cátedra

- **WHEN** la rúbrica declara una restricción sobre el manejo de excepciones con alcance `no_recomendar` y el código del alumno podría beneficiarse de él
- **THEN** el prompt instruye explícitamente a no recomendarlo, y la sección de restricciones lo lista con su descripción

#### Scenario: Rúbrica sin restricciones declaradas

- **WHEN** se corrige contra una rúbrica sin restricciones
- **THEN** el prompt no incluye la sección de restricciones y el comportamiento es idéntico al previo

### Requirement: Las restricciones informan el juicio pero no descuentan por sí solas

Una restricción con alcance `prohibido_en_codigo` SHALL informarse al motor como parte del contexto de evaluación, pero NO SHALL generar por sí sola un descuento automático sobre la nota. El descuento por usar una construcción prohibida SHALL expresarse mediante una penalización de la rúbrica.

#### Scenario: Alumno que usa una construcción prohibida

- **WHEN** la rúbrica declara una restricción `prohibido_en_codigo` y el código del alumno la usa
- **THEN** el motor lo señala en el feedback, y la nota solo se reduce si la rúbrica define además una penalización correspondiente

### Requirement: Edición de restricciones desde el frontend de rúbricas

El editor de rúbricas SHALL permitir agregar, editar y eliminar restricciones de cátedra, con su descripción y su alcance, validando el shape en el cliente antes de enviar. Las rúbricas existentes SHALL abrirse en el editor sin restricciones declaradas y sin error.

#### Scenario: Alta de una restricción

- **WHEN** el coordinador agrega una restricción con descripción y alcance en el editor de rúbricas
- **THEN** la restricción se envía y se persiste en la rúbrica

#### Scenario: Rúbrica preexistente en el editor

- **WHEN** se abre en el editor una rúbrica creada antes del change
- **THEN** la sección de restricciones aparece vacía y la rúbrica se puede guardar sin declarar ninguna
