## Context

Active-IA está migrando a multi-tenant (universidades). Fases previas ya archivadas:

- **Fase 0** (`multi-tenant-modelo-datos`): tablas `universidades`, `usuario_universidad` (membresía con `rol` scopeado + `activo`), columna `usuarios.es_superadmin`. `usuarios.rol` TODAVÍA existe (convivencia hasta Fase 6).
- **Fase 1** (`multi-tenant-auth-jwt`): el JWT porta `universidad_activa_id` + `rol` (de la membresía activa) + `es_superadmin`. Existe el dependency `get_universidad_activa` en `app/core/dependencies.py` que resuelve la universidad activa del token, valida membresía activa (salvo superadmin) y **relee el rol de la base** (`ContextoUniversidad{universidad_id, rol, es_superadmin}`). Hoy está implementado y testeado pero **NO montado en ningún endpoint**.

Hoy `app/core/permissions.py` (~638 LOC) autoriza leyendo `usuario.rol` (el rol global). Esta Fase 2 hace que la autorización pase a basarse en el rol del usuario **en la universidad activa del request**, con **bypass total para `es_superadmin`**. Es la fase de mayor riesgo del feature: es el corazón de la autorización. El patrón del proyecto exige tests de regresión de permisos **antes** de tocar nada.

**Estado de datos actual (mono-universidad):** todos los usuarios están en una única universidad (TUPaD), cada uno con exactamente una membresía activa cuyo `rol` es igual a su viejo `usuarios.rol`. No hay superadmins salvo los designados a mano. En este estado, el comportamiento de permisos observable NO debe cambiar.

### Inventario de guards en `permissions.py`

**Grupo A — guards de rol** (sync, hoy reciben `Usuario`, comparan `user.rol`):
`require_admin`, `require_coordinador`, `require_tutor`, `require_gestor`, `require_coordinador_or_admin`, `require_tutor_or_coordinador`, `require_gestor_or_admin`, `require_any_authenticated` (este último NO compara rol: solo devuelve el user).

**Grupo B — guards de pertenencia** (async, reciben `db, usuario, <id>`, consultan la DB; el acceso total hoy es `if usuario.rol == RolEnum.ADMIN`):
`verificar_acceso_materia`, `verificar_acceso_unidad`, `verificar_acceso_examen`, `verificar_acceso_materia_de_comision`, `verificar_acceso_rubrica`, `verificar_acceso_comision`, `verificar_acceso_comision_o_materia`, `verificar_acceso_entrega`, `verificar_acceso_correccion`, `filtrar_entregas_accesibles`, `comisiones_visibles_para`.

### Los puntos de uso (consumidores de los guards)

Grep de `require_admin|require_coordinador|require_tutor|require_gestor|verificar_acceso|filtrar_entregas_accesibles|comisiones_visibles_para` → **18 archivos consumidores** (17 routers + 1 service). El plan citaba "17 puntos": ese conteo se refería a los archivos que leen `RolEnum` directamente; el conteo real de consumidores de los guards es 18 (incluye `moodle_grade_service.py`, que no importa `RolEnum` pero sí un guard). Los 18:

