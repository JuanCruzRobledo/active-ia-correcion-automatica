## Context

Fase 4 de 7 del feature multi-tenant. La estructura ya está (Fases 0-3):

- **Fase 0**: `universidad_id` existe como columna en las 9 entidades del core: `materias`, `comisiones`, `entregas`, `correcciones`, `unidades`, `rubricas`, `examenes_materia`, `cierre_cursada_runs`, `avance_snapshots`. HOY es **nullable** (`Mapped[int | None]`) por el backfill histórico; el plan la lleva a NOT NULL en una fase posterior. También `notificaciones` tiene `universidad_id` (bonus, no es una de las 9 del core).
- **Fase 1**: `get_universidad_activa` → `ContextoUniversidad(universidad_id: int | None, rol: RolEnum | None, es_superadmin: bool)`. Superadmin sin universidad elegida ⇒ `universidad_id=None`. Superadmin con universidad elegida ⇒ `universidad_id` seteado + `rol=ADMIN` sintético + `es_superadmin=True`. Miembro normal ⇒ `universidad_id` + `rol` de la membresía.
- **Fase 2**: `permissions.py` refactorizado. Helper `_acceso_total(ctx) = ctx.es_superadmin or ctx.rol == ADMIN`. Los `verificar_acceso_*` reciben `ctx`. **OQ3 (check de pertenencia por universidad) se DIFIRIÓ explícitamente a esta fase** — Fase 2 NO agregó ninguna comparación de `universidad_id`.
- **Fase 3**: guard defensivo en `permissions.py` — `verificar_materia_universidad_activa(materia, universidad_id_activa)` lanza **409** si `materia.universidad_id` difiere de la activa (red de seguridad LOCAL para sync Moodle cross-campus), y `materia_pertenece_a_universidad_activa(...) -> bool` (versión sin excepción para filtrar lotes). Ambos tratan `universidad_id IS NULL` como "no es mismatch" (permisivo, para no romper datos legados sin migrar).

**Estado actual del problema**: ningún repository filtra por `universidad_id`. Ejemplo real — `entrega_repository.get_all` ya tiene el patrón exacto que necesitamos, pero para pertenencia (`comisiones_visibles: list[int] | None`), no para universidad. `materia_repository.get_all` toma filtros keyword-only y arma condiciones. El patrón de scoping calca esto.

**Restricciones**: Clean Architecture (ARCH-001: el `WHERE` va en el repository, NUNCA SQLAlchemy en el service). Máx 500 LOC/archivo. Soft delete se respeta: el filtro de universidad se SUMA al de `deleted_at`/`activa`, no lo reemplaza. Dominio de seguridad ⇒ governance HIGH, TDD estricto con red de caracterización antes de tocar.

## Goals / Non-Goals

**Goals:**
- Toda query de listado/búsqueda/conteo/agregación de las 9 entidades scopeadas filtra por la universidad activa.
- Todo acceso por id valida pertenencia a la universidad activa; recurso de otra universidad ⇒ **404**.
- Patrón de propagación `ctx.universidad_id` → service → repository, mínimo, consistente, keyword-only.
- Bypass de superadmin sin universidad activa (ve todo).
- Cerrar la deuda de `comisiones.py` (3 endpoints con `current_user.rol` inline).
- Tests de aislamiento con 2 universidades que prueban el invariante.

**Non-Goals:**
- Frontend / selector de workspace (Fase 5).
- Eliminar `usuarios.rol` / `usuarios.moodle_*` (Fase 6).
- Volver `universidad_id` NOT NULL o cualquier migración Alembic (fase posterior; ver OQ4).
- Re-hacer auth (Fase 1) ni la resolución de credenciales Moodle (Fase 3).
- Tocar el guard 409 de Fase 3 (sigue vivo para sync Moodle).

## Decisions

### D1 — El filtro `WHERE universidad_id = :activa` vive en el repository (ARCH-001)

