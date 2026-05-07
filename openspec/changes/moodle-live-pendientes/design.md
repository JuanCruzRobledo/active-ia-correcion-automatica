## Context

Active-IA ya tiene un mecanismo de cifrado AES-256 para API keys de Gemini (`app/core/security.py`). El patrón de almacenamiento de credenciales de terceros está establecido: se cifran en DB y se descifran en memoria solo cuando se necesitan. La capa de servicios ya sigue Clean Architecture (Router → Service → Repository → DB), por lo que la integración con Moodle debe seguir el mismo patrón.

Moodle expone una API REST bajo `/webservice/rest/server.php` una vez obtenido el token vía `/login/token.php`. Las funciones relevantes son `mod_assign_get_submissions` y `core_enrol_get_enrolled_users_with_capability`. El token es stateless y válido por sesión; conviene cachearlo en memoria por un tiempo acotado.

## Goals / Non-Goals

**Goals:**
- Almacenar credenciales Moodle cifradas por tutor (usuario, password, moodle_host)
- Endpoint `GET /api/pendientes/moodle` que devuelve submissions pendientes agrupadas por Materia → Unidad → Comisión
- Página `/pendientes` en el frontend con accordeón, stat cards, filtros y deep links al grader de Moodle
- Banner de alerta en el Dashboard del tutor cuando hay entregas pendientes
- Item "Pendientes" en el Sidebar
- Agrupación por Materia como nivel superior (no estaba en el diseño original)

**Non-Goals:**
- Sincronización automática en background (cron jobs, webhooks de Moodle)
- Soporte multi-instancia Moodle por usuario (un tutor → un host Moodle)
- Descarga automática de archivos desde Moodle
- Corrección automática sin intervención del tutor
- Modificación de notas en Moodle desde Active-IA

## Decisions

### D1: Credenciales Moodle como campos en `Usuario`, no tabla separada

**Decisión:** Agregar `moodle_username`, `moodle_password_encrypted` y `moodle_host` directamente al modelo `Usuario`.

**Alternativa considerada:** Tabla `MoodleCredencial` con FK a `Usuario` (1:1).

**Rationale:** El patrón existente para `gemini_api_key_encrypted` está en `Usuario`. Mantener consistencia evita una JOIN innecesaria y simplifica el modelo. Si en el futuro se necesitan múltiples credenciales Moodle por usuario, se puede migrar.

---

### D2: Token Moodle cacheado en memoria con TTL

**Decisión:** El `MoodleService` obtiene un token de Moodle y lo cachea en un dict `{user_id: (token, expires_at)}` en memoria del proceso. TTL: 50 minutos (los tokens de Moodle duran ~1 hora).

**Alternativa considerada:** Re-autenticar en cada request.

**Rationale:** Las llamadas al endpoint `/api/pendientes/moodle` pueden generar múltiples requests al webservice (una por asignación × comisión). Re-autenticar en cada llamada sería innecesariamente lento y podría hacer rate-limiting en Moodle.

**Riesgo:** El cache se pierde si el proceso se reinicia. Aceptable — el tutor simplemente verá una re-autenticación transparente.

---

### D3: Agrupación por Materia en el response del backend

**Decisión:** El endpoint `GET /api/pendientes/moodle` devuelve una estructura `MateriasPendientes` con array de materias, cada una con sus unidades y comisiones.

```
MateriasPendientesResponse
└── materias: List[MateriaPendiente]
    ├── id, nombre
    ├── totalEspera, totalCorregidos, totalSinEntrega
    └── unidades: List[UnidadPendiente]
        ├── id, titulo, subtitulo, cmid
        └── comisiones: List[ComisionPendiente]
            ├── id, nombre, codigo, groupId
            ├── espera, corregidos, sinEntrega
```

**Rationale:** El diseño original solo agrupaba por unidad. La propuesta agrega materia como nivel superior. Devolver la jerarquía completa desde el backend hace el frontend stateless respecto a la agrupación.

---

### D4: Consultas Moodle en paralelo con `asyncio.gather`

**Decisión:** Para cada asignación (unidad), se disparan en paralelo las llamadas a `mod_assign_get_submissions` para cada grupo (comisión) usando `asyncio.gather`.

**Alternativa considerada:** Llamadas secuenciales.

**Rationale:** Un tutor puede tener 10+ unidades × 3+ comisiones = 30+ requests a Moodle. La serialización haría el endpoint demasiado lento (>10s). Con `httpx.AsyncClient` y `asyncio.gather` se pueden paralelizar fácilmente.