| # | Archivo | Líneas | Guards usados | Grupo |
|---|---------|--------|---------------|-------|
| 1 | `routers/actividades.py` | 47 | `require_admin` | A |
| 2 | `routers/cierre_cursada.py` | 54, 76, 98 | `verificar_acceso_materia` | B |
| 3 | `routers/comisiones.py` | 108, 199, 219, 238, 266 | `require_admin`, `verificar_acceso_materia`, `verificar_acceso_materia_de_comision` | A+B |
| 4 | `routers/cohortes.py` | 39, 51, 63, 76, 88, 108, 121, 135 | `require_admin`, `require_coordinador_or_admin` | A |
| 5 | `routers/dashboard.py` | 39, 59, 79 | `require_admin`, `require_coordinador`, `require_tutor` | A |
| 6 | `routers/correcciones.py` | 112, 159, 208, 267, 295, 319, 359, 453, 496 | `verificar_acceso_entrega`, `verificar_acceso_correccion`, `filtrar_entregas_accesibles`, `require_any_authenticated` | A+B |
| 7 | `routers/entregas.py` | 82, 85, 138, 221, 263, 296, 330, 358, 381, 400 | `verificar_acceso_comision_o_materia`, `comisiones_visibles_para`, `filtrar_entregas_accesibles`, `verificar_acceso_entrega` | B |
| 8 | `routers/dashboard_gestores.py` | 52, 63, 82, 111, 132, 213, 225, 238, 250 | `require_admin`, `require_gestor_or_admin` | A |
| 9 | `routers/documentos.py` | 66, 113, 153, 197 | `verificar_acceso_correccion`, `verificar_acceso_comision_o_materia`, `filtrar_entregas_accesibles` | B |
| 10 | `routers/materias.py` | 50, 82, 99, 100, 120, 121, 143, 160, 180 | `require_admin`, `require_coordinador_or_admin`, `verificar_acceso_materia` | A+B |
| 11 | `routers/notificaciones.py` | 95, 105, 136, 175, 206, 220 | `require_admin` | A |
| 12 | `routers/examenes.py` | 36, 37, 53, 54, 66, 67, 78, 79 | `require_coordinador_or_admin`, `verificar_acceso_materia`, `verificar_acceso_examen` | A+B |
| 13 | `routers/gestion.py` | 59, 71, 84, 99, 120 | `require_gestor_or_admin` | A |
| 14 | `routers/rubricas.py` | 64, 110, 136, 166, 190, 212, 246, 276, 318, 361, 400, 471 | `require_any_authenticated`, `require_coordinador_or_admin`, `require_admin` | A |
| 15 | `routers/tutores_nexo.py` | 28, 39, 50, 62, 73 | `require_admin` | A |
| 16 | `routers/unidades.py` | 52-211 (12 sitios) | `require_coordinador_or_admin`, `verificar_acceso_materia`, `verificar_acceso_unidad`, `verificar_acceso_rubrica` | A+B |
| 17 | `routers/usuarios.py` | 55, 83, 100, 119, 137, 161, 180 | `require_admin` | A |
| 18 | `services/moodle_grade_service.py` | 95, 235 | `verificar_acceso_comision` | B |

## Goals / Non-Goals

**Goals:**
- Que todo guard de rol y todo guard de pertenencia autorice por el rol del usuario **en la universidad activa del request** (fuente: `get_universidad_activa` de Fase 1), no por `usuarios.rol`.
- Bypass total de `es_superadmin` en todos los guards.
- **Cero cambio de comportamiento observable** en el estado mono-universidad actual (invariante de seguridad), respaldado por tests de caracterización escritos **antes** del refactor.
- Enganche mínimo y consistente de la universidad activa a los guards en los 18 consumidores.

**Non-Goals:**
- Scoping/filtrado de queries por `universidad_id` en repositories (Fase 4). No se agregan cláusulas `WHERE universidad_id = ...`.
- Refactor de los services de Moodle que leen `moodle_host/username/password` (Fase 3). `moodle_grade_service.py` se toca SOLO en su llamada a `verificar_acceso_comision`.
- Frontend (Fase 5).
- Eliminar `usuarios.rol` (Fase 6): sigue existiendo; simplemente los guards dejan de leerlo.
- Login/select/switch de universidad: ya resuelto en Fase 1.

## Decisions

### D1 — Los guards de rol (Grupo A) reciben `ContextoUniversidad`, no `Usuario`

`require_admin(user)` → `require_admin(ctx: ContextoUniversidad)`. La lógica pasa a:

```
def require_admin(ctx):
    if ctx.es_superadmin:            # bypass total
        return ctx
    if ctx.rol != RolEnum.ADMIN:     # rol de la universidad activa (releído de la base)
        raise HTTPException(403, "Se requiere rol de administrador")
    return ctx
```

Análogo para `require_coordinador`, `require_tutor`, `require_gestor`, y las combinadas (`require_*_or_*` comparan `ctx.rol not in (...)`). El mensaje de detalle de cada 403 se mantiene idéntico.

**Alternativa considerada:** mantener la firma `(user)` y hacer que el guard llame internamente a `get_universidad_activa`. Rechazada: un guard no es un dependency de FastAPI, no puede resolver `Depends`; forzarlo a abrir su propia sesión y decodificar el token rompería Clean Architecture y duplicaría Fase 1.

### D2 — `require_any_authenticated` NO cambia

Solo afirma "cualquier usuario autenticado"; no lee rol. Se mantiene recibiendo `Usuario`. Consecuencia deliberada: montar la universidad activa en un endpoint que HOY solo usa `require_any_authenticated` sería un cambio de comportamiento (pasaría a exigir universidad activa). Ver Open Question OQ2.

### D3 — Los guards de pertenencia (Grupo B) ganan un parámetro de contexto; conservan `usuario` para las joins

