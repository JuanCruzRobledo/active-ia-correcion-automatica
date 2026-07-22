## Context

Active-IA es hoy **mono-tenant implícito**: una sola universidad (TUP/TUPaD) hardcodeada en el modelo de datos. El rol vive como campo único global (`usuarios.rol`) y el campus Moodle por usuario (`usuarios.moodle_host`). El feature multi-tenant introduce `Universidad` como tenant de primer nivel y está partido en **6 fases, un change por fase**. Este documento cubre **solo la Fase 0: modelo de datos + migración de datos**.

Estado actual verificado sobre el código (2026-07-22):

- `usuarios` (`app/models/usuario.py`): tiene `rol: RolEnum` (NOT NULL, indexado), `moodle_username`, `moodle_password_encrypted`, `moodle_host` (nullable), más las API keys de Gemini/OpenRouter. `Usuario` usa `TimestampMixin`.
- Patrón de junction con atributos ya establecido: `CoordinadorMateria` (`coordinador_materia`) y `ComisionTutor` (`comision_tutor`) — PK `id`, dos FKs, `UniqueConstraint`, sin `TimestampMixin` (solo un `asignado_en`). `usuario_universidad` sigue este mismo patrón.
- Cifrado de credenciales: Fernet (AES-128-CBC + HMAC-SHA256) en `app/core/security.py`. Es lo que hay que reusar para `usuario_universidad.moodle_password_encrypted`.
- Mixins disponibles en `app/models/base.py`: `TimestampMixin` (`created_at`/`updated_at`) y `SoftDeleteMixin` (`deleted_at` + `is_deleted`). Convención de nombres de constraints definida en `Base.metadata` (prefijos `uq_`, `fk_`, `ix_`, etc.) — Alembic la respeta.
- Cadena de FKs del árbol de Materia confirmada leyendo cada modelo (ver Decisiones).

Gobernanza: **CRÍTICA/ALTA** — toca el modelo `Usuario`, base de auth y permisos aguas abajo. El patrón del proyecto es **proponer artefactos y esperar aprobación humana línea por línea antes de escribir código o correr migraciones**. Este change entrega solo artefactos OpenSpec.

## Goals / Non-Goals

**Goals:**

- Introducir la tabla `universidades` (tenant de primer nivel).
- Introducir la tabla `usuario_universidad` (membresía con rol scopeado + credenciales Moodle por membresía).
- Agregar `usuarios.es_superadmin` (default `false`), sin borrar los campos viejos.
- Agregar `universidad_id` (FK, denormalizado en cascada) a las 9 tablas del árbol de Materia, nullable → NOT NULL tras backfill.
- Cambiar la unicidad de `materias.codigo` a `(universidad_id, codigo)`.
- Migrar todos los datos existentes a una universidad semilla TUPaD, dejando el sistema funcionando **exactamente igual** (una sola universidad).
- Dejar el plan de migración en varias revisiones Alembic con orden y downgrade claros, y los pasos operativos manuales explícitos.

**Non-Goals (fases posteriores, NO en este change):**

- Auth/JWT con `universidad_activa_id`, endpoint de selección/switch de universidad (Fase 1).
- Refactor de `app/core/permissions.py` y sus puntos de uso; el bypass real de `es_superadmin` (Fase 2).
- Refactor de los services que leen `moodle_host`/`moodle_username`/`moodle_password` del usuario → leerlos desde `UsuarioUniversidad`/`Universidad` (Fase 3).
- Scoping real de queries por `universidad_id` en repositories/services, y la validación en servicio de la coherencia denormalizada (Fase 4).
- Frontend: selector de workspace, CRUD de universidades, perfil por universidad (Fase 5).
- Borrado de `usuarios.rol`/`moodle_*` (Fase 6).
- CRUD/endpoint/schemas de `Universidad` y `UsuarioUniversidad` (no se agregan routers ni Pydantic en esta fase; solo modelos + migración).

## Decisions

### D1 — Cadena de FKs para el backfill (confirmada leyendo los modelos)

Se agrega `universidad_id` a las **9 tablas primarias** del árbol, con esta cadena de backfill:

| Tabla (modelo) | FK hacia materia | Backfill de `universidad_id` |
|---|---|---|
| `materias` (`Materia`) | — (raíz) | `= <id_tupad>` (seed directo) |
| `comisiones` (`Comision`) | `materia_id` | vía `materias.universidad_id` |
| `entregas` (`Entrega`) | `comision_id` (y `rubrica_id`) | vía `comisiones.universidad_id` |
| `correcciones` (`Correccion`) | `entrega_id` | vía `entregas.universidad_id` |
| `unidades` (`Unidad`) | `materia_id` | vía `materias.universidad_id` |
| `rubricas` (`Rubrica`) | `materia_id` | vía `materias.universidad_id` |
| `examenes_materia` (`ExamenMateria`) | `materia_id` | vía `materias.universidad_id` |
| `cierre_cursada_runs` (`CierreCursadaRun`) | `materia_id` | vía `materias.universidad_id` |
| `avance_snapshots` (`AvanceSnapshot`) | `materia_id` | vía `materias.universidad_id` |

