# Capability: Autorización por Pertenencia

## Purpose

Autorizar el acceso a recursos de corrección (entregas, correcciones, documentos) en función de la pertenencia real del usuario a la comisión del recurso, verificada contra la base de datos, usando el rol de la universidad activa del request.

## Requirements

### Requirement: Matriz de acceso por pertenencia a la comisión

El sistema SHALL autorizar el acceso a un recurso de corrección (entrega, corrección, documento) en función de la pertenencia real del usuario a la comisión del recurso, verificada contra la base de datos en cada request. La sola posesión de un token válido NO SHALL ser suficiente.

El eje de "acceso total" SHALL determinarse por el rol del usuario **en la universidad activa del request** (releído de `usuario_universidad`, según `get_universidad_activa` de Fase 1) o por el flag `es_superadmin`, y NO por el campo global `usuarios.rol`. La pertenencia (ComisionTutor/CoordinadorMateria) SHALL evaluarse igual que hoy.

La matriz de acceso SHALL ser la unión de estos ejes:

| Condición | Acceso |
|-----------|--------|
| `es_superadmin = true` | acceso total, sin consulta de pertenencia |
| rol `ADMIN` en la universidad activa | acceso total, sin consulta de pertenencia |
| rol `TUTOR` en la universidad activa | existe `ComisionTutor(comision_id, tutor_id = usuario.id)` |
| rol `COORDINADOR` en la universidad activa | existe `CoordinadorMateria(materia_id, coordinador_id = usuario.id)` donde `materia_id = Comision.materia_id` |
| rol `GESTOR` en la universidad activa | denegado |
| cualquier otro | denegado |

El acceso denegado SHALL producir `HTTP 403`. Una comisión inexistente SHALL producir `HTTP 404`.

Con los datos actuales (usuario con una única membresía activa cuyo rol es igual a su viejo `usuarios.rol`, sin superadmins salvo los designados), esta matriz SHALL producir exactamente el mismo resultado observable que la matriz previa basada en `usuarios.rol`.

#### Scenario: Superadmin accede a cualquier comisión
- **WHEN** un usuario con `es_superadmin = true` solicita un recurso de una comisión a la que no está asignado
- **THEN** el sistema permite el acceso sin consultar `ComisionTutor` ni `CoordinadorMateria`

#### Scenario: Admin de la universidad activa accede a cualquier comisión
- **WHEN** un usuario con rol `ADMIN` en la universidad activa solicita un recurso de una comisión a la que no está asignado
- **THEN** el sistema permite el acceso sin consultar `ComisionTutor` ni `CoordinadorMateria`

#### Scenario: Rol ADMIN global pero no en la universidad activa
- **WHEN** un usuario con `usuarios.rol = ADMIN` (viejo) cuya membresía activa en la universidad del request es `TUTOR` solicita un recurso de una comisión a la que no está asignado
- **THEN** el sistema responde `403` (no se aplica el acceso total: el rol de la universidad activa es `TUTOR`)

#### Scenario: Tutor asignado a la comisión accede
- **WHEN** un usuario con rol `TUTOR` en la universidad activa que tiene una fila en `ComisionTutor` para esa comisión solicita el recurso
- **THEN** el sistema permite el acceso

#### Scenario: Tutor NO asignado a la comisión es rechazado
- **WHEN** un usuario con rol `TUTOR` en la universidad activa sin fila en `ComisionTutor` para esa comisión solicita el recurso
- **THEN** el sistema responde `403` y no devuelve ningún dato del recurso

#### Scenario: Coordinador de la materia de la comisión accede
- **WHEN** un usuario con rol `COORDINADOR` en la universidad activa asignado en `CoordinadorMateria` a la materia de esa comisión solicita el recurso
- **THEN** el sistema permite el acceso, aunque no exista fila en `ComisionTutor` para ese usuario

#### Scenario: Coordinador de otra materia es rechazado
- **WHEN** un usuario con rol `COORDINADOR` en la universidad activa asignado a una materia distinta de la de la comisión solicita el recurso
- **THEN** el sistema responde `403`

#### Scenario: Gestor es rechazado
- **WHEN** un usuario con rol `GESTOR` en la universidad activa solicita cualquier recurso de corrección
- **THEN** el sistema responde `403`, dado que el rol `GESTOR` solo opera sobre reportes de Moodle

#### Scenario: Comisión inexistente
- **WHEN** un usuario sin acceso total solicita un recurso cuya comisión no existe
- **THEN** el sistema responde `404` y no `403`, para no filtrar la existencia por diferencia de código
