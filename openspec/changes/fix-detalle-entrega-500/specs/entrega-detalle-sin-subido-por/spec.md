## ADDED Requirements

### Requirement: El detalle de una entrega sin usuario que la haya subido se sirve correctamente

El sistema SHALL devolver el detalle de una entrega cuyo usuario que la subió sea nulo, sin producir un error interno. El campo correspondiente en la respuesta SHALL admitir el valor nulo, y el resto del detalle SHALL devolverse íntegro.

#### Scenario: Entrega importada automáticamente

- **WHEN** se consulta el detalle de una entrega cuyo usuario que la subió es nulo
- **THEN** el sistema responde 200 con el detalle completo y el campo del usuario en nulo

#### Scenario: Entrega subida por un usuario

- **WHEN** se consulta el detalle de una entrega que sí tiene usuario que la subió
- **THEN** el sistema responde 200 con los datos de ese usuario, igual que antes del change

#### Scenario: Entrega inexistente

- **WHEN** se consulta el detalle de una entrega que no existe
- **THEN** el sistema responde 404, igual que antes del change

### Requirement: El resto del detalle no se altera

Los demás campos del detalle de la entrega —comisión, rúbrica, estado, si tiene corrección y la cantidad de versiones anteriores— SHALL devolverse con el mismo contenido y la misma forma que antes del change, exista o no el usuario que la subió.

#### Scenario: Detalle de una entrega sin usuario con corrección e historial

- **WHEN** se consulta el detalle de una entrega sin usuario que la subió, que está corregida y tiene versiones anteriores
- **THEN** la respuesta trae la comisión, la rúbrica, la marca de corrección y el conteo de versiones anteriores correctamente

### Requirement: El identificador del usuario que subió la entrega admite la ausencia en toda la API

El campo con el identificador del usuario que subió la entrega SHALL admitir el valor nulo en **todas** las respuestas que lo expongan, no solo en el detalle. El sistema NO SHALL declararlo obligatorio en ningún contrato de salida.

#### Scenario: Respuesta base de una entrega sin usuario

- **WHEN** una respuesta que incluye el identificador del usuario que subió la entrega corresponde a una entrega importada automáticamente
- **THEN** el campo viaja nulo y la respuesta se serializa sin error

### Requirement: El tipado del cliente refleja la nulabilidad

Los tipos del frontend que describen una entrega y su detalle SHALL declarar como opcionales el identificador y los datos del usuario que la subió, en coherencia con el contrato del backend.

#### Scenario: Tipo de entrega en el cliente

- **WHEN** se consulta el tipo que describe una entrega en el cliente
- **THEN** el identificador del usuario que la subió admite el valor nulo

#### Scenario: Tipo de detalle de entrega en el cliente

- **WHEN** se consulta el tipo que describe el detalle de una entrega en el cliente
- **THEN** los datos del usuario que la subió admiten el valor nulo y coinciden en nombre y forma con lo que devuelve el backend
