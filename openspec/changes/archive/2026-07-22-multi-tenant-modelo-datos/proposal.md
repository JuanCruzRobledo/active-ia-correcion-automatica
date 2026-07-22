## Why

Active-IA hoy es **mono-tenant implícito**: existe UNA sola universidad (TUP/TUPaD) hardcodeada en el modelo de datos, sin que exista el concepto explícito de "universidad". El rol del usuario es un campo único global (`usuarios.rol`) y el link del campus Moodle vive por usuario (`usuarios.moodle_host`). En cuanto exista una segunda universidad, nada de eso alcanza. Este change introduce **Universidad como entidad tenant de primer nivel** a nivel de **modelo de datos** y migra todo lo existente a una universidad semilla, sin cambiar el comportamiento del sistema (sigue habiendo una sola universidad).

> **Fase 0 de 6.** Este es el primer change de un feature multi-tenant grande, partido en un change por fase. **Este change SOLO toca el modelo de datos y la migración de datos.** NO toca auth/JWT (Fase 1), NI `permissions.py` (Fase 2), NI los services de Moodle (Fase 3), NI el scoping real de queries (Fase 4), NI el frontend (Fase 5), NI el cleanup de campos viejos (Fase 6). El objetivo explícito es que, tras aplicar esta migración, **todo siga funcionando exactamente igual** porque hay una única universidad y los campos viejos se mantienen (convivencia).

## What Changes

- **Nueva tabla `universidades`**: `id`, `nombre` (unique), `moodle_host` (nullable), `activa` (bool), timestamps. Entidad tenant de primer nivel.
- **Nueva tabla `usuario_universidad`** (junction con atributos, mismo patrón que `CoordinadorMateria`/`ComisionTutor`): `usuario_id`, `universidad_id`, `rol` (scopeado a esta membresía), `moodle_username`, `moodle_password_encrypted` (mismo cifrado Fernet), `activo`, `UniqueConstraint(usuario_id, universidad_id)`. Habilita que un usuario tenga **rol distinto por universidad** y credenciales Moodle **por (usuario, universidad)**.
- **`usuarios`**: ➕ nueva columna `es_superadmin: bool` (default `False`) — admin global que en fases posteriores bypasea el scoping. **NO se eliminan** `rol`, `moodle_username`, `moodle_password_encrypted`, `moodle_host` (convivencia; se borran en Fase 6).
- **`universidad_id`** (FK → `universidades.id`, denormalizado en cascada) agregado a **todas las tablas que cuelgan del árbol de Materia**: `materias`, `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots`. Primero **nullable** (para backfill), luego **NOT NULL** tras backfillear.
- **`materias`**: **BREAKING** (a nivel de schema, no de datos con 1 universidad) — el unique global de `codigo` pasa a `UniqueConstraint(universidad_id, codigo)`: dos universidades podrán tener ambas una materia con código "PROG1".
- **Migración Alembic en varias revisiones**: crear tablas nuevas → columnas nullable + `es_superadmin` → seed universidad **"Tecnicatura Universitaria en Programación a Distancia" (TUPaD)** → backfill (materias por seed; el resto propagando por su FK hacia materia; una membresía `usuario_universidad` por usuario copiando su `rol`/`moodle_*` actuales) → NOT NULL + nuevo `UniqueConstraint`.
- **Pasos operativos manuales documentados** (NO automatizados): el valor real del `moodle_host` de seed se toma de producción, y la decisión de qué ADMIN(s) reciben `es_superadmin=true` es una decisión de negocio a mano.

## Capabilities

### New Capabilities

- `universidad-entidad`: La entidad `Universidad` (tabla `universidades`) como tenant de primer nivel — campos, unicidad de `nombre`, `moodle_host` opcional, soft-state `activa`.
- `usuario-universidad-membresia`: La membresía usuario↔universidad (tabla `usuario_universidad`) con rol scopeado y credenciales Moodle por membresía, más el flag `usuarios.es_superadmin`, y la regla de convivencia (no se borran los campos viejos de `usuarios` en esta fase).
- `universidad-id-denormalizado`: La columna `universidad_id` denormalizada en cascada sobre todas las tablas del árbol de Materia, su invariante de coherencia con el padre, y el cambio de unicidad de `materias.codigo` a `(universidad_id, codigo)`.
- `migracion-datos-tupad`: La migración de datos existentes a la universidad semilla TUPaD — orden de revisiones Alembic, backfill por tabla, membresías 1-por-usuario, y los pasos operativos manuales (moodle_host de seed, asignación de `es_superadmin`).

### Modified Capabilities

<!-- Ninguna. Fase 0 es puramente aditiva a nivel de datos y NO cambia requisitos de
     ninguna capability existente. En particular, `autorizacion-por-pertenencia`
     (permisos/roles) queda DELIBERADAMENTE intacta: su refactor es la Fase 2. -->

## Impact

**Backend — Modelos (nuevos):**
- `app/models/universidad.py` (nuevo) — `Universidad`
- `app/models/usuario_universidad.py` (nuevo) — `UsuarioUniversidad`

**Backend — Modelos (columnas nuevas, sin quitar nada):**
- `app/models/usuario.py` — ➕ `es_superadmin`, relationship a `UsuarioUniversidad` (sin tocar `rol`/`moodle_*`)
- `app/models/materia.py` — ➕ `universidad_id`, cambiar unique de `codigo` a `(universidad_id, codigo)`
- `app/models/comision.py` (`Comision`), `app/models/entrega.py` (`Entrega`), `app/models/correccion.py` (`Correccion`) — ➕ `universidad_id`
- `app/models/unidad.py` (`Unidad`), `app/models/rubrica.py` (`Rubrica`), `app/models/examen_materia.py` (`ExamenMateria`) — ➕ `universidad_id`
- `app/models/cierre_cursada.py` (`CierreCursadaRun`), `app/models/avance.py` (`AvanceSnapshot`) — ➕ `universidad_id`
- `app/models/__init__.py` — registrar los 2 modelos nuevos

**Backend — Migraciones:**
- Varias revisiones nuevas en `backend/alembic/versions/` (ver `design.md` para el orden exacto)

**Datos / Operativo:**
- Seed de la universidad TUPaD; `moodle_host` de seed tomado de producción (paso manual)
- Backfill de todas las tablas del árbol + membresías; asignación de `es_superadmin` (decisión de negocio manual)

**Fuera de alcance (fases posteriores, NO en este change):**
- Auth/JWT y selección de universidad (Fase 1) · `permissions.py` (Fase 2) · services de Moodle (Fase 3) · scoping real de queries por `universidad_id` (Fase 4) · frontend (Fase 5) · borrado de `usuarios.rol`/`moodle_*` (Fase 6)
