## ADDED Requirements

### Requirement: Matriz de acceso por pertenencia a la comisión

El sistema SHALL autorizar el acceso a un recurso de corrección (entrega, corrección, documento) en función de la pertenencia real del usuario a la comisión del recurso, verificada contra la base de datos en cada request. La sola posesión de un token válido NO SHALL ser suficiente.

La matriz de acceso SHALL ser la unión de dos ejes independientes:

| Rol | Condición de acceso |
|-----|---------------------|
| `ADMIN` | acceso total, sin consulta de pertenencia |
| `TUTOR` | existe `ComisionTutor(comision_id, tutor_id = usuario.id)` |
| `COORDINADOR` | existe `CoordinadorMateria(materia_id, coordinador_id = usuario.id)` donde `materia_id = Comision.materia_id` |
| `GESTOR` | denegado |
| cualquier otro | denegado |

El acceso denegado SHALL producir `HTTP 403`. Una comisión inexistente SHALL producir `HTTP 404`.

#### Scenario: Admin accede a cualquier comisión
- **WHEN** un usuario con rol `ADMIN` solicita un recurso de una comisión a la que no está asignado
- **THEN** el sistema permite el acceso sin consultar `ComisionTutor` ni `CoordinadorMateria`

#### Scenario: Tutor asignado a la comisión accede
- **WHEN** un usuario con rol `TUTOR` que tiene una fila en `ComisionTutor` para esa comisión solicita el recurso
- **THEN** el sistema permite el acceso

#### Scenario: Tutor NO asignado a la comisión es rechazado
- **WHEN** un usuario con rol `TUTOR` sin fila en `ComisionTutor` para esa comisión solicita el recurso
- **THEN** el sistema responde `403` y no devuelve ningún dato del recurso

#### Scenario: Coordinador de la materia de la comisión accede
- **WHEN** un usuario con rol `COORDINADOR` asignado en `CoordinadorMateria` a la materia de esa comisión solicita el recurso
- **THEN** el sistema permite el acceso, aunque no exista fila en `ComisionTutor` para ese usuario

#### Scenario: Coordinador de otra materia es rechazado
- **WHEN** un usuario con rol `COORDINADOR` asignado a una materia distinta de la de la comisión solicita el recurso
- **THEN** el sistema responde `403`

#### Scenario: Gestor es rechazado
- **WHEN** un usuario con rol `GESTOR` solicita cualquier recurso de corrección
- **THEN** el sistema responde `403`, dado que el rol `GESTOR` solo opera sobre reportes de Moodle

#### Scenario: Comisión inexistente
- **WHEN** un usuario no-admin solicita un recurso cuya comisión no existe
- **THEN** el sistema responde `404` y no `403`, para no filtrar la existencia por diferencia de código

### Requirement: Resolución de la cadena entrega y corrección

El sistema SHALL resolver la comisión de un recurso siguiendo la cadena de claves foráneas `Correccion.entrega_id → Entrega.id`, `Entrega.comision_id → Comision.id`, `Comision.materia_id → Materia.id`, y aplicar sobre la comisión resultante la matriz de acceso por pertenencia.

La resolución SHALL seleccionar únicamente las columnas necesarias para la autorización. En particular NO SHALL cargar la entidad `Entrega` completa, porque sus columnas `contenido_consolidado` y `pdf_contenido_b64` están declaradas `deferred=True` y cargarlas arrastraría el contenido íntegro de la entrega en cada verificación de permisos.

`Entrega.subido_por_id` NO SHALL usarse como eje de autorización, dado que es nullable.

#### Scenario: Autorización de una entrega
- **WHEN** se verifica el acceso a una entrega por su ID
- **THEN** el sistema resuelve `Entrega.comision_id` y aplica la matriz de acceso sobre esa comisión

#### Scenario: Autorización de una corrección
- **WHEN** se verifica el acceso a una corrección por su ID
- **THEN** el sistema resuelve `Correccion.entrega_id → Entrega.comision_id` y aplica la matriz de acceso sobre esa comisión

#### Scenario: El guard no carga columnas diferidas
- **WHEN** el sistema resuelve la comisión de una entrega para autorizar
- **THEN** la consulta selecciona solo las columnas de clave (`id`, `comision_id`) y no incluye `contenido_consolidado` ni `pdf_contenido_b64`

