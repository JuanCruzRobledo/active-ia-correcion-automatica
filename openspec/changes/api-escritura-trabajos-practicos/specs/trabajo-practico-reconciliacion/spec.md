## ADDED Requirements

### Requirement: Los ejercicios se emparejan por identificador externo

Al actualizar un trabajo práctico existente, el sistema SHALL emparejar los ejercicios del cuerpo con los ejercicios vigentes del trabajo práctico **por su identificador externo**. El sistema NO SHALL emparejar por orden ni por título.

#### Scenario: Ejercicios reordenados entre pushes

- **WHEN** se republica un trabajo práctico con los mismos ejercicios pero en distinto orden
- **THEN** cada ejercicio se actualiza en su lugar por su identificador externo, y ninguno se duplica ni se recrea

#### Scenario: Ejercicio renombrado

- **WHEN** se republica un ejercicio con el mismo identificador externo y un título distinto
- **THEN** el ejercicio existente se actualiza con el título nuevo, sin crear uno nuevo

### Requirement: Un ejercicio conserva su rúbrica de por vida

El identificador de la rúbrica de un ejercicio SHALL permanecer estable durante toda la vida de ese ejercicio. Al actualizar un ejercicio, el sistema SHALL actualizar el contenido de su rúbrica existente y NO SHALL reemplazarla por una rúbrica nueva.

#### Scenario: Actualización de los criterios de un ejercicio

- **WHEN** se republica un ejercicio con criterios de rúbrica distintos
- **THEN** la rúbrica existente se actualiza y su identificador es el mismo que antes del push

#### Scenario: Entregas previas conservan su vínculo

- **WHEN** un ejercicio ya tiene entregas y correcciones, y se republica con la rúbrica modificada
- **THEN** las entregas y correcciones siguen apuntando a la misma rúbrica, sin quedar huérfanas

### Requirement: Alta de ejercicios nuevos en un push

Cuando el cuerpo incluya un ejercicio cuyo identificador externo no exista en el trabajo práctico, el sistema SHALL crearlo junto con su rúbrica, dentro de la misma operación.

#### Scenario: Un ejercicio nuevo se agrega al trabajo práctico

- **WHEN** se republica un trabajo práctico de tres ejercicios agregando un cuarto con identificador externo nuevo
- **THEN** el cuarto ejercicio y su rúbrica se crean, y los tres existentes conservan sus identificadores de rúbrica

### Requirement: Baja lógica de los ejercicios ausentes en el push

Cuando un ejercicio vigente del trabajo práctico no aparezca en el cuerpo del upsert, el sistema SHALL darlo de baja lógica junto con su rúbrica. El ejercicio dado de baja NO SHALL aparecer en las respuestas del trabajo práctico y NO SHALL aceptar correcciones nuevas. Las entregas y correcciones que ya existían SHALL conservarse y seguir siendo consultables.

#### Scenario: Un ejercicio deja de venir en el push

- **WHEN** se republica un trabajo práctico de cuatro ejercicios enviando solo tres
- **THEN** el cuarto ejercicio y su rúbrica quedan dados de baja lógica y ya no figuran en la respuesta

#### Scenario: Correcciones previas de un ejercicio dado de baja

- **WHEN** se da de baja un ejercicio que tenía correcciones
- **THEN** esas correcciones siguen existiendo y siendo consultables, y ninguna fila se elimina físicamente

#### Scenario: Restauración por republicación

- **WHEN** se vuelve a enviar en un push posterior el identificador externo de un ejercicio dado de baja
- **THEN** el sistema deja el trabajo práctico con ese ejercicio vigente nuevamente

### Requirement: La reconciliación es parte de la misma transacción

Las altas, actualizaciones y bajas lógicas derivadas de un upsert SHALL ejecutarse dentro de la misma transacción que el resto de la operación. Un fallo en cualquiera de ellas SHALL dejar el trabajo práctico exactamente como estaba antes del push.

#### Scenario: Fallo durante la reconciliación

- **WHEN** un upsert falla al validar un ejercicio nuevo después de haber actualizado dos existentes
- **THEN** ninguna de las tres operaciones se persiste y el trabajo práctico queda como estaba
