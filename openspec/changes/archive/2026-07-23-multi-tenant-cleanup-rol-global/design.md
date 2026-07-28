## Context

Fase 6 y última de `PLAN-MULTI-TENANT-UNIVERSIDADES.md`. Las Fases 0–5 están implementadas y archivadas, y OP-1/OP-2 quedaron cerradas por la migración `a71e5c9d3b82`.

Desde la Fase 0, `usuarios.rol` y `usuarios.moodle_{username,password_encrypted,host}` conviven con sus reemplazos en `usuario_universidad` y `universidades`. Esa convivencia fue deliberada y sirvió: permitió avanzar cinco fases sin romper nada.

Relevamiento hecho contra el código y la base real antes de escribir esto:

**Datos — seguro de borrar**

| Chequeo | Resultado |
|---|---|
| Usuarios con `moodle_username` cargado | 33 |
| De esos, sin credencial equivalente en su membresía | **0** |
| Usuarios sin membresía activa (quedarían sin rol) | **0** |

**Código — `moodle_*` sale limpio, `rol` no**

Las tres columnas `moodle_*` sólo están declaradas en `app/models/usuario.py`; ningún código las lee (la Fase 3 movió todo al resolver). `rol`, en cambio, sigue vivo:

- **Escritura**: `usuario_service.crear_usuario` (`rol=data.rol`) y `actualizar_usuario` (`user.rol = data.rol`)
- **Lectura**: `usuario_repository.get_all` y `get_tutores`; `routers/materias.py:53,131`; `routers/rubricas.py:66`; `routers/usuarios.py:49`; `routers/perfil.py:124`; `rubrica_service._validar_acceso_materia`
- `usuario_repository.get_coordinadores` no tiene llamadores: es código muerto
- ~47 archivos de test construyen `Usuario(rol=...)`

**Agujero de aislamiento heredado de la Fase 4**

`usuario_repository.get_all()` no recibe ni aplica `universidad_id`. `GET /usuarios` monta `ctx` pero el repositorio ignora el scope: un ADMIN de una universidad ve los usuarios de las demás. `get_tutores()` tiene el mismo problema y alimenta `notificacion_service._cargar_tutores()`, o sea que las notificaciones pueden cruzar universidades.

La Fase 4 scopeó "las nueve entidades que cuelgan de materia"; `usuarios` no cuelga de materia y se coló por el hueco de esa definición. Es invisible hoy porque hay una sola universidad cargada — igual que lo era el resto del scoping antes de tener dos.

Gobernanza: **CRITICAL**. Toca permisos, el alta de usuarios y borra columnas de forma irreversible.

## Goals / Non-Goals

**Goals:**

- Una sola fuente de verdad para el rol: la membresía.
- Cerrar la filtración cross-tenant del listado de usuarios y de las notificaciones.
- Que el alta y la edición de usuarios escriban el rol donde corresponde.
- Eliminar las cuatro columnas sin perder un solo dato.

**Non-Goals:**

- ABM completo de membresías (asignar, quitar, ver todas las membresías de una persona). Sigue siendo la open question que arrastramos desde la Fase 5.
- Permitir que un mismo usuario se cree simultáneamente en varias universidades.
- Rediseñar la pantalla de usuarios del frontend.
- Tocar `es_superadmin`, que no es un rol sino un bypass y vive bien donde está.

## Decisions

### D1 — El orden es: aislar, migrar escrituras, migrar lecturas, borrar

Las columnas se eliminan **al final**, en su propia tarea, y sólo cuando ningún código las toca.

**Por qué**: mientras la columna existe, un olvido se manifiesta como comportamiento raro pero el sistema sigue en pie. Si se borra primero, un olvido es un `UndefinedColumn` en producción. El orden convierte errores silenciosos en errores de compilación, que es lo que queremos.

### D2 — El scoping de usuarios se hace por `EXISTS` sobre la membresía

`get_all` y `get_tutores` filtran con un `EXISTS` sobre `usuario_universidad` con `universidad_id` y `activo = true`, siguiendo el patrón que la Fase 4 ya usó en `dashboard_repository`.

**Por qué un `EXISTS` y no un `JOIN`**: un usuario puede tener varias membresías; un `JOIN` duplicaría filas y rompería la paginación y los conteos de forma sutil. El `EXISTS` no multiplica.

`universidad_id = None` significa "sin filtro", igual que en toda la Fase 4, y es lo que habilita el modo global del superadmin.

### D3 — El filtro por rol se resuelve dentro del mismo `EXISTS`

Cuando se filtra por rol, la condición de rol va **dentro** del `EXISTS` de la membresía, no como un `WHERE` separado.

