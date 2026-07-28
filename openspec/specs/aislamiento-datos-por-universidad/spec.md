# aislamiento-datos-por-universidad Specification

## Purpose
TBD - created by archiving change multi-tenant-scoping-queries. Update Purpose after archive.
## Requirements
### Requirement: Listados filtrados por universidad activa

Todo método de repositorio que lista, busca o cuenta cualquiera de las 9 entidades scopeadas (`materias`, `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots`) SHALL aplicar el filtro `WHERE universidad_id = :universidad_activa` cuando la universidad activa está definida. El filtro SHALL vivir en el repository (nunca en el service — ARCH-001) y SHALL formar parte de las mismas condiciones que alimentan tanto la consulta de datos como la de conteo, de modo que el total paginado no revele la cantidad global cross-universidad.

#### Scenario: Un miembro solo ve datos de su universidad activa

- **WHEN** un usuario con universidad activa UniA solicita el listado de cualquiera de las 9 entidades
- **THEN** la respuesta contiene únicamente registros cuyo `universidad_id` es el de UniA
- **AND** el total paginado cuenta únicamente esos registros

#### Scenario: Aislamiento entre dos universidades

- **WHEN** existen datos en UniA y en UniB, y un usuario con universidad activa UniA lista una entidad
- **THEN** ningún registro de UniB aparece en la respuesta ni en el conteo

#### Scenario: El filtro de universidad se suma al de soft delete

- **WHEN** se lista una entidad con soft delete (p. ej. entregas o materias)
- **THEN** el resultado excluye simultáneamente los registros de otra universidad Y los marcados como borrados/inactivos, sin que el filtro de universidad reemplace el de soft delete

### Requirement: Acceso por id valida pertenencia a la universidad activa

Cuando se accede a un recurso de una entidad scopeada por su id, el sistema SHALL validar que `recurso.universidad_id` coincide con la universidad activa. Si el recurso pertenece a otra universidad, el sistema SHALL responder **404 Not Found**, indistinguible de un recurso inexistente. El sistema NO SHALL responder 403 en este caso, para no revelar que el recurso existe en otra universidad.

#### Scenario: Recurso de otra universidad devuelve 404

- **WHEN** un usuario con universidad activa UniA solicita por id un recurso que pertenece a UniB
- **THEN** el sistema responde 404 Not Found
- **AND** el cuerpo de la respuesta no distingue este caso de un id inexistente

#### Scenario: Recurso de la propia universidad se accede normalmente

- **WHEN** un usuario con universidad activa UniA solicita por id un recurso de UniA al que tiene permiso
- **THEN** el sistema devuelve el recurso normalmente

#### Scenario: El guard 409 de sync Moodle no se altera

- **WHEN** un flujo de sincronización Moodle intenta operar sobre una materia de otra universidad
- **THEN** conserva su semántica previa de 409 Conflict (no se convierte en 404), porque es un caso distinto del acceso general por id

### Requirement: Bypass del superadmin sin universidad activa

Cuando la universidad activa no está definida (`ctx.universidad_id is None`, superadmin que no eligió universidad), el sistema NO SHALL aplicar ningún filtro por universidad: los listados devuelven registros de todas las universidades y el acceso por id no valida pertenencia. Cuando el superadmin SÍ eligió una universidad (`ctx.universidad_id` definido), el sistema SHALL comportarse como para cualquier miembro de esa universidad (filtra a esa universidad).

#### Scenario: Superadmin sin universidad activa ve todas las universidades

- **WHEN** un superadmin sin universidad activa lista una entidad que tiene datos en UniA y UniB
- **THEN** la respuesta incluye registros de ambas universidades

#### Scenario: Superadmin sin universidad activa accede a cualquier recurso por id

- **WHEN** un superadmin sin universidad activa solicita por id un recurso de cualquier universidad
- **THEN** el sistema devuelve el recurso sin validar pertenencia

#### Scenario: Superadmin con universidad elegida queda scopeado a esa universidad