Las queries de pertenencia usan `usuario.id` (`ComisionTutor.tutor_id == usuario.id`, `CoordinadorMateria.coordinador_id == usuario.id`), y `ContextoUniversidad` no lleva el id del usuario. Por eso los guards de pertenencia SÍ necesitan ambos: `usuario` (para el id) y el contexto (para el acceso total). Firma nueva:

```
async def verificar_acceso_materia(db, usuario, ctx, materia_id):
    if _acceso_total(ctx):           # ctx.es_superadmin or ctx.rol == RolEnum.ADMIN
        return
    # ... resto idéntico (CoordinadorMateria por usuario.id) ...
```

Se introduce un helper privado `_acceso_total(ctx) -> bool` (superadmin OR rol ADMIN en la universidad activa) reutilizado por los 11 guards de pertenencia, para no repetir la condición. El resto del cuerpo de cada guard (las joins de pertenencia, los 404/403) queda **byte-por-byte igual**.

**Alternativa considerada:** meter `usuario_id` dentro de `ContextoUniversidad` (Fase 1) y pasar solo `ctx`. Rechazada: modificaría la estructura entregada por Fase 1 y su spec; el costo de pasar `usuario` como parámetro extra es trivial y localizado.

### D4 — Enganche en los consumidores: montar `get_universidad_activa` como dependency

Cada endpoint que use un guard obtiene el contexto con una línea de dependency:

```
ctx: ContextoUniversidad = Depends(get_universidad_activa)
```

- **Grupo A:** se reemplaza `require_admin(current_user)` por `require_admin(ctx)`. Si el endpoint ya no usa `current_user` para nada más, se puede quitar; si lo usa (p. ej. para `created_by`), se conservan ambos dependencies (get_universidad_activa ya depende internamente de get_current_user, sin doble costo de red).
- **Grupo B:** se agrega `ctx` a la llamada: `await verificar_acceso_materia(db, current_user, ctx, materia_id)`.

Este es el enganche **mínimo**: una línea de dependency por endpoint + ajustar el argumento del guard. No se crea un decorador ni un router-level dependency global (se evaluó y se descarta por OQ2: aplicarlo global forzaría universidad activa en endpoints que hoy no la piden).

### D5 — `_acceso_total` centraliza la equivalencia "ADMIN o superadmin"

Único punto donde vive la regla "quién tiene acceso total". Hace el invariante auditable: con datos mono-universidad, `ctx.rol == ADMIN` ⇔ el viejo `usuario.rol == ADMIN`, y `es_superadmin` es un eje nuevo aditivo (nadie lo tiene salvo los designados). Por eso el comportamiento observable no cambia.

### D6 — Plan de tests de caracterización (PRIMERO, antes de tocar guards)

Antes de modificar `permissions.py`, se escribe/extiende una suite que **congela el comportamiento actual** de cada guard, tomando como base los tests existentes (`tests/unit/core/test_permissions_gestor.py`, `test_permissions_invariante.py`, `test_permissions_materia.py`, `test_permissions_pertenencia.py`):

1. **Grupo A:** para cada guard de rol, un test parametrizado por los 4 roles (ADMIN/COORDINADOR/TUTOR/GESTOR) que fija quién pasa y quién recibe 403 con qué detalle. Estado de referencia: rol leído hoy de `usuario.rol`.
2. **Grupo B:** para cada guard de pertenencia, congelar: ADMIN pasa sin consulta; no-admin con pertenencia pasa; no-admin sin pertenencia → 403; recurso inexistente → 404; y el caso de lote (permitidos/denegados) para `filtrar_entregas_accesibles` y `comisiones_visibles_para`.
3. **Equivalencia mono-universidad:** helper de test que crea un usuario con 1 membresía activa cuyo rol == su rol global, y verifica que tras el refactor cada guard da el MISMO resultado que la versión vieja.
4. **Ejes nuevos (post-refactor, se agregan en verde):** superadmin pasa todo; usuario ADMIN-global pero TUTOR-en-la-universidad-activa recibe 403 donde el ADMIN pasaría (prueba de que la fuente cambió).

La suite de caracterización (1-3) debe existir y pasar contra el código VIEJO antes de refactorizar; luego el refactor debe mantenerla verde (salvo los ajustes de firma, que son mecánicos: los tests llaman a los guards con `ctx` en vez de `user`).

## Risks / Trade-offs

