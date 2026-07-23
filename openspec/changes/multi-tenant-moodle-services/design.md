## Context

Active-IA está a mitad de un feature multi-tenant de 6 fases. Fases 0/1/2 están archivadas:

- **Fase 0** (`multi-tenant-modelo-datos`): existen las tablas `universidades` (con `moodle_host`, hoy NULL para TUPaD) y `usuario_universidad` (con `moodle_username`, `moodle_password_encrypted`, `rol`, `activo`), backfilleadas desde los campos viejos del usuario. Los campos viejos `usuarios.moodle_host`/`moodle_username`/`moodle_password_encrypted` **todavía existen** (convivencia hasta Fase 6).
- **Fase 1** (`multi-tenant-auth-jwt`): el JWT lleva `universidad_activa_id`; el dependency `get_universidad_activa` devuelve un `ContextoUniversidad(universidad_id, rol, es_superadmin)`. El repo `UsuarioRepository.get_membresia(usuario_id, universidad_id)` ya devuelve la `UsuarioUniversidad` de esa membresía con `.universidad` **precargada** (selectinload) → expone `membresia.moodle_username`, `membresia.moodle_password_encrypted` y `membresia.universidad.moodle_host` en una sola consulta.
- **Fase 2** (`multi-tenant-permisos`): `permissions.py` refactorizado; casi todos los routers montan `ctx: ContextoUniversidad = Depends(get_universidad_activa)`. En `moodle_grade_service` los métodos `subir_correccion`/`preview_correccion` **ya reciben `ctx`**.

**Estado actual de la fuente de datos Moodle** (confirmado por grep sobre `app/services/`): ~10 services leen `usuario.moodle_host`/`moodle_username`/`moodle_password_encrypted` (el usuario global) para construir un token Moodle. Este design cambia SOLO esa fuente.

**Servicios que leen datos Moodle (grep confirmado):**

| Service | Entrypoint(s) | Cómo recibe la identidad HOY | Qué lee | Categoría |
|---|---|---|---|---|
| `moodle_service.py` | `get_pendientes(user_id)` | `user_id` → `usuario_repo.get_by_id` | host+user+pass | token |
| `moodle_grade_service.py` | `subir_correccion(*, usuario, ctx, ...)`, `preview_correccion(*, usuario, ctx, ...)` | **`usuario` + `ctx`** (ya) | host+user+pass | token |
| `moodle_import_service.py` | `importar(user_id, scope)`, `importar_stream(user_id, scope)` | `user_id` → repo | host+user+pass | token |
| `cierre_cursada_service.py` | `token_de_usuario(usuario)` | objeto `usuario` | host+user+pass | token |
| `snapshot_service.py` | `token_de_usuario(usuario)`, `generar_todas_para_usuario(...)` | objeto `usuario` | host+user+pass | token |
| `unidad_service.py` | `_token_moodle(usuario)` | objeto `usuario` | host+user+pass | token |
| `gestion_service.py` | `_token(usuario)`, `listar_cursos(usuario)`, `opciones_filtros(usuario, materia_id)` | objeto `usuario` | host+user+pass | token |
| `por_entregar_service.py` | `listar(usuario)` | objeto `usuario` | host+user+pass | token |
| `usuario_service.py` | `update_moodle_credentials(user_id, data)` | `user_id` (write) | **escribe** host+user+pass | perfil/write |
| `notificacion_config_service.py` | validación de usuario de servicio (cron) | `data.usuario_id` → repo | user+pass (gate booleano) | config/cron |
| `snapshot_config_service.py` | validación de usuario de servicio (cron) | `data.usuario_id` → repo | user+pass (gate booleano) | config/cron |

Routers que hoy leen `current_user.moodle_*` como pre-check o display: `perfil.py` (display: host/user/configured), `pendientes.py`, `moodle_import.py`, `cierre_cursada.py`, `por_entregar.py`, `dashboard_gestores.py`.

