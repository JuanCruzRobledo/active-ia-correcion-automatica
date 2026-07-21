## Why

Hoy **cualquier usuario autenticado puede leer, corregir, editar y borrar las entregas y correcciones de cualquier comisión del sistema**, incluso de materias que no le corresponden. Los 20 endpoints de `entregas`, `correcciones` y `documentos` están protegidos únicamente por `require_any_authenticated()`, que es literalmente `return user` — no valida nada más allá de que el token sea válido. Un tutor de la comisión A puede pedir `GET /entregas/{id}/contenido` de un alumno de la comisión B y obtener su código fuente completo, o `PUT /correcciones/{id}` y cambiarle la nota.

Esto cierra 4 hallazgos de la auditoría de seguridad (`docs/auditoria/06-seguridad-permisos.md`):

| ID | Severidad | Hallazgo |
|----|-----------|----------|
| **SEC-001** | 🔴 Crítica | IDOR en correcciones (6 endpoints) |
| **SEC-002** | 🔴 Crítica | IDOR en entregas (8 endpoints) |
| **SEC-004** | 🟠 Alta | IDOR en documentos (4 endpoints) |
| **SEC-006** | 🟠 Alta | Guards placeholder que no consultan la DB |

El sistema ya tiene la infraestructura para resolver esto (`verificar_acceso_comision`, `verificar_acceso_materia_de_comision` son guards async reales que sí consultan la DB), pero **ninguno de los tres routers afectados la usa**, y los dos ejes de pertenencia existentes son mutuamente excluyentes: no hay ningún guard que exprese "tutor de la comisión **O** coordinador de la materia **O** admin".

## What Changes

### Nuevos guards de pertenencia (`app/core/permissions.py`)

- **`verificar_acceso_comision_o_materia(db, usuario, comision_id)`** — guard **combinado** (unión de los dos ejes existentes, que hoy solo existen por separado). Matriz de acceso:

  | Rol | Condición |
  |-----|-----------|
  | `ADMIN` | siempre permitido |
  | `TUTOR` | `ComisionTutor(comision_id, tutor_id == user.id)` |
  | `COORDINADOR` | `CoordinadorMateria(materia_id, coordinador_id == user.id)` vía `Comision.materia_id` |
  | `GESTOR` | 403 |
  | cualquier otro | 403 |

- **`verificar_acceso_entrega(db, usuario, entrega_id)`** — resuelve `Entrega.comision_id` y delega en el combinado.
- **`verificar_acceso_correccion(db, usuario, correccion_id)`** — resuelve `Correccion → Entrega → comision_id` y delega en el combinado.
- **Variantes de lote** que resuelven la pertenencia de N IDs en **una sola query** (sin N+1), devolviendo la partición `(permitidos, denegados)`.
- **`comisiones_visibles_para(db, usuario)`** — helper de *scoping* para listados.

### Endpoints protegidos (20)

- `entregas.py` (8/8), `correcciones.py` (6 — los 2 de Moodle ya validan vía `MoodleGradeService` y no se tocan), `documentos.py` (4).
- **`GET /entregas/`** no pasa a 403: pasa a **scoping** — se filtra por join a las comisiones del usuario (patrón `comision_repository.py:118-124`). ADMIN ve todo. Hoy, sin filtros, devuelve **todas las entregas del sistema**.

### **BREAKING** — contrato de respuesta de los 4 endpoints de lote

`PATCH /entregas/archivar`, `DELETE /entregas/masivo`, `POST /correcciones/lote` y `POST /documentos/pdfs-seleccionados` pasan a **filtrar los IDs sin acceso y reportar explícitamente lo omitido**, en lugar de operar sobre todo o fallar entero. La respuesta suma los IDs denegados. En `DELETE /entregas/masivo` el reporte de omitidos debe ser **prominente**, no un campo perdido: borrar es irreversible y el usuario tiene que ver qué NO se borró.

Requiere actualizar el frontend React (`EntregasPage.tsx`, `entregas-service.ts`, `correcciones-service.ts`, tipos y hooks) para mostrar los omitidos.

### Limpieza (SEC-006)

- Se **eliminan** `require_coordinador_of_materia` y `require_tutor_of_comision`: son placeholders sync que no consultan la DB (el chequeo real está comentado como TODO) y son **código muerto** — sus únicas referencias en `app/` son autorreferencias dentro de `permissions.py`. Dejarlos es una trampa: parecen guards de pertenencia y no lo son.

### Tests

Hoy **no existe ningún test de authz** sobre entregas/correcciones/documentos. Se agrega cobertura para los 20 endpoints (tutor ajeno → 403, coordinador de otra materia → 403, admin → 200, tutor propio → 200, GESTOR → 403) más los guards nuevos y el comportamiento de lote parcial.

## Capabilities

### New Capabilities

- `autorizacion-por-pertenencia`: reglas de autorización basadas en la pertenencia real del usuario al recurso (tutor asignado a la comisión, coordinador de la materia, admin), la resolución de la cadena `Correccion → Entrega → Comisión → Materia`, el scoping de listados y la semántica de las operaciones de lote con acceso parcial.

### Modified Capabilities

<!-- Ninguna. Las specs existentes en openspec/specs/ (auth-error-feedback, secret-key-hardening,
     usuarios-eliminacion-segura, etc.) no definen requisitos sobre la autorización de
     entregas/correcciones/documentos, así que no cambia ningún requisito ya especificado. -->

## Impact

**Backend**

- `backend/app/core/permissions.py` — guards nuevos (+ borrado de 2 placeholders muertos)
- `backend/app/routers/entregas.py`, `correcciones.py`, `documentos.py` — 20 endpoints
- `backend/app/services/entrega_service.py`, `correccion_service.py`, `pdf_service.py`, `excel_service.py` — firmas de los métodos de lote y del listado (scoping)
- `backend/app/repositories/entrega_repository.py` — filtro por comisiones visibles
- `backend/app/schemas/entrega.py`, `correccion.py` — campos de "omitidos" en las respuestas de lote

**Frontend**

- `frontend/src/features/entregas/` — `services/entregas-service.ts`, `hooks/useEntregas.ts`, `types/index.ts`, `pages/EntregasPage.tsx`
- `frontend/src/features/correcciones/services/correcciones-service.ts`

**Base de datos**

- Sin migración de esquema. Los `UniqueConstraint` existentes (`uq_comision_tutor` sobre `(comision_id, tutor_id)`, `uq_coordinador_materia` sobre `(coordinador_id, materia_id)`) ya generan índices compuestos que cubren las búsquedas de los guards. Ver `design.md` para el análisis.

**Riesgo operativo**

- Cambio de superficie de permisos: usuarios que hoy ven todo pasarán a ver solo lo suyo. Si hay tutores/coordinadores mal asignados en la DB de producción, **perderán acceso a datos que hoy usan**. Requiere auditar las asignaciones antes de desplegar.
- Gobernanza **CRÍTICA** (dominio Seguridad): la implementación se revisa línea por línea con aprobación humana.
