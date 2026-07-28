## ADDED Requirements

### Requirement: Universidad semilla TUPaD

La migración SHALL crear una universidad semilla con `nombre = "Tecnicatura Universitaria en Programación a Distancia"` (nombre corto de referencia: TUPaD) y `activa = true`. Todos los datos existentes del sistema SHALL migrarse a esta universidad. El seed SHALL ser idempotente en la práctica: si la universidad ya existe (por `nombre`), la migración SHALL reutilizarla en vez de duplicarla.

#### Scenario: El seed inserta la universidad TUPaD

- **WHEN** se ejecuta la revisión de seed y no existe una universidad con ese `nombre`
- **THEN** se inserta una fila en `universidades` con `nombre = "Tecnicatura Universitaria en Programación a Distancia"` y `activa = true`

#### Scenario: El seed no duplica si ya existe

- **WHEN** se ejecuta la revisión de seed y ya existe una universidad con ese `nombre`
- **THEN** no se inserta una fila nueva; se reutiliza la existente para el backfill

### Requirement: moodle_host de seed tomado de producción (paso manual)

El valor real de `universidades.moodle_host` de la universidad semilla SHALL tomarse del valor que hoy tienen los usuarios en `usuarios.moodle_host` en producción. La migración NO SHALL inventar ni hardcodear un `moodle_host`. Confirmar en producción que ese valor es el mismo para todos los usuarios y, en la revisión de seed, dejarlo como el `moodle_host` de TUPaD (o dejarlo NULL y setearlo en un paso operativo documentado). Este es un **paso operativo manual**, no una decisión automatizable.

#### Scenario: El moodle_host de seed proviene de datos reales

- **WHEN** se prepara la revisión de seed
- **THEN** el `moodle_host` de TUPaD se toma del valor real de `usuarios.moodle_host` en producción, o queda NULL para setearse manualmente
- **THEN** en ningún caso se hardcodea un host inventado en la migración

### Requirement: Backfill de universidad_id por tabla del árbol

Tras crear la universidad TUPaD, la migración SHALL backfillear `universidad_id` en todas las tablas del árbol propagando desde la materia:
- `materias`: `universidad_id = <id_tupad>` (directo, por seed).
- `comisiones`: propagar vía `materia_id` → `materias.universidad_id`.
- `entregas`: propagar vía `comision_id` → `comisiones.universidad_id`.
- `correcciones`: propagar vía `entrega_id` → `entregas.universidad_id`.
- `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots`: propagar vía `materia_id` → `materias.universidad_id`.

El backfill SHALL dejar cero filas con `universidad_id IS NULL` en cada una de esas tablas antes de aplicar el NOT NULL.

#### Scenario: Todas las materias quedan en TUPaD

- **WHEN** se ejecuta el backfill con una sola universidad existente
- **THEN** toda fila de `materias` tiene `universidad_id = <id_tupad>`

#### Scenario: Las tablas hijas heredan el universidad_id de su materia

- **WHEN** se ejecuta el backfill en cascada
- **THEN** `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs` y `avance_snapshots` quedan sin ninguna fila con `universidad_id IS NULL`
- **THEN** cada fila tiene el mismo `universidad_id` que su materia ancestro

### Requirement: Backfill de membresías (una por usuario)

Por cada `Usuario` existente, la migración SHALL crear exactamente una fila en `usuario_universidad` con: `universidad_id = <id_tupad>`, `rol = <el valor actual de usuarios.rol>`, `moodle_username = <el valor actual de usuarios.moodle_username>`, `moodle_password_encrypted = <el valor actual de usuarios.moodle_password_encrypted>` (copiado tal cual, ya cifrado — sin re-cifrar), y `activo = true`. El backfill de membresías SHALL respetar el `UniqueConstraint(usuario_id, universidad_id)` (no crear duplicados si se re-ejecuta).

#### Scenario: Cada usuario recibe su membresía TUPaD copiando su estado actual

- **WHEN** se ejecuta el backfill de membresías
- **THEN** por cada usuario existe una fila en `usuario_universidad` con `universidad_id = <id_tupad>`, `activo = true`, y `rol`/`moodle_username`/`moodle_password_encrypted` copiados de las columnas homónimas del usuario

#### Scenario: El password Moodle se copia cifrado, sin re-cifrar

- **WHEN** el backfill copia `moodle_password_encrypted` del usuario a la membresía
- **THEN** el valor se copia byte a byte (ya está cifrado) — la migración NO descifra ni re-cifra

#### Scenario: Re-ejecutar el backfill no duplica membresías

- **WHEN** el backfill de membresías se ejecuta y ya existe la membresía `(usuario, TUPaD)`
- **THEN** no se crea una segunda membresía para ese par

### Requirement: Asignación de es_superadmin como decisión manual

La decisión de **qué usuario(s) ADMIN existentes reciben `es_superadmin = true`** SHALL ser una decisión de negocio tomada a mano. La migración NO SHALL asumir que "todo ADMIN pasa a superadmin" ni setear `es_superadmin = true` automáticamente. El backfill SHALL dejar a todos los usuarios con `es_superadmin = false`, y la promoción de superadmins SHALL documentarse como un paso operativo manual posterior.

#### Scenario: El backfill no promueve superadmins automáticamente

- **WHEN** finaliza el backfill
- **THEN** todos los usuarios tienen `es_superadmin = false`
- **THEN** la promoción de uno o más ADMIN a superadmin queda como paso operativo manual documentado (no lo hace la migración)

### Requirement: Orden de la migración en varias revisiones

La migración SHALL partirse en varias revisiones Alembic (no una sola) para separar los cambios estructurales de los de datos y del endurecimiento de constraints. El orden SHALL ser: (1) crear `universidades`; (2) crear `usuario_universidad`; (3) agregar `universidad_id` nullable a las tablas del árbol y `usuarios.es_superadmin`; (4) seed TUPaD; (5) backfill de `universidad_id` en cascada; (6) backfill de membresías; (7) pasar `universidad_id` a NOT NULL y reemplazar el unique de `materias.codigo` por `(universidad_id, codigo)`. Cada revisión estructural SHALL tener su `downgrade` correspondiente.

#### Scenario: Las revisiones se aplican en orden y el sistema sigue operativo

- **WHEN** se aplican todas las revisiones con `alembic upgrade head` sobre una base con datos de una sola universidad
- **THEN** cada revisión de datos corre después de las estructurales de las que depende (columnas nullable antes del backfill; NOT NULL después del backfill)
- **THEN** al terminar, el sistema sigue funcionando igual (una sola universidad, campos viejos intactos)

#### Scenario: Las revisiones estructurales son reversibles

- **WHEN** se ejecuta `alembic downgrade` de una revisión estructural
- **THEN** existe un `downgrade` que revierte el cambio (elimina columna/constraint/tabla) en orden inverso, respetando las FKs