#### Scenario: Entrega o corrección inexistente
- **WHEN** se verifica el acceso a una entrega o corrección cuyo ID no existe
- **THEN** el sistema responde `404`

#### Scenario: Entrega sin usuario que la subió
- **WHEN** se verifica el acceso a una entrega cuyo `subido_por_id` es `NULL`
- **THEN** la autorización se resuelve igualmente por la comisión de la entrega, sin depender de `subido_por_id`

### Requirement: Protección de los endpoints de entregas, correcciones y documentos

El sistema SHALL aplicar la verificación de pertenencia en los 20 endpoints que hoy solo invocan `require_any_authenticated`, antes de ejecutar cualquier lógica de negocio o devolver datos.

Endpoints alcanzados:

- **Entregas**: `GET /entregas/`, `POST /entregas/`, `POST /entregas/masiva`, `PATCH /entregas/archivar`, `DELETE /entregas/masivo`, `GET /entregas/{entrega_id}`, `GET /entregas/{entrega_id}/contenido`, `DELETE /entregas/{entrega_id}`
- **Correcciones**: `POST /correcciones/entregas/{entrega_id}/corregir`, `POST /correcciones/entregas/{entrega_id}/recorregir`, `POST /correcciones/lote`, `GET /correcciones/{correccion_id}`, `GET /correcciones/entregas/{entrega_id}`, `PUT /correcciones/{correccion_id}`
- **Documentos**: `GET /documentos/correcciones/{correccion_id}/pdf`, `GET /documentos/comisiones/{comision_id}/rubricas/{rubrica_id}/pdfs`, `POST /documentos/pdfs-seleccionados`, `GET /documentos/comisiones/{comision_id}/rubricas/{rubrica_id}/excel`

Los endpoints de Moodle (`GET /correcciones/{correccion_id}/moodle/preview` y `POST /correcciones/{correccion_id}/moodle`) NO SHALL modificarse: ya validan pertenencia a través de `MoodleGradeService`.

#### Scenario: Lectura del contenido de una entrega ajena
- **WHEN** un tutor solicita `GET /entregas/{id}/contenido` de una entrega de una comisión que no le pertenece
- **THEN** el sistema responde `403` y no expone el código fuente del alumno

#### Scenario: Edición de la nota de una corrección ajena
- **WHEN** un tutor envía `PUT /correcciones/{id}` con una `nota` nueva sobre una corrección de otra comisión
- **THEN** el sistema responde `403` y la nota permanece sin cambios

#### Scenario: Creación de una entrega en una comisión ajena
- **WHEN** un tutor envía `POST /entregas/` con un `comision_id` al que no está asignado
- **THEN** el sistema responde `403` y no crea la entrega

#### Scenario: Descarga de documentos de una comisión ajena
- **WHEN** un tutor solicita el ZIP de PDFs o el Excel de notas de una comisión que no le pertenece
- **THEN** el sistema responde `403` y no genera el documento

#### Scenario: Los endpoints de Moodle conservan su validación
- **WHEN** se ejecuta la suite de tests tras el cambio
- **THEN** los endpoints de Moodle siguen validando pertenencia mediante `MoodleGradeService`, sin guard duplicado

### Requirement: Scoping del listado de entregas

`GET /entregas/` NO SHALL responder `403` por ausencia de filtros. En su lugar SHALL restringir el conjunto de resultados a las entregas de las comisiones visibles para el usuario, aplicando el filtro como parte de la consulta SQL mediante un `JOIN`, de modo que la paginación y el conteo total reflejen únicamente lo visible.

Un usuario `ADMIN` SHALL ver todas las entregas.

#### Scenario: Tutor lista sin filtros
- **WHEN** un tutor solicita `GET /entregas/` sin `comision_id`
- **THEN** el sistema devuelve solo las entregas de las comisiones en las que ese tutor está asignado, y el total paginado refleja ese subconjunto

#### Scenario: Coordinador lista sin filtros
- **WHEN** un coordinador solicita `GET /entregas/` sin `comision_id`
- **THEN** el sistema devuelve solo las entregas de las comisiones pertenecientes a las materias que coordina

#### Scenario: Admin lista sin filtros
- **WHEN** un `ADMIN` solicita `GET /entregas/` sin filtros
- **THEN** el sistema devuelve las entregas de todas las comisiones