**Constraints del proyecto**: Clean Architecture (ARCH-001: services no ejecutan SQLAlchemy; los datos llegan por repository). Cifrado Fernet/AES idéntico. Máx 500 LOC/archivo. Errores de proveedor externo (Moodle) → 502/424 según el caso. Gobernanza CRÍTICA/ALTA (credenciales Moodle cifradas) → proponer y esperar aprobación humana antes de codear.

## Goals / Non-Goals

**Goals:**
- Cambiar la **fuente** de host+credenciales Moodle en los services: universidad activa (`Universidad.moodle_host`) + membresía `(usuario, universidad activa)` (`UsuarioUniversidad.moodle_*`), no el usuario global.
- Un **único punto** de resolución de credenciales (resolver en repo) que todos los services consuman, para no repetir la lógica de "de dónde salen los bytes" en 10 lugares.
- Enganche mínimo y consistente del `universidad_id` activo a los services, respetando Clean Architecture.
- Rediseño del perfil: host read-only (propiedad de la Universidad), credenciales por membresía activa.
- Resolver el riesgo OP-1 (host de TUPaD en NULL) de forma explícita y segura.
- **Invariante**: cero cambio de comportamiento observable en el estado mono-universidad (TUPaD única con host seteado; cada usuario con 1 membresía cuyas credenciales == las viejas globales).

**Non-Goals:**
- Scoping/filtrado de queries por `universidad_id` (Fase 4). No se agrega `WHERE universidad_id=...` a ninguna query de negocio.
- Frontend (Fase 5).
- Borrar los campos viejos `usuarios.moodle_*`/`rol` (Fase 6). Acá **conviven**.
- Re-hacer permisos (Fase 2). El `ctx` ya existe y se reusa.
- Cambiar el cifrado o el formato de las credenciales.
- Cambiar el API Key de Gemini/OpenRouter (sigue global del usuario — decisión 6 del plan).

## Decisions

### D1 — OP-1 (host de TUPaD en NULL): gate duro + fail-fast, SIN fallback al host viejo (opción b reforzada)

**Decisión**: El host de TUPaD (`Universidad.moodle_host`) debe estar seteado **antes** de deployar Fase 3 (prerrequisito operativo bloqueante, Task 0). Además, el resolver de credenciales **falla-rápido** con `HTTP 424` y un mensaje accionable ("El campus Moodle de tu universidad no está configurado; contactá al administrador") cuando el host de la universidad activa es NULL/vacío. **No** se cae al viejo `usuario.moodle_host`.

**Alternativas consideradas:**
- **(a) Fallback temporal a `usuario.moodle_host`**: rechazada. En producción los usuarios tenían **3 valores distintos** de `usuario.moodle_host`, así que el fallback reintroduciría exactamente la inconsistencia que multi-tenant elimina (distintos tutores pegándole a distintos campus para la MISMA universidad). En un flujo de credenciales sensibles, un fallback silencioso es peor que una falla ruidosa, y además enmascararía que OP-1 nunca se resolvió.
- **(b) Gate duro + fail-fast**: elegida. Como hoy hay UNA sola universidad y el arreglo es un único `UPDATE`, el costo del gate es trivial y convierte un potencial "todo Moodle roto en runtime (500s)" en una falla temprana, ruidosa y con causa clara. El fail-fast del resolver protege también a futuras universidades creadas sin host.
- **(c) Verificación en el arranque de la app**: complementaria, opcional. Un check de startup que aborte si alguna universidad `activa` con membresías tiene `moodle_host` NULL sería más fuerte aún, pero acopla el arranque al estado de datos de todas las universidades; se deja como mejora opcional (no bloqueante de esta fase), y el gate operativo (Task 0) + el fail-fast por request cubren el riesgo real.

**Justificación**: es el camino más seguro para un dominio de credenciales cifradas; no perpetúa la lectura del campo viejo (objetivo central de la fase); y el fail-fast da un error de negocio claro en vez de un 500 opaco o, peor, un token contra el campus equivocado.

