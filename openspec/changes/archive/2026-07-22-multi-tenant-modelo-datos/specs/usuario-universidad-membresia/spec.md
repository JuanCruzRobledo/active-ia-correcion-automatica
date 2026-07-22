## ADDED Requirements

### Requirement: Membresía usuario-universidad con rol scopeado

El sistema SHALL introducir una tabla `usuario_universidad` (junction con atributos, siguiendo el mismo patrón que `CoordinadorMateria` y `ComisionTutor`) que vincula un `Usuario` con una `Universidad` y porta el rol de ese usuario **en esa universidad**. Cada fila SHALL tener: `id` (PK), `usuario_id` (FK → `usuarios.id`, NOT NULL), `universidad_id` (FK → `universidades.id`, NOT NULL), `rol` (`RolEnum`, NOT NULL — scopeado a esta membresía), `moodle_username` (String, nullable), `moodle_password_encrypted` (Text, nullable, cifrado con el mismo Fernet/AES que hoy usa `usuarios.moodle_password_encrypted`), `activo` (Boolean, NOT NULL, default `true`), y `UniqueConstraint(usuario_id, universidad_id)`. El modelo `UsuarioUniversidad` SHALL vivir en `app/models/usuario_universidad.py` y registrarse en `app/models/__init__.py`. `Usuario` SHALL exponer una relationship a `UsuarioUniversidad`.

#### Scenario: Se crea la tabla usuario_universidad con sus columnas y unique

- **WHEN** se aplica la migración que crea `usuario_universidad`
- **THEN** la tabla existe con columnas `id`, `usuario_id`, `universidad_id`, `rol`, `moodle_username`, `moodle_password_encrypted`, `activo`
- **THEN** existe un `UniqueConstraint(usuario_id, universidad_id)`
- **THEN** `usuario_id` y `universidad_id` son FKs NOT NULL a `usuarios.id` y `universidades.id`

#### Scenario: Un usuario puede tener roles distintos en dos universidades

- **WHEN** se insertan dos membresías del mismo `usuario_id` con `universidad_id` distintos y `rol` distintos (ej. ADMIN en una, TUTOR en otra)
- **THEN** ambos inserts son válidos (el rol es por membresía, no global)

#### Scenario: No se permite membresía duplicada del mismo par usuario-universidad

- **WHEN** ya existe una membresía `(usuario_id=1, universidad_id=1)` y se intenta insertar otra con el mismo par
- **THEN** la base de datos SHALL rechazar el insert por el `UniqueConstraint(usuario_id, universidad_id)`

#### Scenario: Las credenciales Moodle de la membresía usan el mismo cifrado que hoy

- **WHEN** se guarda `moodle_password_encrypted` en una membresía
- **THEN** el valor SHALL estar cifrado con el mismo mecanismo Fernet (AES-128-CBC + HMAC-SHA256) de `app/core/security.py` — nunca en texto plano

### Requirement: Flag de admin global en Usuario

El modelo `Usuario` SHALL incorporar una columna `es_superadmin` (Boolean, NOT NULL, default `false`, con `server_default` equivalente). Esta columna marca al admin global. En esta fase la columna solo se introduce y se puebla en el backfill/operativo; su efecto de bypass del scoping se implementa en fases posteriores (Auth/permisos) y NO forma parte de este change.

#### Scenario: Se agrega es_superadmin con default false

- **WHEN** se aplica la migración que agrega `usuarios.es_superadmin`
- **THEN** la columna existe como Boolean NOT NULL con default `false`
- **THEN** todos los usuarios existentes quedan con `es_superadmin = false` tras la migración

### Requirement: Convivencia de los campos viejos de Usuario

En esta fase el sistema SHALL **mantener** las columnas existentes de `usuarios`: `rol`, `moodle_username`, `moodle_password_encrypted` y `moodle_host`. NO SHALL eliminarse ninguna de ellas en este change. La eliminación es una fase posterior (cleanup), condicionada a verificar en producción que ningún código las usa. Esto garantiza que el sistema siga funcionando igual mientras solo exista una universidad.

#### Scenario: Los campos viejos siguen presentes tras la migración

- **WHEN** se completa toda la migración de este change
- **THEN** `usuarios.rol`, `usuarios.moodle_username`, `usuarios.moodle_password_encrypted` y `usuarios.moodle_host` siguen existiendo con sus valores intactos

#### Scenario: El comportamiento actual del sistema no cambia

- **WHEN** el código existente lee `usuario.rol` o `usuario.moodle_host` tras aplicar este change
- **THEN** obtiene los mismos valores que antes de la migración (convivencia, sin regresión)