**Por qué**: "TUTOR" debe significar "tutor *en esta universidad*". Si el rol se evalúa fuera del `EXISTS`, una persona que es COORDINADOR acá y TUTOR allá aparecería al filtrar por TUTOR en la universidad equivocada. Es exactamente el tipo de fuga que este plan viene a cerrar.

### D4 — El alta es transaccional y toma la universidad del contexto

`crear_usuario` recibe `universidad_id` desde `ctx`, crea `Usuario` y `UsuarioUniversidad` en la misma transacción, y falla con 400 si no hay universidad activa.

**Por qué el contexto y no un parámetro explícito**: no cambia el contrato del endpoint ni el formulario del frontend, y es coherente con cómo la Fase 4 resolvió la creación de materias (`ctx.universidad_id`, 400 si falta). Un superadmin que quiera crear usuarios elige universidad primero, igual que para cualquier otra alta.

**Por qué transaccional**: un usuario sin membresía no puede iniciar sesión (Fase 1 responde 403 a quien no tiene universidad asignada). Crear el usuario y fallar al crear la membresía dejaría una cuenta fantasma imposible de usar y difícil de diagnosticar.

**Alternativa descartada**: `UsuarioCreate` con `universidad_id` explícito. Más flexible para un superadmin, pero cambia el contrato del endpoint y el formulario del frontend sin necesidad real hoy.

### D5 — `PerfilResponse.rol` pasa a ser el rol de la membresía activa

**Por qué**: hoy sale de `current_user.rol`. Al no existir esa columna, la única respuesta correcta es el rol en la universidad activa — que además es el que la interfaz necesita para decidir qué mostrar.

### D6 — La migración es reversible de verdad

El `downgrade` recrea las cuatro columnas **y las repuebla** desde `usuario_universidad`, tomando la membresía activa más antigua de cada usuario.

**Por qué**: un `downgrade` que sólo recrea columnas vacías es un botón de pánico que no salva a nadie. La reversión tiene que devolver un sistema usable. Se documenta explícitamente que es una reversión con pérdida cuando alguien tiene roles distintos en varias universidades: el rol global no puede representar eso, y elegir el de la membresía más antigua es una convención, no una recuperación fiel.

### D7 — Los tests migran a fixtures de membresía, no a parches

Los ~47 archivos que construyen `Usuario(rol=...)` pasan a crear usuario + membresía mediante un helper compartido.

**Por qué**: la tentación es borrar el `rol=` y listo. Pero muchos de esos tests dependen de que el usuario TENGA ese rol para que el escenario tenga sentido; sacarlo sin crear la membresía deja tests que pasan sin verificar nada. Un helper único hace que la migración sea revisable de un vistazo.

## Risks / Trade-offs

- **Punto de no retorno del plan** → el borrado va último (D1), con `downgrade` que repuebla (D6) y verificación del ciclo completo contra Postgres real antes de commitear.
- **47 archivos de test es mucha superficie mecánica; es fácil colar un test que ya no verifica nada** → helper único (D7) y comparación estricta del conteo antes/después: si el total baja, hay tests que se apagaron.
- **La filtración de usuarios sólo se ve con dos universidades** → el gate de esta fase es un test de aislamiento con dos universidades, igual que el de la Fase 4. Con una sola, el filtro es indistinguible de no tener filtro.
- **Alguien puede quedar sin rol si su membresía no existe** → verificado: 0 usuarios sin membresía activa. La migración además debe abortar si encuentra alguno, en vez de dejarlo sin rol.
- **`_validar_acceso_materia` de rúbricas es lógica de permisos** → se migra a `ctx` como el resto, con los tests de caracterización corriendo antes y después.

## Migration Plan

1. Partes 1–3 sin tocar el esquema: el código deja de leer y escribir las columnas.
2. Suite verde con las columnas todavía presentes. Esto prueba que nada las necesita.
3. Recién ahí, la migración que las elimina.
4. Verificación del ciclo `upgrade` → `downgrade` → `upgrade` contra el Postgres real, comprobando que el downgrade repuebla el rol.

Precondición: ningún usuario sin membresía activa. Verificado hoy (0), pero la migración lo revalida y aborta si no se cumple.

Rollback: `alembic downgrade -1` recrea y repuebla. Con la salvedad de D6 sobre roles divergentes entre universidades.

## Open Questions

- Sigue sin resolverse la gestión de membresías desde la interfaz: hoy no hay forma de sumar una persona existente a una segunda universidad, ni de quitarle una membresía. Con `usuarios.rol` eliminado, esta carencia se vuelve más visible, porque el rol pasa a ser algo que sólo existe dentro de una universidad. Se propone un change propio, y esta fase no lo bloquea.
- ¿El listado de usuarios debería poder mostrar, para un superadmin en modo global, a qué universidades pertenece cada persona? Hoy la respuesta no lo informa y sería la base natural de ese ABM de membresías.