### D2 — Resolver único de credenciales en la capa Repository (ARCH-001)

**Decisión**: agregar a `UsuarioRepository` un método `get_credenciales_moodle(usuario_id, universidad_id) -> CredencialesMoodle | None` que devuelve un pequeño DTO/namedtuple `(moodle_host, moodle_username, moodle_password_encrypted)` leído de la nueva fuente (membresía + su universidad). Internamente puede reusar `get_membresia` (que ya precarga `.universidad`) o hacer un `select` acotado que traiga solo esas 3 columnas. Los services consumen el resolver y **nunca** navegan `usuario.moodle_*` ni ejecutan SQLAlchemy.

**Alternativas**: (i) que cada service arme la terna leyendo `ctx` + navegando relaciones → viola ARCH-001 y duplica lógica en 10 lugares. (ii) Un `MoodleCredentialsService` en la capa service que llame al repo → capa extra innecesaria; el resolver es puramente acceso a datos, va en el repo. La forma DTO evita devolver la entidad ORM entera (menos acoplamiento, controla qué se expone).

**Fail-fast (D1)** vive en el borde service↔resolver: si el resolver devuelve `None` (sin membresía o membresía sin credenciales) → 424 "configurá tus credenciales"; si devuelve terna con host vacío → 424 "campus no configurado". Se preserva el 424 que hoy ya devuelven los services cuando faltan credenciales.

### D3 — Enganche del `universidad_id` activo a los services: parámetro `universidad_id: int`

**Decisión**: cada método de service que hoy lee `usuario.moodle_*` pasa a recibir un parámetro `universidad_id: int` (el `ctx.universidad_id` del request). El router, que ya tiene `ctx` (Fase 2), pasa `ctx.universidad_id` al service. **Excepción**: en `moodle_grade_service` los métodos ya reciben `ctx` (Fase 2) → ahí se usa `ctx.universidad_id` directamente, sin agregar parámetro nuevo.

**Por qué `universidad_id: int` y no el `ctx` entero**: los services de token solo necesitan el id para resolver credenciales; `ContextoUniversidad` es un concepto de auth/autorización (rol, superadmin) que no le incumbe a la construcción del token. Pasar el id mantiene el contrato mínimo y explícito. Donde el `ctx` ya está threadeado (moodle_grade), se reusa para no cambiar firmas.

**Firmas que cambian (service por service):**

| Service | Firma vieja | Firma nueva |
|---|---|---|
| `moodle_service` | `get_pendientes(user_id)` | `get_pendientes(user_id, universidad_id)` |
| `moodle_grade_service` | `subir_correccion(*, ..., usuario, ctx, ...)` | **igual** (usa `ctx.universidad_id`) |
| `moodle_grade_service` | `preview_correccion(*, ..., usuario, ctx, ...)` | **igual** (usa `ctx.universidad_id`) |
| `moodle_import_service` | `importar(user_id, scope, ...)` | `importar(user_id, scope, ..., universidad_id)` |
| `moodle_import_service` | `importar_stream(user_id, scope, ...)` | `importar_stream(user_id, scope, ..., universidad_id)` |
| `cierre_cursada_service` | `token_de_usuario(usuario)` | `token_de_usuario(usuario, universidad_id)` |
| `snapshot_service` | `token_de_usuario(usuario)` | `token_de_usuario(usuario, universidad_id)` |
| `snapshot_service` | `generar_todas_para_usuario(...)` | `generar_todas_para_usuario(..., universidad_id)` |
| `unidad_service` | `_token_moodle(usuario)` | `_token_moodle(usuario, universidad_id)` |
| `gestion_service` | `_token(usuario)` | `_token(usuario, universidad_id)` |
| `gestion_service` | `listar_cursos(usuario)` | `listar_cursos(usuario, universidad_id)` |
| `gestion_service` | `opciones_filtros(usuario, materia_id)` | `opciones_filtros(usuario, materia_id, universidad_id)` |
| `por_entregar_service` | `listar(usuario)` | `listar(usuario, universidad_id)` |

