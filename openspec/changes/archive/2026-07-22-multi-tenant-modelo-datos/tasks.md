## 1. Modelos nuevos

- [x] 1.1 Crear `app/models/universidad.py` con el modelo `Universidad` (`TimestampMixin`): `id`, `nombre` (String, unique, NOT NULL), `moodle_host` (String(255), nullable), `activa` (Boolean, NOT NULL, default True, server_default `true`).
- [x] 1.2 Crear `app/models/usuario_universidad.py` con el modelo `UsuarioUniversidad` (patrón `ComisionTutor`): `id`, `usuario_id` FK→`usuarios.id` NOT NULL, `universidad_id` FK→`universidades.id` NOT NULL, `rol` (`RolEnum`, `create_type=False` para reusar `rol_enum`), `moodle_username` (String(100), nullable), `moodle_password_encrypted` (Text, nullable), `activo` (Boolean, NOT NULL, default True), `UniqueConstraint(usuario_id, universidad_id)`.
- [x] 1.3 Definir relationships: `Universidad`↔`UsuarioUniversidad`, `Usuario`↔`UsuarioUniversidad`, `Usuario`↔`Universidad` (según convenga), sin romper las relationships existentes. (Nota: `lazy="raise"` en ambas direcciones — PERF-001 — nada las lee todavía en Fase 0; ver desvío en el resumen de apply.)
- [x] 1.4 Registrar `Universidad` y `UsuarioUniversidad` en `app/models/__init__.py` (imports + `__all__`).

## 2. Cambios en modelos existentes (aditivos, sin quitar nada)

