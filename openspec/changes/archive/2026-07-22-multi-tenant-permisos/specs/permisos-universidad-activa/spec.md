## ADDED Requirements

### Requirement: Los guards de rol autorizan por el rol de la universidad activa

El sistema SHALL resolver el rol para todo guard de rol (`require_admin`, `require_coordinador`, `require_tutor`, `require_gestor`, `require_coordinador_or_admin`, `require_tutor_or_coordinador`, `require_gestor_or_admin`) a partir del rol del usuario **en la universidad activa del request** — el rol releído de `usuario_universidad` que entrega el contexto de universidad activa (`get_universidad_activa`, Fase 1) — y NO a partir del campo global `usuarios.rol`. El claim `rol` del token NO SHALL usarse como fuente de autorización (es informativo); la fuente de verdad es el rol de la membresía releído de la base.

La semántica de negación SHALL preservarse: cuando el rol de la universidad activa no alcanza para el guard, el sistema SHALL responder `HTTP 403` con el mismo mensaje de detalle que hoy.

#### Scenario: Guard de admin acepta al admin de la universidad activa

- **WHEN** un usuario cuya membresía activa en la universidad del request tiene rol `ADMIN` pasa por `require_admin`
- **THEN** el guard permite el acceso

#### Scenario: Guard de admin rechaza a un rol insuficiente en la universidad activa

- **WHEN** un usuario cuya membresía activa en la universidad del request tiene rol `TUTOR` pasa por `require_admin`
- **THEN** el guard responde `403` con el detalle "Se requiere rol de administrador"

#### Scenario: El rol se toma de la membresía activa, no del rol global

- **WHEN** un usuario tiene `usuarios.rol = ADMIN` (viejo, global) pero su membresía activa en la universidad del request es `COORDINADOR`, y pasa por `require_admin`
- **THEN** el guard responde `403` (el rol global `ADMIN` es ignorado; manda el rol de la membresía activa)

#### Scenario: Guard combinado acepta cualquiera de los roles admitidos en la universidad activa

- **WHEN** un usuario con rol `COORDINADOR` en la universidad activa pasa por `require_coordinador_or_admin`
- **THEN** el guard permite el acceso

### Requirement: Bypass total de superadmin en todos los guards

El sistema SHALL permitir que un usuario con `es_superadmin = true` pase **cualquier** guard de rol (`require_*`) y **cualquier** guard de pertenencia (`verificar_acceso_*`, `filtrar_entregas_accesibles`, `comisiones_visibles_para`) sin evaluar el rol ni la pertenencia. El superadmin SHALL tener acceso total equivalente al que hoy tiene el rol `ADMIN`, con independencia de su rol de membresía (o de la ausencia de membresía) en la universidad activa.

#### Scenario: Superadmin pasa un guard de rol sin membresía admin

- **WHEN** un usuario con `es_superadmin = true` cuya membresía en la universidad activa NO es `ADMIN` (o no tiene membresía) pasa por `require_admin`
- **THEN** el guard permite el acceso por el bypass de superadmin

#### Scenario: Superadmin pasa un guard de pertenencia sin estar asignado

- **WHEN** un usuario con `es_superadmin = true` solicita un recurso de una comisión a la que no está asignado
- **THEN** el guard de pertenencia permite el acceso sin consultar `ComisionTutor` ni `CoordinadorMateria`

### Requirement: Enganche de la universidad activa a los guards en los puntos de uso

El sistema SHALL proveer a cada guard el contexto de la universidad activa del request reutilizando el dependency `get_universidad_activa` de Fase 1 (que valida membresía activa salvo superadmin y relee el rol de la base), sin modificar `get_current_user` ni `get_current_user_optional`. Los guards de rol SHALL pasar a recibir el contexto de universidad activa (`ContextoUniversidad`) en lugar del `Usuario`; los guards de pertenencia SHALL determinar el "acceso total" a partir de ese contexto (rol de la universidad activa o `es_superadmin`) en lugar de `usuario.rol`. El acceso a datos que requieran los guards de pertenencia SHALL seguir haciéndose vía repositorio/consulta parametrizada (nunca SQL crudo), respetando Clean Architecture.