Cada método de repositorio que lista/busca/cuenta una entidad scopeada suma un parámetro **keyword-only** `universidad_id: int | None = None`. Si `is not None` ⇒ agrega la condición al query (a la MISMA lista de `conditions` que comparten datos y count, para que el total paginado tampoco revele el global). Si `is None` ⇒ NO filtra (bypass superadmin).

```python
# Patrón (calcado de comisiones_visibles en entrega_repository.get_all):
if universidad_id is not None:
    conditions.append(Entrega.universidad_id == universidad_id)
```

**Alternativa descartada**: filtrar en el service iterando resultados en Python — viola ARCH-001 y rompe la paginación/count (el total quedaría inflado con filas de otras universidades). Descartada.

**Alternativa descartada**: un `global` SQLAlchemy event / session-level filter (row-level security emulada). Menos explícito, difícil de testear por método, y choca con el bypass del superadmin. Descartada a favor del parámetro explícito.

### D2 — Inventario de métodos a scopear (mapa real, grep de `app/repositories/`)

Entidad ⇒ repository ⇒ métodos que HOY no filtran por universidad y deben recibir `universidad_id`:

| Entidad | Repository | Métodos a scopear |
|---|---|---|
| Materia | `materia_repository.py` | `get_all`, `get_by_codigo`, `get_con_moodle`, `get_by_cuatrimestre`, `get_by_cuatrimestres`, `get_configuradas_dashboard`, `get_by_coordinador`, `contar_por_materias` |
| Comisión | `comision_repository.py` | `get_all`, `contar_tutores_entregas`, `contar_comisiones_activas_por_materia`, `get_by_materia`, `get_by_materia_con_tutores`, `get_by_tutor`, `get_moodle_habilitadas_de_tutor`, `get_by_materia_nombre_anio` |
| Entrega | `entrega_repository.py` | `get_all`, `get_all_for_export`, `get_by_rubrica_alumno`, `get_subidas_ids_by_tutor`, `contar_errores_by_tutor`, `contar_estados_by_tutor` |
| Corrección | `correccion_repository.py` | `get_all`, `get_all_for_export`, `get_statistics_by_rubrica`, `get_pendientes_subida_moodle`, `contar_no_vinculadas_moodle`, `get_by_entrega_ids_corregidas` |
| Unidad | `unidad_repository.py` | `get_by_materia` |
| Rúbrica | `rubrica_repository.py` | `get_all`, `get_by_materia`, `get_by_materia_tipo_numero`, `get_moodle_habilitadas_por_materias` |
| Examen | `examen_repository.py` | `get_by_materia` |
| CierreCursadaRun | `cierre_cursada_repository.py` | `listar_runs` |
| AvanceSnapshot | `avance_repository.py` | `get_ultimo_snapshot`, `get_ultimos_snapshots`, `contar_por_estado` |
| Dashboard (agregación) | `dashboard_repository.py` | `get_admin_counts`, `contar_comisiones_activas_en_materias`, `contar_rubricas_activas_en_materias`, `contar_pendientes_en_materias`, `get_progreso_por_comision_de_materias`, `contar_pendientes_en_comisiones`, `contar_corregidas_en_comisiones`, `get_detalle_comisiones` |

**Métodos `get_by_id*`** (acceso por id): NO reciben `universidad_id` como filtro del `WHERE` — se resuelven con el check de pertenencia de D3 (traen el recurso y comparan). Así el 404 se distingue de "no existe en ninguna universidad" de forma uniforme.

**Métodos que reciben `materia_id`/`comision_id` ya scopeados aguas arriba** (ej. `get_by_materia`): igual reciben `universidad_id` y filtran, como defensa en profundidad — si el `materia_id` fuera de otra universidad, el resultado es vacío en lugar de fugarse. El id padre ya debería haber pasado el check de pertenencia D3 en el router, pero el doble filtro es barato y cierra la ventana.

Este inventario es la base de la checklist de `tasks.md`; durante el apply se confirma método por método con la red de caracterización (algún método puede resultar ya inalcanzable o cubierto por otro filtro — se documenta, no se fuerza).

