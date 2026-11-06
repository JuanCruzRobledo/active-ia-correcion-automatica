# Spec Delta

## ADDED Requirements

### Requirement: Edición de puntaje y comentario de subcriterios evaluados

El sistema SHALL permitir al tutor autorizado editar `puntaje_obtenido` y `feedback` de los subcriterios evaluados existentes de una entrega. SHALL conservar su identificador, máximo, estado y pertenencia al criterio. El modo consulta SHALL mostrar los valores sin controles editables; editar la corrección no SHALL modificar la definición de la rúbrica.

#### Scenario: Editar y guardar un subcriterio
- **WHEN** el tutor cambia C1.1 de 12/20 a 16/20, reemplaza su comentario y guarda
- **THEN** la corrección persiste 16/20 y el nuevo comentario de C1.1
- **AND** los demás subcriterios, identificadores, máximos y estados permanecen iguales

#### Scenario: Consulta y devolución actualizadas
- **WHEN** se vuelve a consultar una corrección editada o se genera su devolución PDF
- **THEN** se muestran el puntaje y comentario guardados para el subcriterio
- **AND** el modo consulta no permite modificarlos

#### Scenario: Cancelar la edición
- **WHEN** el tutor modifica subcriterios y cancela o cierra sin guardar
- **THEN** al volver a editar se muestran los valores persistidos originales
- **AND** no se envía una actualización por los cambios descartados

### Requirement: Validación de modificaciones del desglose

El sistema SHALL validar en cliente y servidor que los puntajes de subcriterios editados sean números finitos entre cero y su máximo almacenado, inclusive, y que sus comentarios no estén vacíos ni contengan solo espacios. SHALL rechazar cambios de identificadores, máximos, estados o composición del desglose en esta edición, sin persistir parcialmente la corrección.

#### Scenario: Puntaje en los límites
- **WHEN** se guarda un subcriterio de máximo 20 con puntaje 0 o 20 y comentario válido
- **THEN** la edición es aceptada

#### Scenario: Puntaje inválido
- **WHEN** se intenta guardar un subcriterio de máximo 20 con -1, 21 o un valor no finito
- **THEN** el cliente informa el error y bloquea guardar
- **AND** una solicitud directa equivalente es rechazada por el servidor sin persistir cambios

#### Scenario: Comentario vacío
- **WHEN** se intenta guardar un comentario vacío o compuesto solo por espacios
- **THEN** se informa qué subcriterio requiere comentario y no se guarda la edición

#### Scenario: Alterar la estructura desde la solicitud
- **WHEN** una solicitud altera el máximo, estado o identificador de un subcriterio existente, lo mueve de criterio o agrega o elimina subcriterios
- **THEN** el servidor rechaza la edición completa sin cambiar los valores persistidos

### Requirement: Coherencia de puntajes al editar el desglose

Cuando una edición modifica puntajes de subcriterios, el sistema SHALL derivar el puntaje de cada criterio afectado de su suma y mostrar ese puntaje sin edición independiente. El comentario y estado del criterio SHALL conservar su edición actual independiente. La nota académica SHALL mantener su ajuste manual y la acción explícita Recalcular nota; el tope de entrega SHALL aplicarse posteriormente en servidor.

#### Scenario: Actualizar el total del criterio
- **WHEN** C1 tiene subcriterios de 10 y 20 puntos y el tutor cambia el primero a 15
- **THEN** el total de C1 pasa a 35 en pantalla y al guardar
- **AND** el comentario y estado de C1 no cambian automáticamente

#### Scenario: Solicitud con total de criterio desactualizado
- **WHEN** una solicitud modifica un puntaje de subcriterio pero envía el total anterior del criterio
- **THEN** el servidor guarda para el criterio la suma de sus subcriterios

#### Scenario: Edición de comentario sin cambio de puntaje
- **WHEN** el tutor cambia solo el comentario de un subcriterio
- **THEN** se conserva el puntaje del criterio y la nota académica anteriores

#### Scenario: Nota recalculada con entrega restringida
- **WHEN** los criterios suman 82, el tutor usa Recalcular nota y guarda una entrega con máximo de 50
- **THEN** se conserva 82 como nota académica y 50 como nota final
- **AND** los puntajes de criterios y subcriterios no se reducen por ese tope

#### Scenario: Nota sin recálculo explícito
- **WHEN** el tutor modifica el puntaje de un subcriterio y guarda sin Recalcular nota ni cambiar manualmente la nota académica
- **THEN** cambia el puntaje del criterio afectado pero se conserva la nota académica anterior

### Requirement: Compatibilidad de la edición manual del desglose

El sistema SHALL conservar la edición actual de criterios sin desglose para correcciones históricas o v1 y para arreglos ausentes, nulos o vacíos. SHALL preservar el desglose almacenado cuando una actualización omita ese campo, sin inventar subcriterios. Las ediciones válidas SHALL seguir usando los permisos de la corrección y el marcado de edición manual existentes.

#### Scenario: Corrección sin desglose
- **WHEN** se edita un criterio con `subcriterios_evaluados` ausente, nulo o vacío
- **THEN** se permite editar su puntaje y comentario como antes sin mostrar un editor de subcriterios

#### Scenario: Cliente que omite el desglose
- **WHEN** una actualización modifica el comentario del criterio sin incluir su desglose almacenado
- **THEN** se conserva el desglose y no se inventan ni eliminan subcriterios

#### Scenario: Persistencia y marcado manual
- **WHEN** un tutor autorizado guarda una modificación válida de subcriterio
- **THEN** se registra la corrección como editada manualmente por ese usuario
- **AND** una lectura posterior devuelve el desglose completo actualizado

#### Scenario: Acceso ajeno a la entrega
- **WHEN** un usuario sin acceso a la comisión, materia o universidad de la corrección intenta editar sus subcriterios
- **THEN** la solicitud es denegada con el comportamiento de autorización vigente y la corrección no cambia
