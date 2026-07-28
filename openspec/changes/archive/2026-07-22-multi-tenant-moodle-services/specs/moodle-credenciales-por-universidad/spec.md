## ADDED Requirements

### Requirement: La fuente del host Moodle es la universidad activa del request

El sistema SHALL obtener el campus Moodle (`moodle_host`) usado por todo service que hable con Moodle desde el `moodle_host` de la **universidad activa del request** (`Universidad.moodle_host` de `ctx.universidad_id`, entregado por `get_universidad_activa` de Fase 1), y NO desde el campo global `usuarios.moodle_host`. El campo `usuarios.moodle_host` SHALL dejar de ser leído por los services (convive en la base hasta Fase 6, pero no es fuente de verdad).

#### Scenario: El host se toma de la universidad activa

- **WHEN** un service construye un token Moodle para un request cuya universidad activa tiene `moodle_host = "https://campus.uni.edu"`
- **THEN** el service usa `"https://campus.uni.edu"` como host, sin leer `usuarios.moodle_host`

#### Scenario: El host global viejo es ignorado

- **WHEN** un usuario tiene `usuarios.moodle_host = "https://viejo.host"` (campo viejo) pero la universidad activa tiene `moodle_host = "https://nuevo.campus"`
- **THEN** el service usa `"https://nuevo.campus"` (el host global viejo es ignorado como fuente)

### Requirement: La fuente de las credenciales Moodle es la membresía activa

El sistema SHALL obtener el usuario y la contraseña Moodle (`moodle_username`, `moodle_password_encrypted`) usados por los services desde la membresía `(usuario, universidad activa)` (`UsuarioUniversidad.moodle_username`/`moodle_password_encrypted` para `(usuario.id, ctx.universidad_id)`), y NO desde `usuarios.moodle_username`/`moodle_password_encrypted`. El cifrado de la contraseña SHALL permanecer idéntico (Fernet, AES-128-CBC + HMAC-SHA256); solo cambia el origen de los bytes cifrados.

#### Scenario: Credenciales tomadas de la membresía activa

- **WHEN** un usuario con dos membresías tiene credenciales distintas en la universidad A y la universidad B, y opera con la universidad B activa
- **THEN** el service usa las credenciales de la membresía en B, no las de A ni las globales del usuario

#### Scenario: El descifrado usa el mismo mecanismo Fernet

- **WHEN** el service necesita la contraseña Moodle en claro para autenticar contra el campus
- **THEN** descifra `UsuarioUniversidad.moodle_password_encrypted` con el mismo mecanismo Fernet que hoy usa el campo global

### Requirement: Resolver único de credenciales Moodle en la capa Repository

El sistema SHALL proveer un único resolver, en la capa Repository (`UsuarioRepository`), que dado `(usuario_id, universidad_id)` devuelva la terna `(moodle_host, moodle_username, moodle_password_encrypted)` de la nueva fuente (membresía activa + su universidad). Los services SHALL consumir ese resolver y NO SHALL ejecutar consultas SQLAlchemy ni navegar `usuario.moodle_*` para obtener estos datos (ARCH-001: el acceso a datos vive en el repositorio).

#### Scenario: El service obtiene la terna por el resolver, no por SQL

- **WHEN** se inspecciona un service que hoy leía `usuario.moodle_host`/`moodle_username`/`moodle_password_encrypted`
- **THEN** el service obtiene host+credenciales llamando al resolver del repositorio con `(usuario_id, universidad_id)`, sin ejecutar SQLAlchemy en la capa de servicio

#### Scenario: Membresía inexistente o sin credenciales

- **WHEN** el resolver se invoca para un `(usuario_id, universidad_id)` sin membresía activa, o cuya membresía no tiene credenciales Moodle cargadas
- **THEN** el resolver indica la ausencia (retorno vacío) y el service responde `HTTP 424` pidiendo configurar las credenciales Moodle

### Requirement: Fail-fast cuando el host de la universidad activa es NULL (OP-1)

El sistema SHALL fallar de forma explícita cuando el `moodle_host` de la universidad activa es NULL o vacío: el service SHALL responder `HTTP 424` con un mensaje accionable indicando que el campus Moodle de la universidad no está configurado. El sistema NO SHALL caer al valor viejo `usuarios.moodle_host` como fallback (evita reintroducir hosts divergentes por usuario para una misma universidad y evita enmascarar la falta de configuración del campus).