#### Scenario: Filtro explícito por una comisión ajena
- **WHEN** un tutor solicita `GET /entregas/?comision_id=<comisión ajena>`
- **THEN** el sistema responde `403`, en lugar de devolver una lista vacía

#### Scenario: El total paginado no filtra información
- **WHEN** un tutor pagina el listado
- **THEN** el campo de total cuenta únicamente las entregas visibles para él, sin revelar la cantidad total del sistema

### Requirement: Operaciones de lote con acceso parcial

Los endpoints que reciben una lista de IDs SHALL particionar la lista en IDs permitidos e IDs denegados, operar únicamente sobre los permitidos, y SHALL informar explícitamente en la respuesta cuáles fueron omitidos. NO SHALL fallar la operación completa por un único ID sin acceso, ni omitir IDs en silencio.

Endpoints alcanzados: `PATCH /entregas/archivar`, `DELETE /entregas/masivo`, `POST /correcciones/lote`, `POST /documentos/pdfs-seleccionados`.

La partición SHALL resolverse con **una sola consulta** por request, sin emitir una consulta por ID.

Para `DELETE /entregas/masivo` el reporte de omitidos SHALL ser prominente en la respuesta y en la interfaz, dado que la eliminación es irreversible y el usuario debe poder distinguir qué no se borró.

Si **ningún** ID del lote es accesible, el sistema SHALL responder `403` en lugar de una operación vacía exitosa.

#### Scenario: Lote mixto se filtra e informa
- **WHEN** un tutor envía `PATCH /entregas/archivar` con 10 IDs, de los cuales 6 son de sus comisiones y 4 no
- **THEN** el sistema archiva las 6 entregas accesibles, no toca las otras 4, y la respuesta incluye la cantidad procesada y la lista de los 4 IDs omitidos

#### Scenario: Borrado masivo informa lo omitido de forma prominente
- **WHEN** un tutor envía `DELETE /entregas/masivo` con IDs de los cuales algunos no le pertenecen
- **THEN** el sistema borra solo los accesibles y la respuesta identifica claramente los IDs omitidos para que la interfaz los muestre de forma destacada

#### Scenario: Corrección en lote filtra antes de encolar
- **WHEN** un tutor envía `POST /correcciones/lote` con IDs mixtos
- **THEN** el sistema encola en background solo las entregas accesibles, y `total_encoladas` junto con la lista de omitidos reflejan esa partición

#### Scenario: Descarga selectiva de PDFs filtra el ZIP
- **WHEN** un tutor envía `POST /documentos/pdfs-seleccionados` con IDs mixtos
- **THEN** el ZIP generado contiene solo los PDFs de las entregas accesibles y el sistema comunica cuáles se omitieron

#### Scenario: Lote sin ningún ID accesible
- **WHEN** un tutor envía un lote donde ningún ID pertenece a sus comisiones
- **THEN** el sistema responde `403` y no ejecuta ninguna operación

#### Scenario: La validación del lote no genera N+1
- **WHEN** se valida un lote de 100 IDs
- **THEN** el sistema emite una única consulta de pertenencia para todo el lote, no 100 consultas

### Requirement: Los guards de pertenencia consultan la base de datos

El sistema NO SHALL exponer funciones de autorización cuyo nombre implique verificación de pertenencia pero que solo comprueben el rol del usuario. Toda función que afirme validar pertenencia a una materia o comisión SHALL consultar la relación correspondiente en la base de datos.

#### Scenario: Se eliminan los guards placeholder
- **WHEN** se inspecciona `app/core/permissions.py` después del cambio
- **THEN** `require_coordinador_of_materia` y `require_tutor_of_comision` ya no existen, por ser placeholders que nunca consultaron la base de datos

#### Scenario: La eliminación no rompe nada
- **WHEN** se buscan referencias a los guards eliminados en todo el código de la aplicación
- **THEN** no queda ninguna referencia y la suite de tests pasa completa

#### Scenario: Todo guard de pertenencia recibe una sesión de base de datos
- **WHEN** se inspecciona la firma de cualquier función de `permissions.py` cuyo nombre refiera a pertenencia a comisión o materia
- **THEN** la función es asíncrona y recibe una `AsyncSession` como parámetro