---

### D5: Frontend — estado de acordeón controlado localmente, expanded-all por defecto

**Decisión:** `MateriaBlock` y `UnidadBlock` mantienen estado `open` local con `useState(true)` (expandido por defecto). El filtro "Solo con pendientes" se maneja con estado en `PendientesPage`.

**Rationale:** El design handoff especifica estado inicial expandido y filtrado local (no requiere re-fetch). Consistente con el patrón existente en el codebase.

---

### D6: Estructura de archivos — feature module independiente

**Decisión:** Todo el código de pendientes vive en `src/features/pendientes/`. El hook `usePendientesMoodle` hace refetch cada 5 minutos (`staleTime: 5 * 60 * 1000`).

**Rationale:** Sigue el patrón feature-based establecido en el proyecto. El `staleTime` de 5 min es el especificado en el design handoff.

## Risks / Trade-offs

**[Rate limiting de Moodle]** → Mitigation: cachear el token (D2), paralelizar pero no superar ~10 requests simultáneos por llamada (semaphore en `asyncio.gather`).

**[Credenciales Moodle incorrectas / tutor sin configurar]** → Mitigation: el endpoint devuelve 424 (Failed Dependency) con mensaje claro "Configurá tus credenciales Moodle en tu perfil". El frontend muestra un estado vacío con CTA al perfil.

**[Moodle offline o cambia la API]** → Mitigation: el endpoint captura excepciones de httpx y devuelve 502 con mensaje descriptivo. El frontend muestra estado de error sin romper el resto del dashboard.

**[Cifrado de password en DB]** → La misma llave AES-256 de `ENCRYPTION_KEY` que protege las Gemini API keys. Si esa llave se compromete, se comprometen ambas. Mitigación: documentar en `.env.example` la importancia de rotar la key.

**[Agrupación por materia requiere mapeo Moodle → Active-IA]** → El webservice de Moodle no devuelve una "materia" explícita. El tutor deberá tener sus cursos Moodle vinculados a sus Materias en Active-IA, o se puede usar el nombre del curso Moodle directamente como agrupador. **Decisión pendiente:** ¿usar el nombre del curso Moodle como materia, o vincular manualmente? Por ahora: usar el nombre del curso Moodle como materia (más simple, sin configuración extra).

## Migration Plan

1. Generar migración Alembic: `alembic revision --autogenerate -m "add moodle credentials to usuario"`
2. La migración agrega columnas nullable — no requiere backfill.
3. Deploy normal — no hay breaking changes en endpoints existentes.
4. Rollback: `alembic downgrade -1` elimina las columnas.

## Open Questions

*(Resueltas)*

---

### D7: IDs de Moodle configurados por admin en los modelos existentes — no descubierta automáticamente

**Decisión:** Los IDs de Moodle se configuran manualmente por un ADMIN al crear/editar los registros en Active-IA:

| Modelo | Campo nuevo | Descripción | Ejemplo |
|---|---|---|---|
| `Materia` | `moodle_course_id` | ID del curso en Moodle | `123` |
| `Rubrica` | `moodle_assign_id` | `cmid` de la asignación en Moodle | `11237` |
| `Comision` | `moodle_group_id` | ID del grupo en Moodle | `4165` |
| `Comision` | `moodle_group_code` | Código del grupo (groupsearchvalue) | `"m26"` |

**Rationale:** Los tutores ya tienen Materias y Comisiones asignadas en Active-IA. Al agregar los IDs de Moodle en esos modelos, el sistema puede construir automáticamente el deep link al grader:
```
https://tup.sied.utn.edu.ar/mod/assign/view.php
  ?id={rubrica.moodle_assign_id}
  &action=grading
  &status=requiregrading
  &groupsearchvalue={comision.moodle_group_code}
  &group={comision.moodle_group_id}
```

**Ejemplo concreto:** Rúbrica "TP Integrador: Repetitivas" tiene `moodle_assign_id=11237`, Comisión 2 tiene `moodle_group_id=4165` y `moodle_group_code="m26"` → URL completa funcional.

**Alternativa descartada:** Descubrir los IDs automáticamente via `core_course_get_contents` — requeriría lógica de matching por nombre (frágil) y configuración por parte del tutor igualmente.

**Implicación:** El endpoint `GET /api/pendientes/moodle` filtra solo las Rubricas y Comisiones que tienen los IDs de Moodle configurados (`moodle_assign_id IS NOT NULL`). Las que no tienen ID configurado se ignoran silenciosamente.
