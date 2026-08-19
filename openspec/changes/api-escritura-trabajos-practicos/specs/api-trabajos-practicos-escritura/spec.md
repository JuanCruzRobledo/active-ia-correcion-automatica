## ADDED Requirements

### Requirement: Alta de un trabajo práctico con sus ejercicios anidados

El sistema SHALL exponer un endpoint de creación de trabajo práctico que reciba el identificador externo del trabajo práctico, el identificador externo de la materia, el título y la lista de ejercicios anidados con su identificador externo, orden, título, enunciado, peso, rúbrica y casos de prueba. La operación SHALL crear el trabajo práctico, cada ejercicio y la rúbrica de cada ejercicio, y SHALL responder con estado 201.

#### Scenario: Alta de un trabajo práctico con cuatro ejercicios

- **WHEN** se envía un trabajo práctico con cuatro ejercicios, cada uno con su rúbrica de criterios
- **THEN** se crean el trabajo práctico, los cuatro ejercicios y las cuatro rúbricas, y la respuesta es 201

#### Scenario: Materia identificada por su referencia externa

- **WHEN** el cuerpo trae el identificador externo de una materia existente en la universidad activa
- **THEN** la materia se resuelve y el trabajo práctico queda asociado a ella

#### Scenario: Materia inexistente

- **WHEN** el identificador externo de materia no corresponde a ninguna materia vigente de la universidad activa
- **THEN** el sistema responde 404 indicando el identificador que no pudo resolverse, y no crea ninguna materia

### Requirement: Upsert idempotente por identificador externo

El sistema SHALL exponer un endpoint de actualización por identificador externo del trabajo práctico que cree el trabajo práctico si no existe y lo actualice si existe. Reenviar el mismo cuerpo SHALL producir el mismo estado final, sin duplicar trabajos prácticos ni ejercicios. La respuesta SHALL ser 201 cuando la operación creó el trabajo práctico y 200 cuando lo actualizó.

#### Scenario: Primera publicación

- **WHEN** se envía un trabajo práctico por identificador externo que aún no existe
- **THEN** se crea y la respuesta es 201

#### Scenario: Republicación idéntica

- **WHEN** se reenvía exactamente el mismo cuerpo sobre el mismo identificador externo
- **THEN** la respuesta es 200 y no se crea ningún trabajo práctico ni ejercicio adicional

#### Scenario: Republicación con cambios

- **WHEN** se reenvía el trabajo práctico con el título modificado y un criterio de rúbrica distinto
- **THEN** el trabajo práctico existente se actualiza en su lugar y la respuesta es 200

### Requirement: Consulta de un trabajo práctico por identificador externo

El sistema SHALL exponer un endpoint de consulta de trabajo práctico por su identificador externo, que devuelva el trabajo práctico con sus ejercicios vigentes. Si no existe un trabajo práctico vigente con ese identificador en la universidad activa, SHALL responder 404.

#### Scenario: Consulta exitosa

- **WHEN** se consulta por el identificador externo de un trabajo práctico vigente
- **THEN** se devuelve el trabajo práctico con sus ejercicios

#### Scenario: Consulta de un identificador inexistente

- **WHEN** se consulta por un identificador externo que no existe
- **THEN** el sistema responde 404

#### Scenario: Trabajo práctico dado de baja

- **WHEN** se consulta por el identificador externo de un trabajo práctico dado de baja
- **THEN** el sistema responde 404

### Requirement: La respuesta identifica la rúbrica de cada ejercicio

Las respuestas de alta, de upsert y de consulta SHALL incluir, por cada ejercicio, su identificador externo, su identificador interno, su orden, su título, su peso y el identificador de su rúbrica. El consumidor NO SHALL necesitar inferir la correspondencia entre ejercicio y rúbrica por posición ni por título.

#### Scenario: Respuesta de un trabajo práctico con cuatro ejercicios

- **WHEN** se obtiene la respuesta de un trabajo práctico con cuatro ejercicios
- **THEN** cada ejercicio de la respuesta trae su identificador externo y el identificador de su rúbrica

#### Scenario: Correspondencia estable tras un upsert

- **WHEN** se republica un trabajo práctico y se compara la respuesta con la del push anterior
- **THEN** cada ejercicio conserva el mismo identificador de rúbrica que tenía

### Requirement: Atomicidad de la escritura

Las operaciones de alta y de upsert SHALL ser atómicas: si alguna parte del cuerpo es inválida o alguna escritura falla, el sistema NO SHALL persistir ninguna parte de la operación.

#### Scenario: Fallo de validación en un ejercicio intermedio

- **WHEN** se envía un trabajo práctico de cuatro ejercicios donde el tercero es inválido
- **THEN** el sistema responde con error y no queda persistido ni el trabajo práctico ni ningún ejercicio

#### Scenario: Reintento tras corregir el error

- **WHEN** se corrige el ejercicio inválido y se reenvía el cuerpo completo
- **THEN** la operación se completa y el estado final es el esperado, sin residuos del intento fallido

### Requirement: Los errores de contrato identifican el elemento infractor

Cuando el cuerpo viole el contrato, el sistema SHALL responder 422 e indicar en el detalle qué ejercicio y, si corresponde, qué caso de prueba causó el rechazo. SHALL rechazarse: un caso de prueba no público que incluya salida esperada o aserción, un tipo de caso desconocido, identificadores de caso duplicados dentro de un ejercicio, e identificadores externos de ejercicio duplicados dentro del mismo cuerpo.

#### Scenario: Caso oculto con salida esperada

- **WHEN** el cuerpo incluye un caso de prueba no público con salida esperada
- **THEN** el sistema responde 422 nombrando el ejercicio y el caso, y no persiste nada

#### Scenario: Identificadores de ejercicio duplicados en el mismo push

- **WHEN** el cuerpo incluye dos ejercicios con el mismo identificador externo
- **THEN** el sistema responde 422 nombrando el identificador duplicado

#### Scenario: Tipo de caso desconocido

- **WHEN** el cuerpo incluye un caso de prueba con un tipo no admitido
- **THEN** el sistema responde 422 nombrando el ejercicio y el caso

### Requirement: Permisos de escritura y de lectura

Las operaciones de alta y de upsert SHALL requerir rol coordinador o administrador sobre la universidad activa, más acceso a la materia del trabajo práctico. La consulta SHALL admitir además el rol tutor con acceso a la materia. Un usuario sin acceso a la materia SHALL recibir 403 sin que la respuesta revele si el recurso existe.

#### Scenario: Escritura con rol tutor

- **WHEN** un usuario con rol tutor intenta publicar un trabajo práctico
- **THEN** el sistema responde 403

#### Scenario: Consulta con rol tutor

- **WHEN** un usuario con rol tutor y acceso a la materia consulta un trabajo práctico de esa materia
- **THEN** la consulta es exitosa

#### Scenario: Acceso a una materia ajena

- **WHEN** un coordinador sin acceso a la materia intenta publicar un trabajo práctico de esa materia
- **THEN** el sistema responde 403 sin revelar si el trabajo práctico existe

### Requirement: Auditoría de las escrituras

Cada operación de alta y de upsert SHALL registrar una actividad de auditoría con el actor, el identificador externo del trabajo práctico, y la cantidad de ejercicios creados, actualizados y dados de baja en esa operación.

#### Scenario: Auditoría de un upsert con cambios

- **WHEN** un upsert crea un ejercicio, actualiza dos y da de baja uno
- **THEN** queda registrada una actividad con el actor, el identificador externo y esos tres contadores