### D3 — Check de pertenencia al acceder por id ⇒ 404

Se generaliza el guard de Fase 3 a una función de acceso general por id con semántica **404** (no 409, no 403):

```python
def verificar_pertenencia_universidad(recurso, ctx) -> None:
    # superadmin sin universidad activa (ctx.universidad_id is None) ⇒ bypass total
    # recurso None ⇒ 404 (no existe)
    # recurso.universidad_id != ctx.universidad_id ⇒ 404 (no revelar cross-tenant)
```

- **404 sobre 403** (Open Question #1, recomendado): un 403 revelaría que el recurso EXISTE en otra universidad. Con 404 el recurso de otra universidad es indistinguible de uno inexistente. Coherente con la política ya adoptada en `filtrar_entregas_accesibles` ("no convertir el endpoint en un oráculo de enumeración de IDs").
- **No se toca el guard 409 de Fase 3** (`verificar_materia_universidad_activa`): sirve a otro caso (sync Moodle cross-campus, donde 409 Conflict es la semántica correcta porque el recurso SÍ es tuyo pero de otro campus). Coexisten: 409 para el flujo Moodle, 404 para el acceso general por id.
- El check corre en el router/service DESPUÉS de traer el recurso por id (o dentro del `get_..._or_404` del service), antes de devolverlo o de aplicar mutaciones.
- Se respeta el bypass: `ctx.universidad_id is None` (superadmin sin universidad) ⇒ pasa siempre.

### D4 — Propagación `ctx.universidad_id` → service → repository (patrón mínimo)

Cadena: el router ya monta `ctx: ContextoUniversidad = Depends(get_universidad_activa)`. Pasa `ctx.universidad_id` al método del service. El service lo reenvía como keyword `universidad_id=` al repository. Un solo valor viaja (no el `ctx` entero: los repositories no deben conocer `ContextoUniversidad`, solo el int nullable — mantiene el repository ignorante de la capa de auth).

- Los métodos de service ganan un parámetro `universidad_id: int | None`. Firma keyword-only donde el service ya usa keyword-only.
- Donde un router hoy NO monta `ctx` (algunos GET), se agrega `ctx = Depends(get_universidad_activa)` — igual que hizo Fase 2 en sus 18 puntos.
- **Regla de consistencia**: `None` significa SIEMPRE "sin filtro / ver todo" (bypass superadmin), nunca "error" ni "universidad 0". Un miembro normal SIEMPRE trae `ctx.universidad_id` seteado (Fase 1 lo garantiza), así que para ellos el filtro siempre aplica.

### D5 — Comportamiento del superadmin (Open Question #2)

- `ctx.universidad_id is None` (superadmin que NO eligió universidad) ⇒ los repositories reciben `universidad_id=None` ⇒ sin filtro ⇒ ve TODAS las universidades. Dashboards agregados suman todo.
- `ctx.universidad_id` seteado (superadmin que SÍ eligió una universidad en el selector) ⇒ se comporta como un miembro de esa universidad: filtra a esa universidad. **Recomendación**: respetar la universidad elegida (filtrar a esa), porque es lo que el selector de workspace comunica ("estoy trabajando en UniX"); si quiere ver todo, deselecciona. Esto mantiene una sola regla ("si hay `universidad_id`, filtro por él; si no, no filtro") sin ramas especiales de superadmin en cada repository. El bypass del superadmin ya vive en el nivel de `ctx` (Fase 1 decide si `universidad_id` es None), no en cada query.

### D6 — Cierre de la deuda `comisiones.py` (arrastrada de Fase 2)

Tres endpoints leen `current_user.rol` INLINE (rol global viejo) en vez de vía `ctx`:

- `listar_comisiones` (líneas ~65-66): `tutor_id = current_user.id if current_user.rol == RolEnum.TUTOR ...` / `coordinador_id = ... COORDINADOR`. Migrar a `ctx.rol`; montar `ctx = Depends(get_universidad_activa)`; pasar `ctx.universidad_id` al `service.listar_comisiones` → repo `get_all`. Contemplar bypass superadmin (`_acceso_total(ctx)` ⇒ sin filtro de tutor/coordinador).
- `obtener_comision` (línea ~133): `if current_user.rol == RolEnum.TUTOR`. Reemplazar el chequeo inline por el guard de pertenencia adecuado (`verificar_acceso_comision_o_materia` o el que corresponda) + check de pertenencia por universidad (D3, 404 si la comisión es de otra universidad).
- `actualizar_moodle_comision` (líneas ~161-171): `if current_user.rol == RolEnum.TUTOR ... elif current_user.rol != RolEnum.ADMIN`. Migrar a `ctx` (`_acceso_total` / guard de pertenencia) + scoping por universidad.

Se cierra como task explícita. Nota: `crear_comision`, `actualizar_comision`, `eliminar_comision`, `restaurar_comision`, `asignar_tutores` YA usan `ctx` (Fase 2) — solo hay que sumarles el scoping por universidad donde apliquen (creación: heredar `universidad_id` de la materia, ya cubierto en Fase 0/servicios).

### D7 — Manejo de `universidad_id IS NULL` (defensa del invariante — Open Question #4)

La columna es nullable hoy. Fase 0 backfilleó todo a TUPaD, así que en producción no debería haber NULLs en las 9 entidades. Dos opciones para el filtro:

- **(A) Estricto**: `WHERE universidad_id = :activa`. Una fila con NULL NO aparece para nadie con universidad activa. Máximo aislamiento; pero si quedara un NULL por un bug de backfill, desaparece de las listas (falso negativo silencioso).
- **(B) Permisivo**: `WHERE (universidad_id = :activa OR universidad_id IS NULL)`. Filas NULL visibles para todos. Coherente con el guard de Fase 3 (trata NULL como "no mismatch"), preserva el invariante mono-tenant aun si el backfill dejó huecos; pero debilita el aislamiento (una fila NULL se fuga cross-tenant).

**Recomendación**: **(A) estricto**, PORQUE (1) Fase 0 garantiza el backfill y esta fase es justamente la que cierra el aislamiento — un NULL colado es un bug a detectar, no a ocultar; (2) para blindarlo, agregar un test que afirme "cero filas con `universidad_id IS NULL` en las 9 tablas tras Fase 0" como precondición del apply. Si el equipo prefiere no arriesgar un falso negativo antes de que la columna sea NOT NULL, (B) es el fallback conservador. **Decisión a confirmar en el checkpoint humano.**

## Risks / Trade-offs

- **[Una query olvidada = fuga cross-tenant]** → El inventario D2 es exhaustivo por grep, pero puede haber queries armadas ad-hoc en services. Mitigación: los tests de aislamiento con 2 universidades recorren cada endpoint público de las 9 entidades; un endpoint sin scopear se cae con el test (UniA ve datos de UniB). El test es el gate, no el grep.
- **[Falso negativo por `universidad_id` nullable]** (D7) → Test de precondición "cero NULLs" + recomendación estricta.
- **[Bypass del superadmin roto por MagicMock permisivo en tests]** → Gotcha ya documentado en Fase 2: fijar `es_superadmin` y `universidad_id` explícitos en los fixtures (`ContextoUniversidad` real, no `MagicMock`).
- **[Count/paginación revelando totales globales]** → El filtro va a la lista `conditions` compartida datos+count (D1), nunca solo al query de datos. Verificado como patrón en `entrega_repository`.
- **[Regresión en estado mono-tenant]** → Red de caracterización antes de tocar (baseline de tests verdes), invariante "mismo comportamiento con 1 universidad". Igual protocolo que Fase 2.
- **[Blast radius grande, muchos métodos]** → Ir repository por repository, con TDD; cada entidad es una task independiente con su test de aislamiento.
- **[`comisiones.py` cambia auth inline]** → Dominio auth (CRÍTICO); red de caracterización de los 3 endpoints antes de migrarlos.

## Migration Plan

Sin migración de datos ni Alembic en esta fase (D3/Non-Goals). Plan de despliegue = orden de implementación con checkpoints:

1. Introducir el check de pertenencia por id (D3) en `permissions.py` con tests unitarios (404 + bypass superadmin).
2. Repository por repository (D2), con TDD: red de caracterización → sumar `universidad_id` param → aplicar filtro → test de aislamiento de esa entidad.
3. Propagar en services y routers (D4).
4. Cerrar la deuda `comisiones.py` (D6) como task dedicada.
5. Dashboard/agregaciones scopeadas (D2 fila Dashboard) con su test.
6. Suite de aislamiento 2-universidades completa (gate final).
7. **Rollback**: como el filtro solo se ACTIVA cuando `universidad_id is not None` y hoy hay una sola universidad con todo backfilleado a TUPaD, el comportamiento observable es idéntico al actual; revertir el change no deja datos inconsistentes. Rollback = revert del PR.

## Open Questions

**Todas las Open Questions fueron RESUELTAS por el dueño del producto antes del apply (checkpoint humano). Decisiones finales, vinculantes para la implementación:**

1. **RESUELTO — Check de pertenencia: 404** (no 403) al acceder a un recurso de otra universidad. No revela existencia cross-tenant; coherente con `filtrar_entregas_accesibles`. Implementado en `verificar_pertenencia_universidad` (D3).
2. **RESUELTO — Superadmin con `universidad_activa_id` elegida: filtra a esa universidad.** Regla única: si `ctx.universidad_id is not None` ⇒ se filtra por ella (superadmin incluido, sin ramas especiales por repository). El superadmin ve TODO solo cuando `ctx.universidad_id is None`.
3. **RESUELTO — Dashboard/agregaciones: scopeadas** a la universidad activa. Excepción única: superadmin sin universidad activa ⇒ agregación global. No se detectó ninguna métrica que deba ser global cross-universidad.
4. **RESUELTO — `universidad_id IS NULL`: filtro ESTRICTO (A)**, `WHERE universidad_id = :activa` (NUNCA `OR IS NULL`). Blindado con: (a) test que verifica CERO filas con `universidad_id` NULL en las 9 tablas scopeadas, y (b) el modelo SQLAlchemy alineado a `Mapped[int]` (no `Mapped[int | None]`) en las 9 tablas — cierra la divergencia modelo/DB que permitía NULLs en el motor de test (SQLite in-memory generado desde `Base.metadata`). Verificado contra el Postgres real: las 9 columnas YA eran `NOT NULL` (migración R7 de Fase 0) con cero filas NULL — no hizo falta una migración Alembic nueva, solo el ajuste del type hint del modelo.
5. **RESUELTO — Queries ad-hoc: barridas durante el apply** (grupo de tasks §10). Ver reporte de apply para el detalle de lo encontrado y scopeado.

**Hallazgo adicional del apply (no una Open Question original, pero directamente causado por resolver OQ4):** alinear el modelo a `Mapped[int]` NOT NULL expuso que NINGÚN service de creación (`materia_service`, `comision_service`, `entrega_service`, `correccion_service`, `unidad_service`/`unidad_repository.sincronizar`, `rubrica_service`, `examen_service`, `cierre_cursada_service`, `snapshot_service`) seteaba `universidad_id` al construir una fila nueva — un gap real que en Postgres (donde la columna YA era NOT NULL desde R7) hubiera hecho fallar con `IntegrityError` cualquier alta nueva de estas 9 entidades. Se cerró en el apply: cada creación PROPAGA `universidad_id` desde el padre ya cargado en el propio método (materia/comisión/entrega), calcando el comentario "denormalizada, propagada desde X.universidad_id" que ya documentaba cada modelo. `Materia` (raíz del árbol, sin padre) lo recibe de `ctx.universidad_id` vía el router, con 400 si un superadmin sin universidad activa intenta crear una materia "flotante".
