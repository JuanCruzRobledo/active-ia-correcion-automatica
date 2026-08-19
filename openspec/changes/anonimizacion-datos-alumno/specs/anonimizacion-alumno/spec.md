## ADDED Requirements

### Requirement: La anonimización destruye los datos personales y la producción del alumno

El sistema SHALL destruir de forma irreversible, para todas las entregas y correcciones asociadas a un pseudónimo de alumno: el código consolidado, la vista previa del contenido, el contenido del PDF entregado, la lista de archivos incluidos, el nombre del archivo, el hash de la entrega, el identificador de usuario de Moodle, el comentario general, las fortalezas, las recomendaciones, el feedback y la evidencia por criterio, la respuesta cruda del proveedor de IA, y el resultado de ejecución de tests.

#### Scenario: Anonimización de una entrega con corrección

- **WHEN** se anonimiza un alumno con una entrega corregida
- **THEN** el código, el PDF, la devolución textual, la evidencia por criterio y la respuesta cruda del proveedor quedan destruidos

#### Scenario: Anonimización de una entrega sin corregir

- **WHEN** se anonimiza un alumno con una entrega aún sin corregir
- **THEN** el código y los datos de archivo quedan destruidos y la operación no falla por ausencia de corrección

### Requirement: El registro académico despersonalizado se conserva

El sistema SHALL conservar, tras la anonimización: la existencia de la entrega, la rúbrica contra la que se corrigió, la comisión, las fechas, la nota, el puntaje por criterio y el estado. Ninguna fila SHALL eliminarse físicamente.

#### Scenario: Nota conservada

- **WHEN** se anonimiza un alumno que tenía una corrección con nota
- **THEN** la corrección sigue existiendo con su nota y su puntaje por criterio

#### Scenario: Ninguna fila eliminada

- **WHEN** se anonimiza un alumno con tres entregas
- **THEN** las tres filas de entrega siguen existiendo, ninguna se elimina físicamente

### Requirement: El pseudónimo se reemplaza por un identificador anónimo estable e irreversible

El sistema SHALL reemplazar el pseudónimo del alumno por un identificador anónimo que NO SHALL poder derivarse del pseudónimo original ni permitir reconstruirlo. Dentro de una misma operación de anonimización, todas las entregas alcanzadas SHALL recibir el **mismo** identificador anónimo.

#### Scenario: Varias entregas del mismo alumno

- **WHEN** se anonimiza un alumno que tenía cuatro entregas
- **THEN** las cuatro quedan con el mismo identificador anónimo, y ese identificador no permite recuperar el pseudónimo original

#### Scenario: Dos anonimizaciones distintas

- **WHEN** se anonimizan dos alumnos distintos
- **THEN** cada uno recibe un identificador anónimo distinto

#### Scenario: Irreversibilidad

- **WHEN** se conoce el pseudónimo original de un alumno anonimizado
- **THEN** no es posible recalcular su identificador anónimo para volver a encontrar sus filas

### Requirement: El historial queda alcanzado por la anonimización

El sistema SHALL aplicar la misma destrucción y el mismo identificador anónimo a los registros históricos de entregas y de correcciones asociados al pseudónimo, incluyendo el código, la vista previa, el PDF y las correcciones almacenadas en el historial.

#### Scenario: Entrega sobrescrita previamente

- **WHEN** se anonimiza un alumno cuya entrega había sido sobrescrita, dejando una copia en el historial
- **THEN** el código y la corrección guardados en el historial también quedan destruidos

#### Scenario: Corrección reemplazada por una recorrección

- **WHEN** se anonimiza un alumno cuya corrección había sido reemplazada al recorregir
- **THEN** la corrección anterior guardada en el historial también queda anonimizada

### Requirement: La anonimización es atómica

Todas las escrituras de una anonimización SHALL ejecutarse en una sola transacción. Si alguna falla, el sistema NO SHALL dejar ninguna parte aplicada.

#### Scenario: Fallo a mitad de la operación

- **WHEN** una anonimización falla después de haber anonimizado las entregas y antes de anonimizar el historial
- **THEN** ninguna de las dos partes queda aplicada y el estado es el anterior a la operación

### Requirement: Alcance acotado por coincidencia exacta y por universidad

La anonimización SHALL alcanzar únicamente las entregas cuya identificación de alumno coincida exactamente con el pseudónimo indicado, dentro de la universidad del solicitante. NO SHALL usarse coincidencia parcial, por prefijo ni insensible a mayúsculas.

#### Scenario: Coincidencia exacta

- **WHEN** se anonimiza un pseudónimo y existen entregas con ese valor exacto
- **THEN** solo esas entregas se anonimizan

#### Scenario: Coincidencia parcial

- **WHEN** existe una entrega cuya identificación de alumno contiene el pseudónimo como subcadena pero no es igual
- **THEN** esa entrega no se anonimiza

#### Scenario: Otra universidad

- **WHEN** existe una entrega con el mismo pseudónimo en otra universidad
- **THEN** esa entrega no se anonimiza

### Requirement: Auditoría sin registrar el pseudónimo original

El sistema SHALL registrar la anonimización en la auditoría con quién la solicitó, cuándo, la cantidad de entregas y correcciones alcanzadas y el identificador anónimo resultante. NO SHALL registrar el pseudónimo original. El sistema SHALL además anonimizar el pseudónimo en los registros de auditoría previos que lo contengan.

#### Scenario: Registro de la operación

- **WHEN** se completa una anonimización que alcanzó tres entregas
- **THEN** queda un registro con el solicitante, la fecha, los conteos y el identificador anónimo, y sin el pseudónimo original

#### Scenario: Registros de auditoría anteriores

- **WHEN** existen registros de auditoría previos que mencionan el pseudónimo
- **THEN** esas menciones quedan anonimizadas tras la operación

### Requirement: La anonimización es irreversible

El sistema NO SHALL ofrecer ninguna operación de reversión de una anonimización, ni conservar copia de los datos destruidos con el fin de restaurarlos.

#### Scenario: Intento de reversión

- **WHEN** se busca restaurar los datos de un alumno anonimizado
- **THEN** no existe ninguna operación del sistema que lo permita