`entregas` tiene dos caminos posibles hacia la universidad (`comision_id` y `rubrica_id`, ambos cuelgan de materia); se usa `comision_id` por ser el eje natural del árbol. Ambos deben dar el mismo resultado con datos coherentes.

**Alternativa considerada:** derivar `universidad_id` por JOIN en runtime en vez de denormalizar. Descartada por decisión de producto (#4): se denormaliza en cascada para que el scoping de Fase 4 filtre por una columna local barata en cada tabla, sin JOINs hasta materia.

### D2 — Tablas hijas / historial / junction NO incluidas en esta fase

Además de las 9 primarias, el árbol tiene tablas hijas que NO tienen `materia_id` directo y cuelgan de una de las 9 vía otra FK. **Decisión: NO se les agrega `universidad_id` en Fase 0.** Se scopean vía su padre (que ya lleva `universidad_id`) y, si el scoping directo las necesitara, se evaluará en la fase que las toque. Son:

- `entregas_historial` (`entrega_actual_id` → `entregas`)
- `correccion_historial` (`entrega_id` → `entregas`)
- `componentes_unidad` (`unidad_id` → `unidades`)
- `cierre_cursada_alumnos` (`run_id` → `cierre_cursada_runs`)
- `avance_alumnos` (`snapshot_id` → `avance_snapshots`)
- `comision_tutor`, `coordinador_materia` (junctions usuario↔entidad; la pertenencia ya queda scopeada por el padre y por la membresía `usuario_universidad`)
- `snapshot_cron_config` (singleton global, no cuelga de materia — queda fuera)
- `moodle_sync` (`correccion_id` → `correcciones`; cuelga de corrección, mismo criterio que las hijas)

**Rationale:** el pedido fue denormalizar en "todas las tablas que cuelgan de materia"; el grep confirmó 9 dominios. Las hijas duplicarían la denormalización un nivel más abajo sin beneficio de scoping en Fase 0 (siempre se llega a ellas por su padre). Mantenerlas fuera reduce el blast radius de una fase CRÍTICA. Queda como **Open Question** para validación humana si alguna hija necesita `universidad_id` propio (ej. reporting que consulte `avance_alumnos` sin pasar por `avance_snapshots`).

### D3 — `usuario_universidad` sigue el patrón `ComisionTutor`, con extras

PK `id`; FKs `usuario_id`/`universidad_id` NOT NULL; `UniqueConstraint(usuario_id, universidad_id)` (nombre `uq_usuario_universidad_...` por convención). Extras sobre el patrón base: `rol` (`RolEnum`, reusa el tipo PG `rol_enum` ya existente — `create_type=False` en la columna nueva para NO recrear el enum), `moodle_username`, `moodle_password_encrypted`, `activo`. Se agrega relationship `Usuario.universidades` (o `membresias`) ↔ `UsuarioUniversidad.usuario`.

**Nota sobre el enum:** el tipo `rol_enum` ya existe en la base (lo creó la migración de `usuarios.rol`). La columna `usuario_universidad.rol` debe referenciarlo con `create_type=False` para evitar el error "type already exists". Mismo patrón que ya usa `componentes_unidad.modo_aprobacion` con `modoaprobacionenum` en el código actual.

### D4 — `es_superadmin` aditivo, campos viejos en convivencia

`usuarios.es_superadmin`: `Boolean`, NOT NULL, `default=False`, `server_default=text("false")` (mismo patrón que `gemini_api_key_paga`/`openrouter_api_key_valid` en el modelo actual). NO se tocan `rol`/`moodle_*`. La convivencia es deliberada: con una sola universidad el código viejo sigue leyendo `usuario.rol` sin cambios, y el borrado se difiere a Fase 6 tras verificar en producción.

### D5 — Unicidad de `materias.codigo`

Hoy `codigo` es `unique=True` a nivel columna (índice `ix`/`uq` global). Se reemplaza por `UniqueConstraint(universidad_id, codigo)`. En Alembic: `drop_constraint`/`drop_index` del unique viejo + `create_unique_constraint` del compuesto, **en la revisión post-backfill** (cuando `universidad_id` ya es NOT NULL). Verificar el nombre real del constraint viejo en la base (la convención genera `uq_materias_codigo` o un índice `ix_...`; confirmarlo con `\d materias` antes de escribir el drop).

## Migration Plan

Varias revisiones Alembic (recomendado; NO una sola), en este orden. Cada revisión estructural con su `downgrade`.

1. **R1 — crear `universidades`.** Tabla nueva con `id`, `nombre` (unique), `moodle_host` (nullable), `activa` (default true), timestamps. Downgrade: drop table.
2. **R2 — crear `usuario_universidad`.** Tabla nueva (ver D3). FKs a `usuarios`/`universidades`, unique compuesto, `rol` con `create_type=False`. Downgrade: drop table.
3. **R3 — columnas nullable + `es_superadmin`.** `add_column universidad_id` (nullable, FK) en las 9 tablas del árbol; `add_column usuarios.es_superadmin` (NOT NULL, server_default false). Downgrade: drop de esas columnas.
4. **R4 — seed TUPaD (data migration).** Insertar universidad `"Tecnicatura Universitaria en Programación a Distancia"` si no existe. `moodle_host`: **paso operativo** — tomar el valor real de `usuarios.moodle_host` de producción o dejar NULL para setear a mano (NO inventar). Downgrade: delete de esa fila (solo si no quedó referenciada).
5. **R5 — backfill de `universidad_id` en cascada (data migration).** `UPDATE materias SET universidad_id=<id_tupad>`; luego propagar en orden: `comisiones` (JOIN `materias`), `entregas` (JOIN `comisiones`), `correcciones` (JOIN `entregas`), `unidades`/`rubricas`/`examenes_materia`/`cierre_cursada_runs`/`avance_snapshots` (JOIN `materias`). Verificación: `COUNT(*) WHERE universidad_id IS NULL == 0` en cada tabla. Downgrade: no-op o set NULL.
6. **R6 — backfill de membresías (data migration).** Por cada usuario, 1 fila en `usuario_universidad` con `universidad_id=<id_tupad>`, `rol`/`moodle_username`/`moodle_password_encrypted` copiados tal cual del usuario (password ya cifrado, NO re-cifrar), `activo=true`. Idempotente respecto al unique. Downgrade: delete de las membresías de TUPaD.
7. **R7 — NOT NULL + constraint de código (structural, post-backfill).** `ALTER universidad_id ... SET NOT NULL` en las 9 tablas (falla en seco si quedó algún NULL — es la red de seguridad). Drop del unique global de `materias.codigo` + create `UniqueConstraint(universidad_id, codigo)`. Downgrade: revertir a nullable y restaurar el unique global.

**Pasos operativos manuales (NO en la migración, documentados en tasks):**

- **OP-1:** confirmar en producción el `moodle_host` real y aplicarlo a TUPaD (o setearlo a mano post-deploy).
- **OP-2:** decidir a mano qué ADMIN(s) reciben `es_superadmin=true` y aplicarlo con un UPDATE puntual. El backfill deja a todos en `false`.

**Rollback:** cada revisión estructural (R1, R2, R3, R7) es reversible por su `downgrade`. Las de datos (R4–R6) se revierten borrando lo insertado. Recomendado probar `upgrade`/`downgrade` en la DB de dev (Docker `docker-compose.local.yml`) sobre una copia con datos antes de tocar producción.

## Risks / Trade-offs

- **[Denormalización → riesgo de incoherencia futura]** → un `universidad_id` que no coincida con el del padre corrompería el aislamiento. Mitigación: el backfill lo deja 100% coherente por construcción; la validación en servicio al crear/mover se implementa en Fase 4 (fuera de este change). En Fase 0 solo existe el riesgo si alguien inserta a mano.
- **[`ALTER SET NOT NULL` falla si el backfill dejó NULLs]** → detiene la migración a mitad. Mitigación: es intencional (red de seguridad); correr las verificaciones `COUNT NULL == 0` al final de R5/R6 antes de R7.
- **[Nombre real del unique de `materias.codigo` desconocido]** → el `drop_constraint` puede fallar si el nombre no matchea. Mitigación: inspeccionar la base (`\d materias`) y/o el estado de Alembic antes de escribir R7; usar el nombre exacto.
- **[Reuso del tipo enum `rol_enum`]** → recrearlo en R2 daría "type already exists". Mitigación: `create_type=False` en `usuario_universidad.rol` (patrón ya usado en el repo).
- **[Change de unicidad marcado BREAKING]** → a nivel schema cambia el contrato de `codigo`. Con una sola universidad no rompe datos, pero cualquier código que asuma `codigo` único global deberá revisarse en fases posteriores. En Fase 0 no hay consumidores nuevos.
- **[Convivencia de campos duplicados]** → durante fases 0–5 conviven `usuarios.rol` (viejo) y `usuario_universidad.rol` (nuevo); pueden divergir si algo escribe uno y no el otro. Mitigación: en Fase 0 la fuente de verdad sigue siendo la vieja (nadie lee la nueva aún); el corte se hace en Fase 2.

## Open Questions

1. **Tablas hijas (D2):** ¿alguna de `entregas_historial`, `correccion_historial`, `componentes_unidad`, `cierre_cursada_alumnos`, `avance_alumnos` necesita `universidad_id` propio para reporting directo, o alcanza con scopearlas vía su padre? (Propuesta: vía el padre; validar con quien conozca los reportes.)
2. **`moodle_host` de seed (OP-1):** ¿el valor es idéntico para todos los usuarios en producción? Si hay variantes, ¿cuál es el canónico de TUPaD?
3. **`es_superadmin` (OP-2):** ¿qué ADMIN(s) concretos se promueven a superadmin? Decisión de negocio, no se asume "todos los ADMIN".
4. **¿Una sola revisión de datos o varias?** El plan propone R4/R5/R6 separadas por claridad; podrían fusionarse. Se deja a criterio de quien implemente en apply.