- **WHEN** un superadmin selecciona UniA como universidad activa y lista una entidad
- **THEN** la respuesta contiene únicamente registros de UniA

### Requirement: Propagación de la universidad activa desde el router hasta el repository

La universidad activa SHALL propagarse como un valor entero nullable (`universidad_id: int | None`) desde el router (que ya dispone de `ctx: ContextoUniversidad`) hacia el service y de ahí al repository. Los repositories NO SHALL depender de `ContextoUniversidad`; reciben únicamente el `universidad_id`. El valor `None` SHALL significar siempre "sin filtro / ver todo" (bypass), nunca un error ni una universidad concreta.

#### Scenario: El router pasa la universidad activa al service

- **WHEN** un endpoint de una entidad scopeada recibe un request autenticado
- **THEN** el router obtiene `ctx.universidad_id` desde `get_universidad_activa` y lo pasa al método del service

#### Scenario: El repository desconoce ContextoUniversidad

- **WHEN** un método de repositorio aplica el scoping por universidad
- **THEN** recibe un parámetro `universidad_id: int | None` y no importa ni referencia `ContextoUniversidad`

### Requirement: Métricas de dashboard scopeadas por universidad

Las agregaciones y métricas de dashboard (conteos de comisiones, rúbricas, pendientes, corregidas, progreso por comisión y detalle) SHALL calcularse scopeadas a la universidad activa. La única excepción SHALL ser el superadmin sin universidad activa, para quien las agregaciones abarcan todas las universidades.

#### Scenario: Dashboard de un miembro solo agrega su universidad

- **WHEN** un usuario con universidad activa UniA abre el dashboard
- **THEN** todas las métricas cuentan únicamente datos de UniA

#### Scenario: Dashboard del superadmin sin universidad agrega todo

- **WHEN** un superadmin sin universidad activa abre el dashboard
- **THEN** las métricas agregan datos de todas las universidades

### Requirement: Endpoints de comisiones autorizan por contexto de universidad

Los endpoints `listar_comisiones`, `obtener_comision` y `actualizar_moodle_comision` de `comisiones.py` SHALL resolver el rol desde el `ContextoUniversidad` (`ctx`) de la universidad activa y NO desde `current_user.rol` global, y SHALL aplicar el scoping por universidad activa. Esto cierra la deuda arrastrada de Fase 2.

#### Scenario: listar_comisiones scopea por universidad y usa el rol del contexto

- **WHEN** un tutor de UniA lista comisiones
- **THEN** el rol de filtrado (tutor/coordinador) se resuelve desde `ctx` y el resultado contiene solo comisiones de UniA a las que tiene acceso

#### Scenario: obtener_comision de otra universidad devuelve 404

- **WHEN** un usuario de UniA solicita por id una comisión de UniB
- **THEN** el sistema responde 404 Not Found

#### Scenario: actualizar_moodle_comision valida rol vía contexto

- **WHEN** un usuario intenta actualizar la config Moodle de una comisión
- **THEN** la autorización se decide con `ctx` (acceso total o pertenencia), no con `current_user.rol` global, y la comisión debe pertenecer a la universidad activa

### Requirement: Invariante mono-tenant preservado

Con los datos actuales (todos migrados a una sola universidad, TUPaD), el comportamiento observable del sistema NO SHALL cambiar respecto del estado previo a esta fase: todos los usuarios siguen viendo exactamente lo que veían. El aislamiento SHALL volverse observable únicamente cuando exista una segunda universidad con datos.

#### Scenario: Comportamiento idéntico con una sola universidad

- **WHEN** existe una única universidad con todos los datos y un usuario opera normalmente
- **THEN** los listados, accesos por id y dashboards devuelven los mismos resultados que antes de esta fase

#### Scenario: Suite de aislamiento con dos universidades como gate

- **WHEN** se ejecutan los tests de aislamiento que crean una segunda universidad con datos
- **THEN** un usuario de UniA no ve ningún dato de UniB (listados vacíos de UniB, 404 al acceder por id a recursos de UniB) y un superadmin sin universidad activa ve ambas

