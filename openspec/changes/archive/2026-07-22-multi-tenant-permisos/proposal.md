## Why

Hoy toda la autorización de Active-IA se apoya en `usuario.rol`, un rol **único y global** del usuario. Con el modelo multi-tenant ya introducido (Fase 0) un usuario puede ser ADMIN en una universidad y TUTOR en otra, y el JWT ya porta la universidad activa + el rol de esa membresía (Fase 1). Falta el eslabón crítico: que los guards de `app/core/permissions.py` dejen de leer `usuario.rol` y pasen a autorizar por el rol del usuario **en la universidad activa del request**, con bypass total para el superadmin global. Esta es la fase de **mayor riesgo** del feature (CRÍTICO — es el corazón de la autorización), por eso se aborda en su propio change, con tests de regresión que congelan el comportamiento actual **antes** de tocar nada.

Esta es la **Fase 2 de 6** del feature multi-tenant. Depende de Fase 0 (`multi-tenant-modelo-datos`, archivada: tablas `universidades`, `usuario_universidad`, `usuarios.es_superadmin`) y Fase 1 (`multi-tenant-auth-jwt`, archivada: JWT con `universidad_activa_id` + dependency `get_universidad_activa`, hoy implementado pero **no montado en ningún endpoint**).

## What Changes

- Refactor de `app/core/permissions.py` (**archivo entero**): los guards de rol (`require_admin`, `require_coordinador`, `require_tutor`, `require_gestor`, y las combinadas `require_coordinador_or_admin`, `require_tutor_or_coordinador`, `require_gestor_or_admin`) dejan de comparar contra `usuario.rol` y pasan a comparar contra el **rol resuelto para la universidad activa** (el que ya entrega `get_universidad_activa` de Fase 1). `require_any_authenticated` no cambia su semántica.
- Los guards de pertenencia (`verificar_acceso_materia`, `verificar_acceso_unidad`, `verificar_acceso_examen`, `verificar_acceso_materia_de_comision`, `verificar_acceso_rubrica`, `verificar_acceso_comision`, `verificar_acceso_comision_o_materia`, `verificar_acceso_entrega`, `verificar_acceso_correccion`, `filtrar_entregas_accesibles`, `comisiones_visibles_para`): el check `if usuario.rol == RolEnum.ADMIN` (acceso total) pasa a decidirse por el rol de la universidad activa **y** por el bypass de superadmin.
- **Bypass total de superadmin**: si `es_superadmin`, todo guard `require_*` y todo guard de pertenencia pasa sin más chequeo.
- Enganche de la universidad activa a los guards en los ~18 puntos de uso (routers/services), montando `get_universidad_activa` (Fase 1) como dependency donde haga falta.
- **Tests de caracterización/regresión primero**: como PRIMER paso del apply, tests que capturan el comportamiento actual de cada guard (quién pasa, quién recibe 403/404) para congelar la semántica antes del refactor.
- **BREAKING (interno, no de API)**: la firma de los guards `require_*` cambia (pasan a recibir el contexto de universidad activa en vez de `Usuario`); es un contrato interno entre `permissions.py` y sus consumidores — el comportamiento HTTP observable **no** cambia en el estado mono-universidad actual.

**Fuera de alcance** (otras fases, NO tocar acá): scoping/filtrado de queries por `universidad_id` en repositories (Fase 4 — no se agrega `WHERE universidad_id=...`); services de Moodle (Fase 3); frontend (Fase 5); eliminación de `usuarios.rol` (Fase 6). El login/select/switch de universidad ya se hizo en Fase 1 y no se re-hace.

## Capabilities

### New Capabilities
- `permisos-universidad-activa`: Los guards de rol (`require_*`) autorizan por el rol del usuario en la **universidad activa del request** (fuente: `get_universidad_activa` de Fase 1), no por `usuario.rol` global, con bypass total para `es_superadmin`. Incluye el invariante de seguridad (cero cambio de comportamiento observable en el estado mono-universidad actual) y la estrategia de enganche de la universidad activa a los guards.

### Modified Capabilities
- `autorizacion-por-pertenencia`: La matriz de acceso por pertenencia (guards `verificar_acceso_*`) mantiene su lógica de pertenencia a comisión/materia, pero la determinación del "acceso total" deja de leer `usuario.rol == ADMIN` y pasa a resolverse por el rol de la universidad activa; además se agrega el bypass de superadmin como acceso total. La pertenencia (ComisionTutor/CoordinadorMateria) sigue evaluándose igual.

## Impact

- **Core**: `app/core/permissions.py` (archivo entero, ~638 LOC — vigilar el límite de 500 LOC/archivo). Reusa `get_universidad_activa` y `ContextoUniversidad` de `app/core/dependencies.py` (Fase 1, sin modificarlos).
- **Routers (17)**: `actividades.py`, `cierre_cursada.py`, `comisiones.py`, `cohortes.py`, `dashboard.py`, `correcciones.py`, `entregas.py`, `dashboard_gestores.py`, `documentos.py`, `materias.py`, `notificaciones.py`, `examenes.py`, `gestion.py`, `rubricas.py`, `tutores_nexo.py`, `unidades.py`, `usuarios.py`.
- **Services (1)**: `app/services/moodle_grade_service.py` (usa `verificar_acceso_comision`).
- **Tests**: nuevos tests de caracterización + adaptación de los tests existentes (`tests/unit/core/test_permissions_*.py`).
- **Sin cambios de contrato HTTP** para el estado mono-universidad actual (todos los usuarios en TUPaD con 1 membresía cuyo rol == su viejo rol global). No toca DB, ni migraciones, ni frontend.