#### Scenario: Host de la universidad activa sin configurar

- **WHEN** un service intenta construir un token Moodle y la universidad activa tiene `moodle_host` NULL o vacío
- **THEN** el service responde `HTTP 424` con un detalle accionable (el campus no está configurado) y NO intenta autenticar contra un host vacío ni leer el host global viejo

#### Scenario: Sin fallback al host global viejo

- **WHEN** la universidad activa tiene `moodle_host` NULL pero el usuario tiene `usuarios.moodle_host` con un valor viejo
- **THEN** el sistema NO usa ese valor viejo; el resultado es el `HTTP 424` de campus no configurado

### Requirement: Enganche de la universidad activa a los services

El sistema SHALL proveer a cada service que lee datos Moodle el `universidad_id` activo del request. Los routers, que ya disponen del `ContextoUniversidad` (`ctx`, Fase 2), SHALL pasar `ctx.universidad_id` al service. Los métodos de service que hoy leen `usuario.moodle_*` SHALL recibir un parámetro `universidad_id` (o, donde el `ctx` ya está threadeado como en `moodle_grade_service`, SHALL usar `ctx.universidad_id`). El acceso a datos que esto requiera SHALL hacerse vía repositorio (nunca SQL crudo en el service).

#### Scenario: El router pasa la universidad activa al service

- **WHEN** un endpoint que dispara un flujo Moodle invoca a su service
- **THEN** el endpoint provee al service el `universidad_id` de la universidad activa (`ctx.universidad_id`) obtenido de `get_universidad_activa`

#### Scenario: Reuso del ctx ya presente

- **WHEN** un método de service ya recibe `ctx: ContextoUniversidad` (caso `moodle_grade_service`)
- **THEN** ese método usa `ctx.universidad_id` como fuente del `universidad_id`, sin agregar un parámetro nuevo

### Requirement: Las credenciales Moodle del perfil se escriben en la membresía activa

El sistema SHALL escribir las credenciales Moodle configuradas desde el perfil (`moodle_username`, `moodle_password_encrypted`) en la membresía `(usuario, universidad activa)` (`UsuarioUniversidad`), y NO en `usuarios.moodle_*`. El endpoint de configuración de credenciales del perfil SHALL dejar de aceptar `moodle_host` (el campus es propiedad de la Universidad, no editable por el usuario). El `moodle_host` mostrado en el perfil SHALL ser de solo lectura, tomado del `moodle_host` de la universidad activa.

#### Scenario: Guardar credenciales las persiste en la membresía activa

- **WHEN** un usuario con la universidad B activa guarda sus credenciales Moodle desde el perfil
- **THEN** el sistema persiste `moodle_username`/`moodle_password_encrypted` en su `UsuarioUniversidad` de la universidad B, sin escribir `usuarios.moodle_*`

#### Scenario: El perfil no acepta editar el host

- **WHEN** se inspecciona el request de configuración de credenciales Moodle del perfil
- **THEN** el schema no incluye `moodle_host` (el host es propiedad de la Universidad y se muestra read-only)

#### Scenario: El host del perfil se muestra desde la universidad activa

- **WHEN** un usuario consulta su perfil (`GET /perfil`) con la universidad B activa
- **THEN** el `moodle_host` de la respuesta es el `moodle_host` de la universidad B (read-only), y `moodle_configured` se computa desde las credenciales de la membresía en B

### Requirement: Invariante de equivalencia mono-universidad

El sistema SHALL preservar el comportamiento observable de todos los flujos Moodle en el estado mono-universidad actual (una sola universidad TUPaD con su `moodle_host` seteado por OP-1, y cada usuario con exactamente una membresía activa cuyas credenciales Moodle coinciden con las que tenía en los campos globales viejos). El cambio de fuente NO SHALL alterar qué host ni qué credenciales se usan en ese estado.

#### Scenario: Un tutor de TUPaD obtiene el mismo token que antes

- **WHEN** un tutor con una única membresía en TUPaD (host seteado, credenciales == las viejas globales) dispara un flujo Moodle
- **THEN** el host y las credenciales resueltos por la nueva fuente son equivalentes a los que producía la fuente global vieja, y el resultado del flujo es el mismo