Además, los helpers internos que hoy reciben `moodle_host: str` (p. ej. `moodle_import_service._importar_par`, `por_entregar_service._prefetch_grades`, `moodle_service.get_token`) **no cambian**: siguen recibiendo el host ya resuelto como string. Solo cambia quién lo produce (el resolver, no `usuario.moodle_host`).

### D4 — Rediseño del perfil: host read-only (Universidad), credenciales por membresía activa

**Decisión:**
- **`moodle_host`**: deja de editarse en el perfil. En `GET /perfil` se muestra **read-only**, tomado del `Universidad.moodle_host` de la universidad activa (`ctx.universidad_id`). El endpoint de escritura de credenciales **deja de aceptar** `moodle_host`.
- **`moodle_username`/`moodle_password`**: se escriben en la **membresía activa** `UsuarioUniversidad` de `ctx.universidad_id`, no en `usuario`. Nuevo método de repo `update_moodle_credentials_membresia(usuario_id, universidad_id, username, password_encrypted)`. El cifrado (encrypt de la password) no cambia.
- **`moodle_configured`** en `GET /perfil`: se computa desde las credenciales de la membresía activa, no desde `usuario.moodle_*`.
- El router `perfil.py` monta `ctx: ContextoUniversidad = Depends(get_universidad_activa)` en los endpoints de credenciales/perfil que lo necesiten, para saber a qué membresía leer/escribir.
- `schemas/perfil.py`: `MoodleCredentialsUpdate` pierde el campo `moodle_host`; `PerfilResponse.moodle_host` pasa a documentarse como read-only (host de la universidad activa).

**Fuera de alcance del rediseño**: `PerfilResponse.rol` (hoy `current_user.rol`, el global) **no** se toca acá — es territorio de Fase 2/6; esta fase solo cambia los campos `moodle_*`.

**Alternativa considerada**: sacar `moodle_host` del `PerfilResponse` por completo. Rechazada por ahora: el frontend (Fase 5) probablemente lo muestre; mantenerlo read-only evita romper el contrato de respuesta antes de tiempo. Se deja como Open Question menor.

### D5 — Config/cron gate services quedan con TODO explícito, no se rompen

**Decisión**: `notificacion_config_service` y `snapshot_config_service` validan que un **usuario de servicio** (cron) tenga credenciales Moodle. Hoy leen `usuario.moodle_*` como gate booleano. Como los crons corren **sin request/ctx**, no hay universidad activa de un JWT. En esta fase se mantiene el gate leyendo la fuente disponible con la mínima intervención, y se marca explícitamente como Open Question (OQ2) la fuente de `universidad_id` para jobs de fondo. No se cambia el modelo de cron en Fase 3 (evitar invadir alcance); si hace falta una decisión de producto, se resuelve en el checkpoint.

## Risks / Trade-offs