- [x] 2.1 `app/models/usuario.py`: agregar `es_superadmin` (Boolean, NOT NULL, default False, `server_default=text("false")`) y la relationship a `UsuarioUniversidad`. NO tocar `rol`/`moodle_username`/`moodle_password_encrypted`/`moodle_host`.
- [x] 2.2 `app/models/materia.py`: agregar `universidad_id` (FK→`universidades.id`). Cambiar el `unique=True` de `codigo` por `UniqueConstraint(universidad_id, codigo)` en `__table_args__`.
- [x] 2.3 `app/models/comision.py` (`Comision`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.4 `app/models/entrega.py` (`Entrega`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.5 `app/models/correccion.py` (`Correccion`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.6 `app/models/unidad.py` (`Unidad`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.7 `app/models/rubrica.py` (`Rubrica`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.8 `app/models/examen_materia.py` (`ExamenMateria`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.9 `app/models/cierre_cursada.py` (`CierreCursadaRun`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.10 `app/models/avance.py` (`AvanceSnapshot`): agregar `universidad_id` (FK→`universidades.id`).
- [x] 2.11 Definir todas las columnas `universidad_id` como **nullable** en el modelo por ahora (se endurecen a NOT NULL vía migración R7); documentar en el código el porqué (backfill).

## 3. Migración R1 — crear `universidades`

- [x] 3.1 `alembic revision -m "crear tabla universidades"` (o autogenerate) con `create_table` de `universidades` (columnas de 1.1) + `downgrade` con `drop_table`. (Revision `f584cac9a6f7`.)
- [x] 3.2 Verificar que el unique de `nombre` se genere con la convención de nombres del proyecto (`uq_universidades_nombre`).

## 4. Migración R2 — crear `usuario_universidad`

- [x] 4.1 Revisión que crea `usuario_universidad` con FKs, `UniqueConstraint(usuario_id, universidad_id)` y `rol` referenciando `rol_enum` con `create_type=False` (NO recrear el tipo enum). `downgrade` con `drop_table`. (Revision `b7cd41aa7f5e`.)

## 5. Migración R3 — columnas nullable + `es_superadmin`

- [x] 5.1 Revisión que hace `add_column universidad_id` (Integer, nullable, FK→`universidades.id`) en `materias`, `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots`.
- [x] 5.2 En la misma revisión, `add_column usuarios.es_superadmin` (Boolean, NOT NULL, server_default `false`).
- [x] 5.3 `downgrade` que elimina las 9 columnas `universidad_id` y `usuarios.es_superadmin`. (Revision `58da24620545`.)

## 6. Migración R4 — seed TUPaD (data migration)

- [x] 6.1 Revisión de datos que inserta la universidad `nombre="Tecnicatura Universitaria en Programación a Distancia"`, `activa=true`, **solo si no existe** (SELECT por nombre antes de insertar). (Revision `ab77a72ed25f`.)
- [x] 6.2 [MANUAL/OPERATIVO — OP-1] Definir el `moodle_host` de seed a partir del valor real de `usuarios.moodle_host` en producción; NO inventar. Alternativa: dejar `moodle_host` NULL y setearlo con un UPDATE manual post-deploy. Documentar la decisión en el mensaje de la revisión. (La migración deriva el valor automáticamente SOLO si es consistente entre todos los usuarios; en dev quedó NULL — ver resumen de apply. Confirmar contra producción real sigue siendo el paso operativo pendiente.)

## 7. Migración R5 — backfill de `universidad_id` en cascada (data migration)

- [x] 7.1 `UPDATE materias SET universidad_id = <id_tupad>`.
- [x] 7.2 Backfill `comisiones` propagando por `materia_id` → `materias.universidad_id`.
- [x] 7.3 Backfill `entregas` propagando por `comision_id` → `comisiones.universidad_id`.
- [x] 7.4 Backfill `correcciones` propagando por `entrega_id` → `entregas.universidad_id`.
- [x] 7.5 Backfill `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots` propagando por `materia_id` → `materias.universidad_id`.
- [x] 7.6 Verificar `COUNT(*) WHERE universidad_id IS NULL == 0` en las 9 tablas antes de continuar (assert en la migración o check manual documentado). (Revision `e2d06591ae29`, con `RuntimeError` si queda algún NULL.)

## 8. Migración R6 — backfill de membresías (data migration)

- [x] 8.1 Por cada `Usuario`, insertar 1 fila en `usuario_universidad` con `universidad_id=<id_tupad>`, `rol=<usuarios.rol>`, `moodle_username=<usuarios.moodle_username>`, `moodle_password_encrypted=<usuarios.moodle_password_encrypted>` (copiado tal cual, sin descifrar/re-cifrar), `activo=true`.
- [x] 8.2 Hacer el insert idempotente respecto al `UniqueConstraint(usuario_id, universidad_id)` (no duplicar si ya existe).
- [x] 8.3 Verificar que exista exactamente una membresía TUPaD por usuario. (Revision `ea7c83500aac`.)

## 9. Migración R7 — NOT NULL + constraint de código (structural, post-backfill)

- [x] 9.1 `ALTER COLUMN universidad_id ... SET NOT NULL` en las 9 tablas (debe fallar en seco si quedó algún NULL — red de seguridad intencional).
- [x] 9.2 Inspeccionar el nombre real del unique/índice global de `materias.codigo` en la base (`\d materias`) antes de escribir el drop. (Confirmado contra la migración inicial y la DB real de Docker: `uq_materias_codigo` + índice único `ix_materias_codigo`, ambos dropeados.)
- [x] 9.3 Drop del unique global de `materias.codigo` y `create_unique_constraint("uq_materias_universidad_id_codigo", "materias", ["universidad_id", "codigo"])`.
- [x] 9.4 `downgrade` que revierte a nullable las 9 columnas y restaura el unique global de `codigo`. (Revision `103ac75da627`.)

## 10. Pasos operativos manuales (NO automatizar)

- [ ] 10.1 [MANUAL — OP-1] Confirmar en producción el `moodle_host` real de todos los usuarios y aplicarlo a la universidad TUPaD (si no se hizo en 6.2).
- [ ] 10.2 [MANUAL — OP-2] Decidir a mano qué ADMIN(s) reciben `es_superadmin=true` y aplicarlo con un UPDATE puntual. El backfill deja a todos en `false`; NO asumir "todo ADMIN pasa a superadmin".

## 11. Verificación

- [x] 11.1 Correr `alembic upgrade head` sobre la DB de dev (Docker `docker-compose.local.yml`) con datos de prueba; verificar que todas las revisiones aplican en orden. (56 usuarios, 13 materias reales; las 7 revisiones corrieron en orden sin error.)
- [x] 11.2 Correr `alembic downgrade` paso a paso hasta antes de R1 y volver a `head`; verificar reversibilidad de las revisiones estructurales. (`downgrade d6f0e4a2b8c1` completo + `upgrade head` de vuelta; estado final idéntico, seed idempotente confirmado.)
- [x] 11.3 Verificar que el sistema arranca y funciona igual (una sola universidad, campos viejos intactos): `pytest` de la suite existente en verde (sin regresiones). (1300→1335 passed, mismas 1 falla + 3 errores de colección pre-existentes; ORM verificado con queries reales contra la DB migrada.)
- [x] 11.4 Agregar/ajustar tests de modelo para `Universidad` y `UsuarioUniversidad` (unicidad de `nombre`, unique compuesto de membresía, unique `(universidad_id, codigo)` en materias, default de `es_superadmin`). (35 tests nuevos en `backend/tests/unit/models/`.)
- [ ] 11.5 Confirmar con validación humana las Open Questions del `design.md` (tablas hijas sin `universidad_id`, moodle_host de seed, promoción de superadmins) antes de dar la fase por cerrada. **Pendiente — requiere decisión de negocio/producto, no delegable a apply.**
