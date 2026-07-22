# upload-size-limits Specification

## Purpose
Acotar el tamaño de las subidas (individual y masiva) contra `MAX_UPLOAD_SIZE` y proteger el pipeline de descompresión contra ZIP-bombs —por tamaño descomprimido acumulado y por cantidad de entradas— rechazando con mensajes accionables antes de materializar contenido peligroso en memoria.
## Requirements
### Requirement: Límite de tamaño en subida individual

El sistema SHALL rechazar la subida individual de una entrega cuando el archivo supere `settings.MAX_UPLOAD_SIZE` (100 MB por defecto). El rechazo SHALL producirse con código HTTP `413 Request Entity Too Large` (o `400` si el framework no lo permite) y un mensaje que indique que se excedió el tamaño máximo permitido y cuál es ese tope. La validación SHALL ocurrir antes de consolidar el contenido, de modo que un archivo sobredimensionado no avance por el pipeline.

#### Scenario: Rechazo de archivo individual mayor al límite
- **WHEN** un usuario sube una entrega individual cuyo tamaño supera `MAX_UPLOAD_SIZE`
- **THEN** el sistema responde con `413` (o `400`) y no crea ni corrige la entrega

#### Scenario: Aceptación de archivo individual dentro del límite
- **WHEN** un usuario sube una entrega individual cuyo tamaño es menor o igual a `MAX_UPLOAD_SIZE`
- **THEN** el sistema procesa la entrega normalmente sin bloqueo por tamaño

### Requirement: Límite de tamaño en carga masiva

El sistema SHALL rechazar la carga masiva cuando el ZIP contenedor supere `settings.MAX_UPLOAD_SIZE`. El rechazo SHALL producirse con código HTTP `413` (o `400`) y un mensaje accionable que indique el tope superado. La validación SHALL ocurrir antes de iterar las carpetas de alumnos contenidas en el ZIP.

#### Scenario: Rechazo de ZIP contenedor mayor al límite
- **WHEN** un usuario sube un ZIP de carga masiva cuyo tamaño supera `MAX_UPLOAD_SIZE`
- **THEN** el sistema responde con `413` (o `400`) y no procesa ninguna carpeta de alumno

### Requirement: Protección anti ZIP-bomb por tamaño descomprimido acumulado

Al descomprimir un ZIP (tanto en la consolidación de código como en la iteración de carpetas de la carga masiva), el sistema SHALL acumular el tamaño **descomprimido** declarado por cada entrada (`ZipInfo.file_size`) y SHALL abortar de forma controlada cuando el acumulado supere un tope de expansión razonable. El aborto SHALL ocurrir ANTES de materializar en memoria el contenido completo del ZIP, de modo que un ZIP pequeño que se expande a varios GB nunca llegue a leerse por completo.

#### Scenario: Aborto por expansión descomprimida excesiva
- **WHEN** un ZIP cuyo tamaño descomprimido acumulado de sus entradas supera el tope de expansión se sube para consolidación o carga masiva
- **THEN** el sistema aborta con un error controlado (mensaje claro) y no lee el contenido completo en memoria

#### Scenario: ZIP legítimo con expansión moderada se procesa
- **WHEN** un ZIP cuya expansión descomprimida está dentro del tope se sube
- **THEN** el sistema lo descomprime y consolida normalmente

### Requirement: Protección anti ZIP-bomb por cantidad de entradas

El sistema SHALL limitar la cantidad total de entradas procesadas de un ZIP a un tope configurable. Cuando un ZIP declare más entradas que ese tope, el sistema SHALL abortar de forma controlada con un mensaje claro, sin recorrer ni leer todas las entradas.

#### Scenario: Aborto por exceso de entradas en el ZIP
- **WHEN** un ZIP declara más entradas que el tope permitido
- **THEN** el sistema aborta con un error controlado indicando que se excedió la cantidad máxima de archivos

#### Scenario: ZIP con cantidad de entradas dentro del tope se procesa
- **WHEN** un ZIP declara una cantidad de entradas menor o igual al tope
- **THEN** el sistema procesa sus entradas normalmente

### Requirement: Mensajes de error accionables y sin fuga de internals

Los mensajes de error de los rechazos por tamaño y por ZIP-bomb SHALL indicar de forma clara la causa (tamaño de archivo superado, expansión del ZIP excesiva, o demasiadas entradas) y el límite aplicado, sin exponer trazas internas ni rutas del servidor.

#### Scenario: El mensaje nombra la causa y el límite
- **WHEN** una subida es rechazada por superar un límite de tamaño o de expansión
- **THEN** el mensaje de error nombra la causa y el tope aplicado, sin incluir stack traces ni paths internos