- **[Blast radius grande: ~10 services, muchos flujos Moodle]** → Apply **service por service** con TDD; cada service se migra y se testea aislado antes del siguiente. Tests de caracterización que congelan el comportamiento mono-universidad ANTES de tocar la fuente.
- **[Host de TUPaD en NULL rompe TODO Moodle si se deploya sin OP-1]** → Gate duro (Task 0, prerrequisito bloqueante) + fail-fast 424 en el resolver (D1). Sin fallback al host viejo.
- **[Fallback silencioso al campo viejo dejaría la fase "a medio hacer" y con hosts divergentes]** → Explícitamente rechazado (D1 opción a). El resolver nunca lee `usuario.moodle_host`.
- **[Crons sin ctx no tienen universidad activa]** → No se rompen: gate se mantiene; se eleva como OQ2 al checkpoint humano (dominio con credenciales → gobernanza ALTA).
- **[Materia/Comisión de otra universidad sincronizada contra el host activo]** (OQ1/decisión abierta #5) → Recomendación: check defensivo barato `materia.universidad_id == universidad_id` en los entrypoints de sync antes de mintear el token; el aislamiento fuerte lo garantiza Fase 4. Ver Open Questions.
- **[LOC/archivo]** → Vigilar 500 LOC en `moodle_service.py` (ya grande) y `usuario_repository.py`; el resolver es chico, pero medir tras el cambio.

## Migration Plan

1. **Prerrequisito operativo (OP-1, BLOQUEANTE)**: setear `Universidad.moodle_host` de TUPaD en producción (`UPDATE universidades SET moodle_host='<host real>' WHERE nombre LIKE '%Programación a Distancia%'`). Decidir el host correcto a mano (en prod había 3 valores divergentes en `usuarios.moodle_host`). **Sin esto, no se deploya Fase 3.**
2. Implementar el resolver en repo (D2) + tests. Sin consumirlo aún.
3. Migrar los services **de a uno** (D3), en orden de menor a mayor riesgo, cada uno con sus tests. `moodle_grade_service` es el más barato (ya tiene `ctx`).
4. Rediseño de perfil (D4) + tests.
5. Verificación integral: suite completa verde; invariante mono-universidad confirmado.
6. **Rollback**: como los campos viejos `usuarios.moodle_*` **conviven** (no se borran hasta Fase 6) y no hay cambios de esquema, revertir es volver el código a leer la fuente vieja (revert del PR). Datos intactos.

## Open Questions — RESUELTAS (checkpoint humano, decisión de producto)

1. **(OQ1 — Decisión abierta #5 del plan) Validación cruzada Moodle** — **RESUELTA: se incluye en Fase 3.** Check defensivo `materia.universidad_id == universidad_id_activa` en los entrypoints de sync Moodle (`moodle_service.get_pendientes`, `moodle_import_service`, `moodle_grade_service`, y demás entrypoints de sync que reciben una materia/comisión), antes de mintear el token, para evitar pegarle con un `course_id`/`group_id` de la universidad A contra el campus de la universidad B. Guard puntual (403/409), NO es el aislamiento general de queries — eso sigue siendo Fase 4.
2. **(OQ2) Crons/jobs de fondo sin ctx** — **RESUELTA: la config guarda `universidad_id`.** Se migran las tablas de config de los crons (`notificacion_config`, `snapshot_config` — nombres reales de tabla/modelo a confirmar en el código) agregando una columna `universidad_id` (FK → `universidades`, nullable → backfill a TUPaD → NOT NULL). Cada cron lee la universidad desde su propia fila de config, sin depender de un JWT/ctx de request.
3. **(OQ3) Perfil `moodle_host` en la respuesta** — **RESUELTA: read-only (D4).** Se muestra desde `Universidad.moodle_host` de la universidad activa; no se saca del `PerfilResponse`.
4. **(OQ4) Check de startup opcional (D1 opción c)** — **RESUELTA: NO se implementa.** Alcanza con el gate operativo (Task 0, prerrequisito de DEPLOY) + el fail-fast 424 por request del resolver. No se agrega verificación de arranque extra en esta fase.
5. **(OQ5) Superadmin sin universidad activa** operando un flujo Moodle — **RESUELTA: `409/424` pidiendo elegir universidad.** Si `get_universidad_activa` devuelve `universidad_id=None` (superadmin sin universidad elegida), los entrypoints de flujos Moodle responden con un error accionable pidiendo seleccionar universidad activa antes de continuar (no hay credenciales/host sin membresía/universidad).

**Nota sobre el gate OP-1 (D1)**: el gate duro (host de TUPaD seteado) es prerrequisito de **DEPLOY**, no de desarrollo — los tests de esta fase usan fixtures con host seteado. El fail-fast 424 del resolver (sin fallback al `usuario.moodle_host` viejo) se implementa y testea en esta fase independientemente del estado del gate operativo en producción.
