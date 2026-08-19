## ADDED Requirements

### Requirement: Las penalizaciones de la rúbrica reducen la nota en el backend

El sistema SHALL calcular el descuento por penalización en el backend, tomando `descuento_porcentaje` de la **rúbrica** y no de la respuesta de la IA. Para cada penalización declarada por la IA cuyo `id` exista en `penalizaciones_json`, el sistema SHALL descontar `suma_criterios × descuento_porcentaje / 100`. Los descuentos de múltiples penalizaciones SHALL calcularse todos sobre la misma base (la suma de criterios), no en cascada. La nota resultante SHALL acotarse inferiormente a 0.

#### Scenario: Penalización del 30% sobre el total

- **WHEN** la suma de criterios es 87 y la IA declara una penalización `P1` que la rúbrica define con `descuento_porcentaje: 30`
- **THEN** `nota_antes_penalizaciones` es 87.00 y la nota final es 60.90

#### Scenario: Dos penalizaciones sobre la misma base

- **WHEN** la suma de criterios es 100 y la IA declara `P1` (20%) y `P2` (30%), ambas presentes en la rúbrica
- **THEN** el descuento total es 50.00 y la nota final es 50.00

#### Scenario: Penalización con id inexistente en la rúbrica

- **WHEN** la IA declara una penalización cuyo `id` no está en `penalizaciones_json` de la rúbrica
- **THEN** el sistema no aplica ningún descuento por ella, no la incluye en `penalizaciones_aplicadas`, y registra un log WARNING con el id descartado

#### Scenario: Descuento que excedería la nota mínima

- **WHEN** la suma de criterios es 20 y las penalizaciones válidas suman un descuento de 30 puntos
- **THEN** la nota final es 0.00 y no un valor negativo

#### Scenario: Corrección sin penalizaciones declaradas

- **WHEN** la IA devuelve `penalizaciones_aplicadas` vacío
- **THEN** la nota final es la suma de criterios, idéntica al comportamiento previo

### Requirement: Orden de aplicación de descuentos y techo por condición de desaprobación

El sistema SHALL aplicar el descuento por penalizaciones **antes** del techo por condición de desaprobación. La nota final SHALL ser `min(suma_criterios − descuentos, nota_maxima_de_la_condicion)` cuando la IA declare una condición de desaprobación cuyo `id` exista en la rúbrica.

#### Scenario: Penalización y condición de desaprobación combinadas

- **WHEN** la suma de criterios es 80, hay una penalización del 25% y una condición de desaprobación con `nota_maxima: 40`
- **THEN** el descuento es 20.00, la nota penada es 60.00 y la nota final es 40.00 (el techo manda)

#### Scenario: Techo por encima de la nota penada

- **WHEN** la suma de criterios es 80, hay una penalización del 50% y una condición de desaprobación con `nota_maxima: 60`
- **THEN** la nota final es 40.00 (la nota penada, que ya está por debajo del techo)

### Requirement: El puntaje del criterio se recomputa como suma de sus subcriterios en rúbricas v2

Cuando la rúbrica tenga `schema_version >= 2` y un criterio evaluado traiga `subcriterios_evaluados` no vacío, el sistema SHALL recomputar `puntaje_obtenido` del criterio como la suma de los puntajes de sus subcriterios, descartando el valor devuelto por la IA para ese criterio. Cada subcriterio SHALL acotarse a su `puntaje_maximo` antes de sumar, y la suma resultante SHALL acotarse al `peso` que la rúbrica define para ese criterio. En rúbricas `schema_version = 1`, o cuando el criterio no traiga desglose, el `puntaje_obtenido` devuelto por la IA SHALL respetarse sin cambios.

#### Scenario: Criterio que no cierra con sus subcriterios

- **WHEN** la IA devuelve un criterio con `puntaje_obtenido: 0` cuyos `subcriterios_evaluados` suman 5, sobre una rúbrica v2
- **THEN** el criterio se persiste con `puntaje_obtenido: 5`, la nota lo refleja, y se registra un log WARNING con la discrepancia

#### Scenario: Subcriterio por encima de su máximo

- **WHEN** un subcriterio con `puntaje_maximo: 4` viene con `puntaje_obtenido: 7`
- **THEN** se computa como 4 y la suma del criterio usa ese valor acotado

#### Scenario: Suma de subcriterios por encima del peso del criterio

- **WHEN** los subcriterios de un criterio cuyo `peso` en la rúbrica es 10 suman 13 tras acotarlos individualmente
- **THEN** el `puntaje_obtenido` del criterio se acota a 10

#### Scenario: Rúbrica v1 sin cambio de comportamiento

