## ADDED Requirements

### Requirement: Endpoint de corrección por ejercicio

El sistema SHALL exponer un endpoint que corrija un ejercicio identificado por su referencia externa, recibiendo el pseudónimo del alumno, el código entregado y, opcionalmente, el resultado de la ejecución de los tests y la referencia externa de la comisión. La corrección SHALL realizarse contra la rúbrica del ejercicio, y la respuesta SHALL incluir la nota y el desglose por criterio de ese ejercicio.

#### Scenario: Corrección de un ejercicio

- **WHEN** se solicita la corrección de un ejercicio vigente con el pseudónimo de un alumno y su código
- **THEN** se corrige contra la rúbrica de ese ejercicio y se devuelve la nota con el desglose por criterio

#### Scenario: Ejercicio inexistente o dado de baja

- **WHEN** se solicita la corrección de una referencia externa de ejercicio que no existe o está dada de baja
- **THEN** el sistema responde 404

#### Scenario: Corrección sin resultado de tests

- **WHEN** se solicita la corrección sin incluir el resultado de la ejecución
- **THEN** la corrección se realiza igual, sin la sección de resultado de ejecución

### Requirement: El sistema no calcula la nota del trabajo práctico

El endpoint SHALL devolver únicamente la nota del ejercicio corregido. El sistema NO SHALL calcular ni devolver una nota agregada del trabajo práctico a partir de los pesos de sus ejercicios.

#### Scenario: Respuesta de una corrección

- **WHEN** se corrige un ejercicio de un trabajo práctico de cuatro
- **THEN** la respuesta contiene la nota de ese ejercicio y no una nota del trabajo práctico

### Requirement: No hay corrección en lote

El sistema SHALL corregir un ejercicio por llamada. NO SHALL exponerse un endpoint que corrija varios ejercicios o varios alumnos en una sola operación por este camino.

#### Scenario: Una llamada, un ejercicio

- **WHEN** el consumidor necesita corregir los cuatro ejercicios de un trabajo práctico
- **THEN** realiza cuatro llamadas independientes, una por ejercicio

### Requirement: Resolución de la comisión de la entrega

El sistema SHALL resolver la comisión de la entrega en este orden: la comisión referenciada por la referencia externa de comisión del cuerpo, si viene y resuelve a una comisión vigente de la materia; en su defecto, la comisión de integración configurada en la materia. Si ninguna resuelve, el sistema SHALL responder 409 indicando explícitamente qué configuración falta, y NO SHALL crear ninguna comisión implícitamente.

#### Scenario: Comisión indicada en el cuerpo

- **WHEN** el cuerpo incluye una referencia externa de comisión que resuelve a una comisión vigente de la materia
- **THEN** la entrega se crea en esa comisión

#### Scenario: Comisión de integración de la materia

- **WHEN** el cuerpo no incluye referencia de comisión y la materia tiene configurada una comisión de integración
- **THEN** la entrega se crea en la comisión de integración

#### Scenario: Sin comisión resoluble

- **WHEN** el cuerpo no trae referencia de comisión y la materia no tiene comisión de integración configurada
- **THEN** el sistema responde 409 indicando que falta configurar la comisión de integración, y no crea ninguna comisión

#### Scenario: Referencia de comisión de otra materia

- **WHEN** el cuerpo trae una referencia externa de comisión que pertenece a otra materia
- **THEN** el sistema responde 409 sin usar esa comisión

### Requirement: Reuso de la entrega y conservación del historial

Cuando ya exista una entrega vigente para el mismo alumno y la misma rúbrica, el sistema SHALL reusarla en lugar de rechazar la operación: SHALL actualizar su código, SHALL guardar la corrección anterior en el historial de correcciones, y SHALL producir una corrección nueva. El sistema NO SHALL responder 409 por una entrega preexistente en este camino.

#### Scenario: Segunda corrección del mismo alumno y ejercicio

- **WHEN** se vuelve a corregir el mismo ejercicio para el mismo pseudónimo de alumno con código actualizado
- **THEN** la entrega existente se reusa, la corrección anterior queda en el historial y se devuelve la corrección nueva

#### Scenario: Primera corrección

- **WHEN** no existe entrega previa para ese alumno y esa rúbrica
- **THEN** se crea la entrega y se produce la corrección

#### Scenario: Independencia entre ejercicios

- **WHEN** el mismo alumno se corrige en dos ejercicios distintos del mismo trabajo práctico
- **THEN** se crean dos entregas independientes, una por rúbrica, sin interferir entre sí

### Requirement: El pseudónimo del alumno se almacena sin enriquecerse

El sistema SHALL almacenar el pseudónimo del alumno tal como lo recibe. NO SHALL intentar resolverlo a una persona, cruzarlo con el padrón de la universidad ni completarlo con datos de ninguna fuente externa.

#### Scenario: Pseudónimo recibido

- **WHEN** se recibe un pseudónimo de alumno en una corrección
- **THEN** se almacena literalmente como identificador del alumno de la entrega, sin ninguna resolución adicional

### Requirement: Permisos y auditoría de la corrección por ejercicio

El endpoint SHALL verificar el acceso del solicitante a la materia del ejercicio y el aislamiento por universidad activa. Cada corrección SHALL registrar una actividad de auditoría con el actor, la referencia externa del ejercicio y el pseudónimo del alumno.

#### Scenario: Solicitante sin acceso a la materia

- **WHEN** un usuario sin acceso a la materia del ejercicio solicita una corrección
- **THEN** el sistema responde 403 sin revelar si el ejercicio existe

#### Scenario: Registro de auditoría

- **WHEN** se completa una corrección por ejercicio
- **THEN** queda registrada una actividad con el actor, la referencia del ejercicio y el pseudónimo del alumno
