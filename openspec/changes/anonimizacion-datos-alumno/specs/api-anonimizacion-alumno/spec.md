## ADDED Requirements

### Requirement: Endpoint de anonimización de los datos de un alumno

El sistema SHALL exponer un endpoint que anonimice todos los datos asociados a un pseudónimo de alumno dentro de la universidad del solicitante, y que devuelva la cantidad de entregas y de correcciones alcanzadas junto con el identificador anónimo resultante.

#### Scenario: Anonimización exitosa

- **WHEN** se solicita la anonimización de un pseudónimo con tres entregas corregidas
- **THEN** la operación se completa y la respuesta informa tres entregas, tres correcciones y el identificador anónimo

#### Scenario: Respuesta sin datos personales

- **WHEN** se obtiene la respuesta de una anonimización
- **THEN** la respuesta no incluye el pseudónimo original ni ningún dato destruido

### Requirement: Confirmación explícita antes de ejecutar

La operación SHALL requerir una confirmación explícita en la petición. Sin esa confirmación, el sistema NO SHALL destruir nada y SHALL responder indicando cuántas entregas y correcciones alcanzaría la operación.

#### Scenario: Petición sin confirmación

- **WHEN** se solicita la anonimización sin la confirmación explícita
- **THEN** el sistema responde con el conteo de lo que alcanzaría y no destruye ningún dato

#### Scenario: Petición con confirmación

- **WHEN** se solicita la anonimización con la confirmación explícita
- **THEN** la operación se ejecuta

### Requirement: La operación es idempotente

Solicitar la anonimización de un pseudónimo ya anonimizado o inexistente SHALL responder con éxito e informar que alcanzó cero entregas, sin error.

#### Scenario: Pseudónimo ya anonimizado

- **WHEN** se solicita por segunda vez la anonimización del mismo pseudónimo
- **THEN** la respuesta es exitosa e informa cero entregas alcanzadas

#### Scenario: Pseudónimo inexistente

- **WHEN** se solicita la anonimización de un pseudónimo que nunca existió
- **THEN** la respuesta es exitosa e informa cero entregas alcanzadas

### Requirement: Permisos de la anonimización

La operación SHALL requerir rol de administrador sobre la universidad activa, o una identidad con un permiso de anonimización explícitamente otorgado. El permiso de anonimización SHALL ser independiente de los permisos de escritura y de corrección.

#### Scenario: Solicitud por un administrador

- **WHEN** un administrador solicita la anonimización de un pseudónimo de su universidad
- **THEN** la operación se permite

#### Scenario: Solicitud por un coordinador

- **WHEN** un coordinador solicita una anonimización
- **THEN** el sistema responde 403

#### Scenario: Identidad con permiso de escritura pero no de anonimización

- **WHEN** una identidad automatizada con permiso de escritura y de corrección, pero sin permiso de anonimización, solicita la operación
- **THEN** el sistema responde 403

#### Scenario: Pseudónimo de otra universidad

- **WHEN** se solicita la anonimización de un pseudónimo que solo existe en otra universidad
- **THEN** la respuesta informa cero entregas alcanzadas y no se anonimiza nada de esa otra universidad
