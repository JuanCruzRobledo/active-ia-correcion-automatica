## ADDED Requirements

### Requirement: Cada criterio evaluado devuelve la evidencia que respalda su puntaje

El esquema de respuesta enviado al proveedor de IA SHALL incluir, por criterio, un campo `evidencia` con una cita textual y literal del código entregado (de una a tres líneas) que respalde el puntaje asignado. En rúbricas `schema_version >= 2`, cada subcriterio evaluado SHALL incluir su propio campo `evidencia`. El campo SHALL parsearse como opcional, de modo que una respuesta sin evidencia no rompa la corrección.

#### Scenario: Criterio cumplido con evidencia

- **WHEN** la IA cierra un criterio con puntaje completo
- **THEN** la respuesta incluye la cita textual del código que lo respalda y el sistema la persiste junto al criterio

#### Scenario: Subcriterio con evidencia en rúbrica v2

- **WHEN** se corrige contra una rúbrica `schema_version = 2`
- **THEN** cada subcriterio evaluado incluye su propia evidencia

#### Scenario: Respuesta sin el campo de evidencia

- **WHEN** la IA omite `evidencia` en algún criterio
- **THEN** la corrección se parsea y persiste sin error, con la evidencia ausente

### Requirement: El backend verifica que la evidencia exista en el código entregado

Para las correcciones de código, el sistema SHALL verificar que la cita de evidencia de cada criterio aparezca en el código consolidado de la entrega, comparando por subcadena tras normalizar el espaciado (colapso de espacios y tabulaciones, saltos de línea ignorados). La comparación NO SHALL normalizar mayúsculas ni puntuación.

#### Scenario: Evidencia presente en el código

- **WHEN** la cita de un criterio aparece en el código entregado salvo por diferencias de espaciado
- **THEN** la verificación es exitosa y el criterio se persiste sin cambios

#### Scenario: Evidencia con espaciado distinto

- **WHEN** la cita usa distinta cantidad de espacios o tabulaciones que el código original, pero es por lo demás idéntica
- **THEN** la verificación es exitosa

#### Scenario: Evidencia con distinta capitalización

- **WHEN** la cita difiere del código en mayúsculas o minúsculas
- **THEN** la verificación falla, porque la comparación es sensible al case

### Requirement: Un criterio con evidencia no verificable se degrada, no se anula

Cuando la evidencia de un criterio no se encuentre en el código entregado, el sistema SHALL degradar ese criterio: su `estado` SHALL pasar a `WARNING` y su `puntaje_obtenido` SHALL acotarse al 50% del peso que la rúbrica define para ese criterio, conservando el valor original si ya era menor. El feedback del criterio SHALL indicar que la evidencia no pudo verificarse, y el sistema SHALL emitir un log de advertencia con el criterio y la cita no encontrada.

#### Scenario: Criterio cerrado con evidencia inexistente

- **WHEN** la IA cierra un criterio de peso 20 con puntaje 20 y una cita que no aparece en el código
- **THEN** el criterio queda con `estado: WARNING`, `puntaje_obtenido: 10`, feedback anotado y log de advertencia

#### Scenario: Criterio con puntaje ya inferior al techo de degradación

- **WHEN** la IA cierra un criterio de peso 20 con puntaje 6 y una cita que no aparece en el código
- **THEN** el `puntaje_obtenido` se mantiene en 6 y solo se marca `WARNING` con la anotación en el feedback

### Requirement: Exenciones de la verificación de evidencia

El sistema NO SHALL degradar un criterio por evidencia no verificable en ninguno de estos casos: (a) el criterio fue cerrado como no cumplido con puntaje 0; (b) la corrección es de un PDF y no hay código consolidado contra el cual verificar; (c) el código enviado a la IA fue truncado. En el caso (c) el sistema SHALL registrar el log de advertencia igualmente, sin degradar.

#### Scenario: Criterio en cero

- **WHEN** un criterio se cierra con `estado: ERROR` y puntaje 0, sin evidencia o con una cita inexistente
- **THEN** el criterio no se degrada ni se anota

#### Scenario: Corrección de PDF

- **WHEN** se corrige una entrega en formato PDF
- **THEN** la evidencia se solicita en la respuesta pero no se verifica y ningún criterio se degrada por ella

#### Scenario: Código truncado

- **WHEN** el código enviado fue truncado y una cita no se encuentra en el fragmento enviado
- **THEN** el criterio no se degrada, y se registra un log de advertencia indicando que la entrega estaba truncada

### Requirement: El prompt distingue presencia de vínculo

El prompt de corrección SHALL incluir la regla de que declarar, instanciar o nombrar una entidad no cumple por sí solo un criterio que evalúa una relación, un uso o un comportamiento sobre esa entidad, y SHALL exigir que la evidencia de un criterio de vínculo sea la línea donde la relación efectivamente ocurre. La regla SHALL acompañarse de al menos un ejemplo negativo concreto.

#### Scenario: Criterio de asociación entre entidades

- **WHEN** un criterio evalúa que los productos queden asociados a una categoría
- **THEN** el prompt exige como evidencia la línea donde la asociación ocurre, y no la declaración de las clases

### Requirement: El prompt trata el hardcodeo como criterio no cumplido

El prompt de corrección SHALL incluir la regla de que un valor literal embebido que hace pasar un caso puntual sin implementar el algoritmo pedido NO cumple el criterio, con al menos un ejemplo negativo concreto, e SHALL instruir a evaluarlo como no cumplido en lugar de elogiarlo.

#### Scenario: Búsqueda resuelta con un literal

- **WHEN** el código resuelve un criterio de búsqueda con una comparación contra un valor literal en lugar de recorrer la estructura
- **THEN** el prompt instruye a tratar el criterio como no cumplido

### Requirement: La evidencia se muestra al tutor y no se incluye en el PDF del alumno

El frontend de correcciones SHALL mostrar la evidencia citada dentro de cada criterio en la vista de revisión del tutor, tolerando su ausencia en correcciones previas. El PDF de devolución al alumno NO SHALL incluir la evidencia.

#### Scenario: Revisión del tutor

- **WHEN** el tutor abre una corrección que tiene evidencia por criterio
- **THEN** ve la cita de código junto a cada criterio

#### Scenario: Corrección anterior al change

- **WHEN** el tutor abre una corrección que no tiene evidencia
- **THEN** la corrección se muestra sin la sección de evidencia y sin errores

#### Scenario: PDF de devolución

- **WHEN** se genera el PDF de devolución de una corrección con evidencia
- **THEN** el PDF no incluye las citas de evidencia

### Requirement: Las reglas de evidencia aplican a todos los proveedores

Los campos de evidencia en el esquema de respuesta y las reglas de vínculo y hardcodeo en el prompt SHALL aplicarse a los proveedores Gemini y OpenRouter, y a los caminos de corrección de código y de PDF.

#### Scenario: Corrección v2 con OpenRouter

- **WHEN** se corrige una entrega de rúbrica v2 usando OpenRouter
- **THEN** el esquema de respuesta incluye evidencia por criterio y por subcriterio, igual que con Gemini