- **WHEN** se corrige una entrega contra una rúbrica `schema_version = 1`
- **THEN** el `puntaje_obtenido` de cada criterio es el que devolvió la IA, sin recomputo

#### Scenario: Criterio v2 sin desglose

- **WHEN** una rúbrica es v2 pero la IA omite `subcriterios_evaluados` en un criterio
- **THEN** el `puntaje_obtenido` de ese criterio se respeta tal cual, sin error

### Requirement: El prompt instruye declarar penalizaciones, no aplicarlas

El prompt enviado a la IA SHALL pedir que las penalizaciones incumplidas se reporten únicamente como identificadores en `penalizaciones_aplicadas`, y SHALL indicar explícitamente que **no** debe ajustar el `puntaje_obtenido` de ningún criterio por causa de una penalización. El texto que hoy instruye aplicar el descuento reduciendo el criterio afectado SHALL eliminarse. Este cambio SHALL aplicarse a los prompts de código y de PDF, y por lo tanto a los proveedores Gemini y OpenRouter, que comparten los constructores.

#### Scenario: Sección de penalizaciones del prompt

- **WHEN** se construye el prompt de corrección para una rúbrica con penalizaciones
- **THEN** cada penalización se lista con su `id` y su descripción, sin instrucción de aplicar el descuento, y las instrucciones piden reportar solo los ids incumplidos

#### Scenario: Prompt de PDF y proveedor OpenRouter

- **WHEN** se construye el prompt de corrección de PDF, o se corrige usando OpenRouter
- **THEN** la sección de penalizaciones es la misma que la del camino de código con Gemini

### Requirement: Trazabilidad del cálculo de la nota

El sistema SHALL persistir el detalle del cálculo de la nota junto a la corrección: la suma de criterios previa a los descuentos, y por cada penalización aplicada su `id`, su descripción, su porcentaje y los puntos descontados. `nota_antes_penalizaciones` SHALL poblarse siempre que se aplique un descuento por penalización o un techo por condición de desaprobación, y SHALL quedar en `NULL` cuando la nota final sea la suma limpia de criterios. El detalle SHALL persistirse dentro de la columna JSONB existente de criterios, sin requerir migración de esquema, y el campo `penalizaciones_aplicadas` SHALL conservar su shape actual de lista de identificadores.

#### Scenario: Corrección con descuento aplicado

- **WHEN** se persiste una corrección donde una penalización descontó puntos
- **THEN** la corrección expone la suma previa, el detalle del descuento (id, descripción, porcentaje, puntos) y la nota final, y `nota_antes_penalizaciones` no es nulo

#### Scenario: Corrección sin descuento ni techo

- **WHEN** se persiste una corrección sin penalizaciones ni condición de desaprobación
- **THEN** `nota_antes_penalizaciones` es nulo y la corrección se lee igual que hoy

#### Scenario: Consumidores existentes no se rompen

- **WHEN** el frontend o el generador de PDF leen los criterios de una corrección nueva
- **THEN** encuentran la lista de criterios en la misma ubicación y con el mismo shape que antes del change

### Requirement: El PDF de devolución muestra el desglose del cálculo

Cuando una corrección tenga descuentos por penalización o techo por condición de desaprobación, el PDF de devolución SHALL mostrar el cálculo: suma de criterios, cada descuento aplicado con su descripción y sus puntos, el techo si corresponde, y la nota final. Cuando no haya descuentos ni techo, el PDF SHALL mantenerse idéntico al actual.

#### Scenario: PDF de una corrección penalizada

- **WHEN** se genera el PDF de una corrección con una penalización aplicada
- **THEN** el PDF muestra la suma previa, la penalización con su descripción y los puntos descontados, y la nota final

#### Scenario: PDF de una corrección limpia

- **WHEN** se genera el PDF de una corrección sin penalizaciones ni condición aplicada
- **THEN** el PDF no incluye la sección de desglose del cálculo

### Requirement: Diagnóstico de impacto sobre correcciones existentes

El sistema SHALL proveer un script de diagnóstico de solo lectura que recorra las correcciones ya persistidas y reporte, sin modificarlas, cuáles tendrían una nota distinta bajo el nuevo cálculo, con la nota actual, la nota que resultaría y la diferencia. Las correcciones existentes NO SHALL recalcularse automáticamente.

#### Scenario: Reporte de impacto

- **WHEN** se ejecuta el script de diagnóstico sobre la base
- **THEN** se obtiene el listado de correcciones cuya nota cambiaría, con nota actual, nota nueva y diferencia, y ninguna fila de la base es modificada

#### Scenario: Correcciones previas intactas tras el despliegue

- **WHEN** se despliega el change y se consulta una corrección hecha antes
- **THEN** su nota es la misma que tenía, sin recálculo