#### Scenario: Un endpoint con guard de rol monta el contexto de universidad activa

- **WHEN** se inspecciona un endpoint que hoy invoca un guard `require_*`
- **THEN** el endpoint obtiene el contexto de universidad activa mediante `get_universidad_activa` y se lo provee al guard, en lugar de pasarle `usuario.rol`

#### Scenario: get_current_user no se modifica

- **WHEN** se comparan `get_current_user` y `get_current_user_optional` antes y después del cambio
- **THEN** su firma y comportamiento permanecen idénticos (el enganche se hace vía `get_universidad_activa`, que los reutiliza)

### Requirement: Invariante de seguridad — cero cambio de comportamiento en el estado mono-universidad

El sistema SHALL garantizar que, con los datos actuales (todos los usuarios en una única universidad TUPaD, cada uno con exactamente una membresía activa cuyo rol es igual a su viejo `usuarios.rol`, y sin superadmins salvo los designados manualmente), el comportamiento de autorización observable (qué usuario pasa cada guard y qué usuario recibe `403`/`404`) SHALL ser **idéntico** al comportamiento previo a este change. La única diferencia interna admitida SHALL ser la FUENTE del rol (membresía de la universidad activa en vez de `usuarios.rol`) y el nuevo bypass de superadmin.

Este invariante SHALL estar cubierto por tests de caracterización escritos **antes** del refactor, que congelan el comportamiento actual de cada guard.

#### Scenario: Un ADMIN mono-universidad sigue siendo ADMIN

- **WHEN** un usuario que hoy es `ADMIN` global, con una única membresía activa `ADMIN` en TUPaD, ejerce cualquier endpoint tras el refactor
- **THEN** obtiene exactamente el mismo resultado (acceso concedido o denegado) que obtenía antes del refactor

#### Scenario: Un TUTOR mono-universidad sigue siendo TUTOR

- **WHEN** un usuario que hoy es `TUTOR` global, con una única membresía activa `TUTOR` en TUPaD, ejerce cualquier endpoint tras el refactor
- **THEN** obtiene exactamente el mismo resultado (acceso concedido o denegado) que obtenía antes del refactor

#### Scenario: La suite de caracterización se escribe antes del refactor

- **WHEN** se inspecciona el historial de tareas del apply
- **THEN** los tests que capturan el comportamiento actual de cada guard existen y pasan ANTES de que se modifique la lógica de los guards

### Requirement: Superadmin sin universidad activa frente a los guards

El sistema SHALL definir que un superadmin operando **sin** `universidad_activa_id` (modo superadmin puro, admitido por Fase 1) pasa todos los guards de rol y todos los guards de pertenencia por el bypass de superadmin, dado que el bypass no depende del contexto de una universidad concreta. Los guards de pertenencia que hoy resuelven un recurso concreto (materia/comisión/entrega/corrección) SHALL seguir localizando el recurso para distinguir `404` de acceso concedido, pero NO SHALL denegar por falta de universidad activa cuando el usuario es superadmin.

#### Scenario: Superadmin sin universidad activa accede a un recurso existente

- **WHEN** un superadmin con `universidad_activa_id = null` solicita un recurso de pertenencia (p. ej. una entrega existente)
- **THEN** el guard concede el acceso por el bypass de superadmin, sin exigir universidad activa

#### Scenario: Superadmin sin universidad activa sobre un recurso inexistente

- **WHEN** un superadmin con `universidad_activa_id = null` solicita un recurso cuyo ID no existe
- **THEN** el sistema responde `404` (el bypass concede acceso, pero el recurso sigue sin existir)
