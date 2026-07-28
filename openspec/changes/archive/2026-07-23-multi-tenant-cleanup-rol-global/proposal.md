## Why

Fase 6 y última del plan multi-tenant. Desde la Fase 0, `usuarios.rol` y las tres columnas `usuarios.moodle_*` conviven con sus reemplazos en `usuario_universidad`. Esa convivencia ya cumplió su función —permitió avanzar sin romper nada— y ahora es el último lugar donde el rol de una persona sigue siendo global en vez de ser por universidad.

Mientras la columna exista, el sistema tiene dos fuentes de verdad para el rol y nada impide que alguien lea la equivocada. De hecho ya pasa: al crear un usuario se escribe `usuarios.rol`, no una membresía.

Y hay un agujero que este cleanup obliga a mirar de frente: **`usuario_repository.get_all()` no filtra por universidad**. `GET /usuarios` monta el contexto pero el repositorio ignora el scope, así que un ADMIN de una universidad ve los usuarios de las demás. La Fase 4 scopeó "las nueve entidades que cuelgan de materia" y `usuarios` no cuelga de materia: se coló por el hueco de la definición. Es invisible hoy porque hay una sola universidad cargada, exactamente como lo era el resto del scoping antes de tener dos. Lo mismo con `get_tutores()`, que alimenta el envío de notificaciones.

## What Changes

**Parte 1 — Aislamiento de usuarios (deuda de Fase 4)**

- `usuario_repository.get_all()` y `get_tutores()` reciben `universidad_id` y filtran por membresía activa en esa universidad.
- El filtro por rol deja de mirar `usuarios.rol` y pasa a mirar `usuario_universidad.rol` de la universidad activa.
- `notificacion_service._cargar_tutores()` propaga la universidad: deja de poder notificar a tutores de otras universidades.
- Se elimina `get_coordinadores()`, que no tiene ningún llamador.

**Parte 2 — El rol se escribe como membresía**

- **BREAKING** `POST /usuarios` crea el usuario **y su membresía** en la universidad activa, con el rol recibido. Un superadmin en modo global recibe 400 y debe elegir una universidad primero, igual que al crear una materia.
- **BREAKING** `PUT /usuarios/{id}` con un rol nuevo actualiza el rol **de la membresía** en la universidad activa, no un rol global.
- La operación de alta pasa a ser transaccional: usuario y membresía se crean juntos o no se crea ninguno.

**Parte 3 — Los últimos lectores del rol global**

- `routers/materias.py` (dos sitios), `routers/rubricas.py`, `routers/usuarios.py`, `routers/perfil.py` y `rubrica_service._validar_acceso_materia` pasan a resolver el rol por `ctx`.
- `PerfilResponse.rol` pasa a informar el rol en la universidad activa.

**Parte 4 — Eliminación de las columnas**

- **BREAKING** Se eliminan de `usuarios`: `rol`, `moodle_username`, `moodle_password_encrypted` y `moodle_host`.
- Migración con `downgrade` que recrea las columnas y repuebla desde `usuario_universidad`.
- Los tests que construyen `Usuario(rol=...)` (47 archivos) se migran a crear la membresía correspondiente.

## Capabilities

### New Capabilities
- `usuarios-scoping-por-universidad`: aislamiento del listado y la búsqueda de usuarios por universidad activa, y alta/edición del rol como membresía.

### Modified Capabilities
<!-- Ninguna. Las specs vigentes describen comportamiento que este change no
     altera: sólo remueve la fuente de verdad duplicada que ya nadie debía leer. -->

## Impact

**Base de datos** — irreversible en la práctica, aunque el `downgrade` exista.

- `usuarios`: se eliminan 4 columnas.
- Verificado contra la base real antes de proponer: 33 usuarios tienen credenciales en las columnas viejas y **0** de ellos carecen de la credencial equivalente en su membresía. El borrado no pierde datos.
- Los 56 usuarios tienen membresía activa, así que ninguno queda sin rol.

**Backend**

- `app/repositories/usuario_repository.py`: `get_all`, `get_tutores`, baja de `get_coordinadores`
- `app/services/usuario_service.py`: alta y edición transaccionales con membresía
- `app/services/notificacion_service.py`, `app/services/rubrica_service.py`
- `app/routers/`: `usuarios.py`, `materias.py`, `rubricas.py`, `perfil.py`
- `app/models/usuario.py`, `app/schemas/usuario.py`, `app/schemas/perfil.py`
- Nueva migración Alembic
- ~47 archivos de test que construyen `Usuario(rol=...)`

**Frontend**

- Sin cambios de contrato en el alta de usuario: sigue enviando `rol` y la universidad sale del token.
- A revisar: pantallas que muestran el rol de un usuario administrado, que ahora es por universidad.

**Riesgos**

- Es el punto de no retorno del plan. Después de esto no hay convivencia: si algo lee el rol global, deja de compilar o de funcionar.
- 47 archivos de test es una superficie grande de cambio mecánico donde es fácil colar un test que ya no verifica lo que dice verificar.
- El agujero de aislamiento de usuarios es una filtración cross-tenant real: necesita test con dos universidades, que es la única forma de verlo.