- **[Regresión silenciosa de autorización — es auth]** → Tests de caracterización escritos ANTES del refactor + `_acceso_total` como único punto de decisión + invariante mono-universidad explícito como criterio de aceptación. Checkpoint humano obligatorio antes del apply (gobernanza CRÍTICA).
- **[Firma de 11 guards de pertenencia + 7 de rol cambia → 18 consumidores a tocar]** → Cambio mecánico y localizado; el compilador/tests detectan cualquier sitio sin actualizar (los guards de rol pasan de aceptar `Usuario` a `ContextoUniversidad`, tipos distintos). Ir archivo por archivo con la tabla de la sección Context como checklist.
- **[Montar `get_universidad_activa` puede romper endpoints que hoy no exigen universidad activa]** → `get_universidad_activa` responde 409 a tokens sin `universidad_activa_id` con 0 o 2+ membresías. En mono-universidad todos tienen exactamente 1 → auto-resuelve, sin 409. Riesgo real solo cuando exista una 2ª universidad (fase posterior). Ver OQ2.
- **[`permissions.py` ya está en ~638 LOC, sobre el límite de 500]** → El refactor no debería agregar LOC neto significativo (cambia firmas, agrega un helper corto). Si se pasa, extraer los guards de pertenencia a un submódulo (`permissions/pertenencia.py`) es una opción, pero se evalúa recién si el archivo crece; no es objetivo de esta fase.
- **[`require_tutor_or_coordinador` está definido pero sin consumidores]** → Se refactoriza igual por consistencia; su test de caracterización lo cubre aunque ningún router lo use hoy.

## Migration Plan

No hay migración de datos (esta fase no toca DB). Despliegue:

1. Merge del change → los guards leen el rol de la universidad activa. Con tokens ya emitidos (Fase 1 los emite con `universidad_activa_id`; tokens viejos pre-Fase-1 auto-resuelven la única membresía).
2. **Rollback:** revertir el PR restaura los guards basados en `usuarios.rol`. Como `usuarios.rol` sigue existiendo (no se toca hasta Fase 6) y coincide con la membresía en mono-universidad, el rollback es seguro y sin pérdida de datos.

## Open Questions — RESUELTAS (checkpoint humano, gobernanza CRÍTICA)

### OQ1 — Superadmin con `universidad_activa_id = null` frente a los guards de pertenencia — RESUELTA

**Decisión:** SÍ. El bypass de `es_superadmin` **alcanza también** los checks de pertenencia (`verificar_acceso_*`). El superadmin accede a cualquier recurso de cualquier universidad. Los guards igual localizan el recurso para distinguir 404 (recurso inexistente sigue dando 404), pero NO deniegan por falta de universidad activa. `_acceso_total(ctx)` devuelve `true` por `es_superadmin` sin mirar `universidad_id`. Capturado en el spec `permisos-universidad-activa` ("Superadmin sin universidad activa frente a los guards").

### OQ2 — Endpoints que hoy solo usan `require_any_authenticated` — RESUELTA

**Decisión:** NO montar `get_universidad_activa` en los endpoints cuyo único guard es `require_any_authenticated` (varios GET de `rubricas.py`, perfil, y cualquiera que hoy solo pida estar logueado). Siguen EXACTAMENTE igual que hoy. `get_universidad_activa` (el `ctx`) se monta SOLO en endpoints que ya tienen un guard de rol (`require_*`) o de pertenencia (`verificar_acceso_*`). Razón: montarlo en todos crea un deadlock de entrada (usuario con 2+ universidades necesita leer perfil/lista-universidades ANTES de seleccionar, pero `get_universidad_activa` devuelve 409 sin selección). Donde `require_any_authenticated` convive con un guard de pertenencia (p. ej. `correcciones.py`), el `ctx` ya es necesario para el guard de pertenencia y se monta de todos modos.

### OQ3 — ¿El CHECK de que el recurso pertenece a la universidad activa va en Fase 2 o Fase 4? — RESUELTA

**Decisión:** NO se implementa en Fase 2. Va en **Fase 4** (scoping de queries). NO se agrega ninguna comparación de `universidad_id` del recurso contra la universidad activa en este change. Fase 2 se limita a "de dónde sale el rol + bypass superadmin"; el aislamiento por `universidad_id` del recurso queda anotado como dependencia explícita de Fase 4: cuando exista una 2ª universidad, un usuario con rol en la universidad A no debe alcanzar recursos de la universidad B aunque tenga el rol — eso lo garantiza el scoping de Fase 4, no estos guards.
