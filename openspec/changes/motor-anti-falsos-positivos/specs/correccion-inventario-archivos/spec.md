## ADDED Requirements

### Requirement: El inventario de archivos de la entrega viaja al motor de corrección

El payload de corrección SHALL incluir un bloque con los datos de la entrega: la lista de archivos consolidados (`archivos_incluidos`), el nombre y el tipo del archivo original. Cuando la entrega no registre archivos consolidados, el bloque SHALL incluir al menos el nombre del archivo original como único elemento del inventario.

#### Scenario: Entrega ZIP con varios archivos consolidados

- **WHEN** se corrige una entrega cuyo `archivos_incluidos` tiene `["Main.java", "Evento.java", "CupoExcedidoException.java"]`
- **THEN** el payload enviado al proveedor de IA incluye esos tres nombres en el inventario de la entrega

#### Scenario: Entrega de archivo único sin consolidación

- **WHEN** se corrige una entrega cuyo `archivos_incluidos` es nulo o vacío
- **THEN** el inventario contiene el nombre del archivo original de la entrega

### Requirement: El prompt prohíbe descontar por archivos presentes en el inventario

El prompt de corrección SHALL renderizar el inventario de archivos como sección propia, previa al código, e incluir la regla de que ningún archivo listado en el inventario puede considerarse ausente. El motor SHALL poder seguir señalando como ausente un archivo que el criterio requiera y que NO figure en el inventario.

#### Scenario: Criterio sobre un archivo listado

- **WHEN** un criterio evalúa la presencia de un archivo que figura en el inventario
- **THEN** el prompt instruye explícitamente a no descontar puntaje por ausencia de ese archivo

#### Scenario: Criterio sobre un archivo realmente ausente

- **WHEN** un criterio requiere un archivo que no figura en el inventario
- **THEN** el prompt permite señalarlo como ausente y descontar el criterio correspondiente

### Requirement: El estado de truncado del código se informa de forma estructurada

Cuando el código consolidado se trunque antes de enviarse al proveedor de IA, el payload SHALL informarlo en un campo estructurado, con la cantidad de caracteres original y la cantidad efectivamente enviada, además del marcador textual existente dentro del código. El prompt SHALL advertir que el código está incompleto y que la ausencia de una construcción puede deberse al corte.

#### Scenario: Código truncado

- **WHEN** el código consolidado supera el límite y se trunca
- **THEN** el payload marca la entrega como truncada, informa caracteres originales y enviados, y el prompt advierte que el código está incompleto

#### Scenario: Código completo

- **WHEN** el código consolidado no supera el límite
- **THEN** el payload marca la entrega como no truncada y el prompt no incluye la advertencia

### Requirement: El inventario aplica a todos los prompts y proveedores

El bloque de inventario y truncado SHALL incluirse tanto en el camino de corrección de código como en el de PDF, y por lo tanto SHALL aplicar a los proveedores Gemini y OpenRouter, que comparten los constructores de prompt. En el camino de PDF, el inventario SHALL describir el archivo PDF entregado.

#### Scenario: Corrección con OpenRouter

- **WHEN** se corrige una entrega usando el proveedor OpenRouter
- **THEN** el prompt incluye el inventario y la regla de no descontar por archivos listados, igual que con Gemini

#### Scenario: Corrección de PDF

- **WHEN** se corrige una entrega en formato PDF
- **THEN** el payload incluye el nombre del archivo PDF entregado como inventario
