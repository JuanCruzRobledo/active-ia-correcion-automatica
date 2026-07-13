# Auditoría QA — 🐛 Bugs Funcionales

**Alcance**: revisión de lógica funcional del backend (FastAPI: `app/services`, `app/integrations`, `app/repositories`, `app/routers`, `app/core`) y del frontend (React + TS: hooks de React Query, services y páginas de `features/`). Foco en el flujo de corrección IA (Gemini Studio / OpenRouter), consolidación de entregas, cierre de cursada (`cierre_cursada_calculo` / `examen_mapper`), importación/subida a Moodle, generación de Excel y derivación de estados en el frontend. El código es la fuente de verdad (N8N fue removido; la doc está desactualizada). No se incluyen hallazgos de seguridad/RBAC ni de documentación (los cubren otras dimensiones). Fecha de la corrida: 2026-07-12, branch `main` (commit `17b4061`).

## Índice de hallazgos

| ID | Título | Severidad | Archivo |
|----|--------|-----------|---------|
| BUG-001 | Modelo Gemini inconsistente: config `gemini-3.5-flash` vs validación `gemini-2.5-flash` | 🔴 Crítica | `backend/app/core/config.py` |
| BUG-002 | Re-corrección borra (y comitea) la corrección vieja antes de crear la nueva | 🟠 Alta | `backend/app/services/correccion_service.py` |
| BUG-003 | Cierre de cursada ignora el rescate cuando el parcial es NUMERICO y el recuperatorio no aporta nota numérica | 🟠 Alta | `backend/app/services/cierre_cursada_calculo.py` |
| BUG-004 | Re-entregas: se detectan pero nunca se re-importan, y "Entregar todos" fuerza la nota vieja sobre la entrega nueva | 🟠 Alta | `backend/app/services/moodle_import_service.py` |
| BUG-005 | Prompts de corrección con `{{`/`}}` literales en los ejemplos JSON | 🟡 Media | `backend/app/integrations/gemini_correction_client.py` |
| BUG-006 | Materia con solo examen GLOBAL: alumnos ausentes clasifican REGULARIZA (nota 5) en vez de ABANDONO | 🟡 Media | `backend/app/services/cierre_cursada_calculo.py` |
| BUG-007 | Fórmula "Recuperable" del Excel de cierre hardcodea umbral 40 (asume escala 100) | 🟡 Media | `backend/app/services/excel_cierre_cursada.py` |
| BUG-008 | `getCorreccionByEntregaId` traga cualquier error y devuelve `null` | 🟡 Media | `frontend/src/features/correcciones/services/correcciones-service.ts` |
| BUG-009 | Identidad de entrega por `alumno_nombre` exacto: homónimos y diferencias de mayúsculas colisionan o duplican | 🟡 Media | `backend/app/repositories/entrega_repository.py` |
| BUG-010 | Tracking del lote en EntregasPage nunca cierra si una entrega en ERROR vuelve a fallar (polling infinito) | 🟡 Media | `frontend/src/features/entregas/pages/EntregasPage.tsx` |
| BUG-011 | Fuga de archivos temporales en la carga masiva (`NamedTemporaryFile(delete=False)`) | 🟢 Baja | `backend/app/services/entrega_service.py` |
| BUG-012 | `corregirEntregasLote` apunta a un endpoint inexistente (`/entregas/corregir-lote`) | 🟢 Baja | `frontend/src/features/correcciones/services/correcciones-service.ts` |
| BUG-013 | Sobrescribir una entrega no limpia `error_code`/`error_mensaje`/`error_at` | 🟢 Baja | `backend/app/services/entrega_service.py` |
| BUG-014 | Fecha del filename del Excel de cierre en UTC (`datetime.utcnow`) en vez de hora Argentina | 🟢 Baja | `backend/app/services/excel_cierre_cursada.py` |

**Totales**: 1 crítica · 3 altas · 6 medias · 4 bajas.

---

### [CRÍTICA] Modelo Gemini inconsistente: config `gemini-3.5-flash` vs validación `gemini-2.5-flash`

- **ID**: BUG-001
- **Ubicación**: `backend/app/core/config.py:78` y `:87`, `backend/app/integrations/gemini_studio_client.py:11-14`, `backend/app/integrations/gemini_correction_client.py:320`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Bug
- **Descripción**: La corrección usa el modelo de config (`GEMINI_MODEL = "gemini-3.5-flash"`, `config.py:78`; `GeminiCorrectionClient.__init__` lo toma en `gemini_correction_client.py:320`), pero la **validación** de la API key pega contra un modelo distinto hardcodeado: `gemini-2.5-flash` (`gemini_studio_client.py:11-14`). OpenRouter arrastra el mismo nombre (`OPENROUTER_MODEL = "google/gemini-3.5-flash"`, `config.py:87`) tanto para validar como para corregir. `gemini-3.5-flash` no figura entre los IDs conocidos de la API de Google (`gemini-2.5-flash` sí existe) — ⚠️ A confirmar contra la API real, pero la inconsistencia interna es un hecho: se valida contra un modelo y se corrige contra otro.
- **Evidencia**:
  ```python
  # config.py:78
  GEMINI_MODEL: str = "gemini-3.5-flash"
  # gemini_studio_client.py:11-14 (validación)
  _VALIDATION_URL = (".../models/" "gemini-2.5-flash:generateContent")
  # gemini_correction_client.py:320 (corrección)
  self.model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
  ```
- **Impacto**: Si `gemini-3.5-flash` no existe en la API, la key del tutor **valida OK** (health check contra 2.5) pero **toda corrección falla** con 404 de Google mapeado a `N8NError` → entregas en ERROR y lotes que abortan. Aunque el modelo exista, validar contra un modelo distinto al de producción puede dar falsos positivos (key sin acceso al modelo real).
- **Reproducción**: configurar una key válida de Gemini Studio (valida OK en el perfil) → corregir una entrega → observar el error 502/`N8N_ERROR` con el mensaje de Google "model not found" (si el ID no existe en la cuenta).
- **Fix propuesto**: una sola fuente de verdad: que la URL de validación use `settings.GEMINI_MODEL` (y OpenRouter ya lo hace); fijar el default a un ID verificado contra la API (p. ej. `gemini-2.5-flash`) y documentar el override por `.env`.
- **Esfuerzo estimado**: S

---

### [ALTA] Re-corrección borra (y comitea) la corrección vieja antes de crear la nueva

- **ID**: BUG-002
- **Ubicación**: `backend/app/services/correccion_service.py:284-344`, `backend/app/repositories/correccion_repository.py:247-258` y `:217-230`
- **Severidad**: 🟠 Alta
- **Dimensión**: Bug
- **Descripción**: En `corregir_individual`, si ya existe corrección se hace `await self.correccion_repo.delete(existing_correccion)` (`correccion_service.py:288-290`), y ese `delete` **comitea inmediatamente** (`correccion_repository.py:257-258`). Recién después se construye y crea la nueva (`:309-344`), con otro commit. No hay transacción que abarque delete+create: si el `create` falla (dato de la IA que rompe una constraint, error de conexión a la DB, caída del proceso), la corrección anterior ya se perdió y la entrega queda en `PENDIENTE` sin corrección. El comentario del frontend (`correcciones-service.ts:92-101`, "la corrección anterior NO se pierde") asume una garantía que el backend no da completa. Además, dos re-correcciones concurrentes de la misma entrega (posible con `procesar_global_background`, que paraleliza con sesiones propias) pueden pasar ambas el check `get_by_entrega_id` y crear dos correcciones para la misma entrega.
- **Evidencia**:
  ```python
  # correccion_service.py:288-290
  if existing_correccion:
      await self.correccion_repo.delete(existing_correccion)  # ← commit acá
  ...
  created_correccion = await self.correccion_repo.create(correccion)  # ← commit separado
  ```
- **Impacto**: pérdida de la corrección previa (nota + criterios + feedback, incluyendo ediciones manuales del tutor) ante cualquier fallo entre ambos commits; posibles correcciones duplicadas por carrera, que luego rompen `get_by_entrega_id().scalar_one_or_none()` con `MultipleResultsFound` (500 en cascada).
- **Reproducción**: difícil de forzar a mano; simular un error de DB en el `create` posterior al `delete` (o matar el proceso entre ambos commits) y verificar que la corrección vieja desapareció.
- **Fix propuesto**: hacer delete+create en la misma transacción (un solo commit al final), o actualizar in-place la corrección existente en vez de borrar/crear. Para la carrera, unique constraint en `correccion.entrega_id` + manejo del IntegrityError.
- **Esfuerzo estimado**: M

---

### [ALTA] Cierre de cursada ignora el rescate cuando el parcial es NUMERICO y el recuperatorio no aporta nota numérica

- **ID**: BUG-003
- **Ubicación**: `backend/app/services/cierre_cursada_calculo.py:87-99` (`cumple_minimo`), `backend/app/services/examen_mapper.py:109-115` (`_valor_numerico`), `backend/app/services/cierre_cursada_service.py:255-265`
- **Severidad**: 🟠 Alta
- **Dimensión**: Bug
- **Descripción**: `examen_mapper.calcular_resultados_examenes` resuelve el rescate en el campo `resultado` (un parcial queda `aprobado` si lo aprobó él o cualquiera de sus recuperatorios, incluso si el recuperatorio es modo ESCALA). Pero `cumple_minimo` (`cierre_cursada_calculo.py:95-99`) **solo mira `resultado_escala` cuando el examen principal es modo ESCALA**; si el principal es NUMERICO, decide únicamente por `valor_real >= nota_minima`. Y `valor_real` excluye los rescates modo ESCALA (`_valor_numerico` devuelve `None` para exámenes no-NUMERICO, `examen_mapper.py:113-115`). Resultado: un parcial NUMERICO desaprobado (o ausente) rescatado por un recuperatorio configurado en modo ESCALA queda con `resultado = "aprobado"` pero `cumple_minimo = False` → el alumno NO promociona/regulariza aunque aprobó el rescate. Lo mismo pasa con `resultado = "sin_corregir"` (entregó el rescate, falta nota): `valor_real` es `None` → `cumple_minimo`/`cumple_banda` `False` y `examen_ausente` `True` (`:119-128`), pudiendo terminar en ABANDONO. ⚠️ A confirmar si en la práctica se configuran cadenas de rescate con modos mixtos (el ABM de `ExamenMateria` permite `modo_aprobacion` por examen, así que es configurable).
- **Evidencia**:
  ```python
  # cumple_minimo — modo NUMERICO ignora el `resultado` rescatado:
  if examen.get("modo_aprobacion") == "ESCALA":
      return examen.get("resultado_escala") == "aprobado"
  return valor_real is not None and nota_minima is not None and valor_real >= nota_minima
  # _valor_numerico — el rescate ESCALA nunca aporta valor:
  if ex.get("modo_aprobacion") != "NUMERICO":
      return None
  ```
- **Impacto**: clasificación de cierre incorrecta (RECURSA/ABANDONO en vez de PROMOCIONA/REGULARIZA) para alumnos que aprobaron por recuperatorio, en materias con modos mixtos. Afecta actas/Excel de cierre — decisión académica errónea.
- **Reproducción**: configurar parcial NUMERICO (mínimo 60) + recuperatorio del mismo parcial en modo ESCALA; alumno con parcial 40 y recuperatorio "Aprobado"; generar el cierre → el alumno figura RECURSA.
- **Fix propuesto**: en el armado de `examenes_para_estado` (o dentro de `cumple_minimo`) considerar el `resultado` rescatado como señal de aprobación aun en modo NUMERICO (p. ej. `resultado == "aprobado"` ⇒ cumple mínimo), y tratar `sin_corregir` como estado pendiente explícito, no como ausente.
- **Esfuerzo estimado**: M

---

### [ALTA] Re-entregas: se detectan pero nunca se re-importan, y "Entregar todos" fuerza la nota vieja sobre la entrega nueva

- **ID**: BUG-004
- **Ubicación**: `backend/app/services/moodle_import_service.py:458-466` y `:276-285`, `backend/app/services/entrega_service.py:286-289`, `backend/app/services/por_entregar_service.py:226-232` y `:268-271`
- **Severidad**: 🟠 Alta
- **Dimensión**: Bug
- **Descripción**: Cuando el alumno re-entrega en Moodle después de una corrección, la importación solo **cuenta** la re-entrega (`resumen.reentregas += 1`, `moodle_import_service.py:460-461`) — no descarga el archivo nuevo ni actualiza la entrega (el flujo corta en `verificar_entrega_existente` → `ya_corregida`). Si el tutor borra la corrección para reprocesar, el import la clasifica `duplicada` (`entrega_service.py:250`) y tampoco re-descarga. Es decir: **no existe camino automatizado para traer el contenido re-entregado**. En paralelo, `por_entregar_service.entregar_masivo_stream` detecta la re-entrega y **fuerza la subida** de la corrección existente (`forzar=es_reentrega_flag`, `:268-271`) — pero esa corrección se calculó sobre la entrega **vieja**, así que pisa la nota de Moodle con una nota que no corresponde al trabajo actual del alumno. ⚠️ A confirmar si el flujo esperado es que el tutor re-importe a mano antes de entregar; hoy el sistema no lo permite sin borrar la entrega completa.
- **Evidencia**:
  ```python
  # moodle_import_service.py:459-463 — la re-entrega solo suma al contador:
  if existente.status == "ya_corregida":
      if self._es_reentrega(sub, existente.correccion_actualizada_en):
          resumen.reentregas += 1
  # por_entregar_service.py:268-271 — y la subida masiva la fuerza igual:
  # "Re-entrega (item #3b): forzamos para pisar la nota vieja con la nueva"
  forzar=es_reentrega_flag,
  ```
- **Impacto**: el alumno que re-entregó recibe en Moodle la nota del trabajo anterior (potencialmente un Desaprobado sobre una versión corregida por él), y el contenido nuevo nunca entra a Active-IA salvo eliminación manual de la entrega. Datos desactualizados con efecto directo en calificaciones.
- **Reproducción**: importar y corregir una entrega; el alumno re-entrega en Moodle; correr "Importar" (solo suma al contador de re-entregas) y luego "Entregar todos" → la nota vieja pisa la calificación en Moodle.
- **Fix propuesto**: al detectar re-entrega, re-descargar y versionar la entrega (ya existe `historial_service.guardar_version_anterior`) invalidando la corrección previa; y en el masivo, excluir (u obligar re-corrección de) las re-entregas en vez de forzar la nota vieja.
- **Esfuerzo estimado**: L

---

### [MEDIA] Prompts de corrección con `{{`/`}}` literales en los ejemplos JSON

- **ID**: BUG-005
- **Ubicación**: `backend/app/integrations/gemini_correction_client.py:384-399` y `:428-443` y `:592-606`, `backend/app/integrations/openrouter_client.py:148-163` y `:176-191`
- **Severidad**: 🟡 Media
- **Dimensión**: Bug
- **Descripción**: Los ejemplos de JSON dentro de los prompts mezclan f-strings con strings comunes. Las líneas de llaves están en strings **no-f** (`'{{\n'`, `'    }}\n'`), por lo que el escape `{{` no se procesa y el modelo recibe literalmente `{{` y `}}` — el "JSON exacto" que se le pide devolver es inválido. Es un vestigio del template JS de N8N. En Gemini el `responseSchema` (`:459`, `:624`) salva el formato de salida, pero en OpenRouter solo hay `response_format: json_object` sin schema (`openrouter_client.py:202`): el modelo ve un ejemplo malformado y la instrucción "respondé EXACTAMENTE con este JSON".
- **Evidencia**:
  ```python
  # gemini_correction_client.py:384-385 — string normal, el {{ va literal:
  '{{\n'
  f'  "nota": 0,\n'
  ```
  El prompt final contiene: `{{\n  "nota": 0,\n  "criterios": [\n    {{ ...`
- **Impacto**: en modo OpenRouter, mayor tasa de respuestas no parseables (`N8NError: Respuesta de OpenRouter no es JSON válido`) o con claves envueltas raras, sobre todo en el camino de anti-inyección donde se pide copiar el JSON textual. En Gemini, ruido en el prompt (menor).
- **Reproducción**: loguear el prompt generado por `corregir_codigo`/`openrouter_client.corregir` y observar los `{{`/`}}` en los bloques de ejemplo.
- **Fix propuesto**: unificar los ejemplos como f-strings con `{{`/`}}` escapados correctamente, o construir el JSON de ejemplo con `json.dumps` de un dict.
- **Esfuerzo estimado**: S

---

### [MEDIA] Materia con solo examen GLOBAL: alumnos ausentes clasifican REGULARIZA (nota 5) en vez de ABANDONO

- **ID**: BUG-006
- **Ubicación**: `backend/app/services/cierre_cursada_calculo.py:212-226`
- **Severidad**: 🟡 Media
- **Dimensión**: Bug
- **Descripción**: `regulariza = (not promociona) and all(cumple_banda(e) for e in no_globales)` — si la materia solo tiene configurado un examen GLOBAL (sin parciales), `no_globales` queda vacío y `all([])` es `True`: **todo alumno que no promociona clasifica REGULARIZA**, incluso el que nunca rindió nada. El chequeo `todos_ausentes` (`:217`) queda inalcanzable porque `regulariza` gana antes en la cadena (`:219-226`), y REGULARIZA además persiste `nota_final = 5` (`:241-242`). `calcular_nota_final` sí exige ≥1 PARCIAL (`:172`), pero `calcular_estado_cierre` no tiene ese guard.
- **Evidencia**:
  ```python
  no_globales = [e for e in examenes if e.get("tipo") != "GLOBAL"]
  regulariza = (not promociona) and all(cumple_banda(e) for e in no_globales)  # all([]) == True
  todos_ausentes = all(examen_ausente(e) for e in examenes)  # nunca se alcanza si regulariza
  ```
- **Impacto**: en materias configuradas solo con GLOBAL (config permitida por el ABM de exámenes), el cierre reporta REGULARIZA con nota 5 para ausentes y desaprobados → acta errónea.
- **Reproducción**: configurar una materia con un único examen GLOBAL; generar cierre con un alumno sin ninguna nota → figura REGULARIZA / 5.
- **Fix propuesto**: exigir `no_globales` no vacío para regularizar (o evaluar `todos_ausentes` antes que `regulariza`), y/o bloquear en `generar` la config sin parciales.
- **Esfuerzo estimado**: S

---

### [MEDIA] Fórmula "Recuperable" del Excel de cierre hardcodea umbral 40 (asume escala 100)

- **ID**: BUG-007
- **Ubicación**: `backend/app/services/excel_cierre_cursada.py:66-88`
- **Severidad**: 🟡 Media
- **Dimensión**: Bug
- **Descripción**: `_formula_recuperable` marca "RECUPERABLE CON PARCIAL N" cuando un parcial es `>=40` y el otro `<40`. Ese 40 asume notas en escala 100 (mínimo 60 − banda 20). El resto del cierre es escala-aware (`detectar_escala` en `cierre_cursada_calculo.py:44-55` soporta escala 10, con banda 2), pero el Excel no: en una materia con parciales en escala 10 (mínimo 6), un 7 es `< 40` → la columna Recuperable queda siempre vacía y el conteo `RECUPERABLES` del resumen (`:105-114`) da 0. Además, exámenes principales en modo ESCALA muestran `N/E` (sin `valor_real`) y `IFERROR(VALUE("N/E"),0)` los trata como 0, o sea nunca recuperables.
- **Evidencia**:
  ```python
  f"IF(AND(IFERROR(VALUE({p1_col}{fila}),0)>=40,IFERROR(VALUE({p2_col}{fila}),0)<40),"
  ```
- **Impacto**: reporte de cierre con la columna Recuperable y el conteo RECUPERABLES incorrectos (vacíos) para materias en escala 10 o modo ESCALA — el gestor toma decisiones con datos que parecen "0 recuperables".
- **Reproducción**: cierre de una materia con parciales `nota_minima=6` (escala 10) y un alumno RECURSA con parcial 1 = 5 y parcial 2 = N/E → la celda Recuperable queda vacía (debería marcar "RECUPERABLE CON PARCIAL 2").
- **Fix propuesto**: derivar el umbral de la fórmula desde la escala de la config congelada (`run.examenes_snapshot`): 40 en escala 100, 4 en escala 10; para modo ESCALA, dejar en blanco explícito y documentarlo.
- **Esfuerzo estimado**: S

---

### [MEDIA] `getCorreccionByEntregaId` traga cualquier error y devuelve `null`

- **ID**: BUG-008
- **Ubicación**: `frontend/src/features/correcciones/services/correcciones-service.ts:57-69`
- **Severidad**: 🟡 Media
- **Dimensión**: Bug
- **Descripción**: El `catch` devuelve `null` ante **cualquier** error (500, timeout, red caída, 401), no solo 404. `useCorreccionByEntrega` (`useCorrecciones.ts:111-118`) cachea ese `null` con `staleTime` de 5 minutos como si la corrección no existiera, y `descargarPDFCorreccion` (`correcciones-service.ts:159-162`) lo traduce a "No se encontró corrección para esta entrega".
- **Evidencia**:
  ```typescript
  } catch (error) {
    // Si no existe corrección, retornar null
    return null;
  }
  ```
- **Impacto**: ante un error transitorio del backend, la UI muestra "sin corrección" para entregas que sí están corregidas (modal de detalle, descarga de PDF), y el estado equivocado persiste en cache hasta 5 minutos. Confunde al tutor y puede disparar re-correcciones innecesarias.
- **Reproducción**: apagar el backend (o forzar 500 en `/correcciones/entregas/{id}`) y abrir el detalle de una entrega corregida → la UI la trata como no corregida en vez de mostrar error.
- **Fix propuesto**: devolver `null` solo si `error.response?.status === 404`; re-lanzar el resto para que React Query lo exponga como `error`.
- **Esfuerzo estimado**: S

---

### [MEDIA] Identidad de entrega por `alumno_nombre` exacto: homónimos y diferencias de mayúsculas colisionan o duplican

- **ID**: BUG-009
- **Ubicación**: `backend/app/repositories/entrega_repository.py:161-186`, `backend/app/services/entrega_service.py:156-159` y `:762`, `backend/app/services/moodle_import_service.py:240-243` y `:441-443`
- **Severidad**: 🟡 Media
- **Dimensión**: Bug
- **Descripción**: La unicidad de una entrega es el par `(rubrica_id, alumno_nombre)` con match **exacto y case-sensitive** (`entrega_repository.py:181-184`). Los distintos caminos normalizan el nombre de forma distinta: la carga masiva y el import de Moodle aplican `.title()` + colapso de espacios (`entrega_service.py:762`, `moodle_import_service.py:441-443`), pero la carga individual usa el texto tal cual lo tipeó el tutor. Consecuencias: (a) el mismo alumno cargado a mano como "juan pérez" y luego importado como "Juan Pérez" genera **dos entregas**; (b) dos alumnos homónimos reales en la misma rúbrica colisionan: el segundo queda `duplicada` y su entrega nunca se importa; (c) si por carrera (import paralelo + carga manual simultánea) se crean dos filas con el mismo par, `scalar_one_or_none()` lanza `MultipleResultsFound` y el flujo entero se cae con 500.
- **Evidencia**:
  ```python
  # entrega_repository.py:181-184
  .where(Entrega.rubrica_id == rubrica_id, Entrega.alumno_nombre == alumno_nombre)
  # entrega_service.py:762 (masiva) vs data.alumno_nombre crudo (individual)
  alumno_nombre = " ".join(alumno_folder.split("_")[0].split()).title()
  ```
- **Impacto**: entregas duplicadas o silenciosamente omitidas (el homónimo se queda sin corrección), y 500 en cascada si aparecen duplicados en DB. En import Moodle el `moodle_user_id` existe y no se usa como clave.
- **Reproducción**: cargar a mano una entrega con el nombre en minúsculas y luego importar la misma desde Moodle → dos entregas para el mismo alumno en la misma rúbrica.
- **Fix propuesto**: usar `moodle_user_id` como clave de identidad cuando existe, y para cargas manuales normalizar el nombre en un solo lugar (casefold + colapso de espacios) antes de comparar/persistir; agregar unique constraint acorde.
- **Esfuerzo estimado**: M

---

### [MEDIA] Tracking del lote en EntregasPage nunca cierra si una entrega en ERROR vuelve a fallar

- **ID**: BUG-010
- **Ubicación**: `frontend/src/features/entregas/pages/EntregasPage.tsx:209-260` (y polling en `:197-205`)
- **Severidad**: 🟡 Media
- **Dimensión**: Bug
- **Descripción**: El efecto que detecta el fin del lote compara el estado actual con el inicial (`batchInitialStates`). Si el lote incluye entregas que **ya estaban en ERROR** (caso típico: reintentar las fallidas) y la corrección vuelve a fallar, el estado final es `ERROR` == estado inicial → la entrega cuenta como `untouched` para siempre (`:219-222`) y tampoco entra en `newErrors` (`:229-232`, que exige `initial !== 'ERROR'`). Con `untouched > 0` el efecto retorna sin limpiar `batchEntregaIds` (`:256`), así que `isBatchActive` queda `true` y el `setInterval` de 10s (`:200-202`) sigue invalidando queries indefinidamente, sin toast de resultado. Además, `batchItems` se calcula solo sobre la página visible (`data.items`, 20 por página): si el lote excede la página o el usuario cambia de filtro, la evaluación del lote opera sobre un subconjunto.
- **Evidencia**:
  ```typescript
  const untouched = batchItems.filter(e => {
    const initial = batchInitialStates.current[e.id];
    return initial !== undefined && e.estado === initial;   // ERROR→ERROR queda acá
  }).length;
  ...
  const newErrors = batchItems.filter(e =>
    e.estado === 'ERROR' && initial !== 'ERROR');           // y nunca entra acá
  ```
- **Impacto**: polling infinito contra `/entregas` mientras la página quede montada, sin feedback de que el lote terminó fallando — el tutor cree que "sigue procesando". Carga innecesaria al backend.
- **Reproducción**: seleccionar entregas en estado ERROR (API key inválida), lanzar "Corregir seleccionadas" → el backend vuelve a fallar → el spinner/polling no termina nunca y no aparece el toast de resumen.
- **Fix propuesto**: trackear la transición por `PENDIENTE` (una entrega que pasó por PENDIENTE y volvió a ERROR ya fue "tocada") o usar `error_at`/`updated_at` como señal de procesamiento, más un timeout máximo del tracking. Evaluar contra todos los IDs del lote, no solo los de la página visible.
- **Esfuerzo estimado**: M

---

### [BAJA] Fuga de archivos temporales en la carga masiva

- **ID**: BUG-011
- **Ubicación**: `backend/app/services/entrega_service.py:817-828`
- **Severidad**: 🟢 Baja
- **Dimensión**: Bug
- **Descripción**: Para carpetas de alumno con varios archivos sueltos se crea `tempfile.NamedTemporaryFile(suffix=".zip", delete=False)` y **nunca se borra**: no hay `os.unlink` posterior (el `os` importado en `:12` no se usa para esto). Cada carga masiva con carpetas multi-archivo deja un `.zip` huérfano en el temp del sistema. Además el archivo físico es innecesario: se lee todo a memoria igual (`tmp_zip.read()`).
- **Evidencia**:
  ```python
  with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
      with zipfile.ZipFile(tmp_zip, "w") as new_zip: ...
      tmp_zip.seek(0)
      contenido_bytes_alumno = tmp_zip.read()
  # ← nadie borra tmp_zip.name
  ```
- **Impacto**: acumulación de archivos temporales en el contenedor/host a lo largo de cuatrimestres de cargas masivas; llenado lento de disco.
- **Reproducción**: subir un ZIP masivo con carpetas de alumno con >1 archivo suelto y listar el dir temp del proceso.
- **Fix propuesto**: reemplazar por `io.BytesIO()` (sin tocar disco), igual que hace `_obtener_bytes` en `moodle_import_service.py:533-538`.
- **Esfuerzo estimado**: S

---

### [BAJA] `corregirEntregasLote` apunta a un endpoint inexistente

- **ID**: BUG-012
- **Ubicación**: `frontend/src/features/correcciones/services/correcciones-service.ts:31-38`, `frontend/src/features/correcciones/hooks/useCorrecciones.ts:171-210`
- **Severidad**: 🟢 Baja
- **Dimensión**: Bug
- **Descripción**: `corregirEntregasLote` hace `POST /entregas/corregir-lote`, ruta que no existe en ningún router del backend (el lote real es `POST /correcciones/lote`, `correcciones.py:154-159`, y devuelve 202 con `CorregirLoteAceptadoResponse`, no `Correccion[]`). El hook `useCorregirEntregasLote` que lo envuelve está exportado en `hooks/index.ts` pero hoy ningún componente lo usa (la vista usa `useCorregirEntregaMasiva` de `features/entregas`, que sí pega a `/correcciones/lote`). Es código muerto armado para un contrato viejo: si alguien lo cablea, falla con 404 y su `onSuccess` (`correcciones.forEach(...)`) explotaría igual porque el shape de respuesta no es un array.
- **Evidencia**:
  ```typescript
  const response = await apiClient.post<Correccion[]>('/entregas/corregir-lote', ...)
  ```
- **Impacto**: trampa latente para el próximo dev; doble implementación del mismo flujo con contratos distintos.
- **Reproducción**: invocar `useCorregirEntregasLote().mutate([id])` → 404.
- **Fix propuesto**: eliminar `corregirEntregasLote`/`useCorregirEntregasLote` o alinearlos al endpoint y contrato reales (`/correcciones/lote`, 202).
- **Esfuerzo estimado**: S

---

### [BAJA] Sobrescribir una entrega no limpia `error_code`/`error_mensaje`/`error_at`

- **ID**: BUG-013
- **Ubicación**: `backend/app/services/entrega_service.py:180-199` (individual) y `:883-897` (masiva)
- **Severidad**: 🟢 Baja
- **Dimensión**: Bug
- **Descripción**: Al sobrescribir una entrega existente se resetea `estado = SUBIDA` pero se dejan intactos los campos de error de la corrida anterior (`error_code`, `error_mensaje`, `error_at`), que solo limpia `_limpiar_entrega_error` en `correccion_service.py:79-84` tras una corrección exitosa. La entrega nueva viaja al frontend con un `error_mensaje` viejo (siempre incluido en `EntregaListItem`, `entrega_service.py:457-458`). Hoy el badge lo muestra solo cuando `estado === 'ERROR'` (`EntregasPage.tsx:819`), así que el impacto visible es nulo, pero cualquier consumidor futuro del campo (o el resumen de errores del progreso global, que cuenta por `error_code`) lee datos stale.
- **Evidencia**: en `:181-197` se asignan archivo/contenido/hash/estado, ninguno de los tres campos `error_*`.
- **Impacto**: datos inconsistentes en API (entrega SUBIDA con mensaje de error de otra versión del archivo); conteos de `errores_por_codigo` potencialmente inflados en `/correcciones/global/progreso` si la entrega quedó en ERROR previo y se re-subió.
- **Reproducción**: corregir una entrega con API key inválida (queda ERROR con mensaje), re-subir el archivo con `sobrescribir=true` y consultar `GET /entregas` → `error_mensaje` sigue presente con `estado=SUBIDA`.
- **Fix propuesto**: limpiar los tres campos `error_*` en ambos caminos de sobrescritura (reutilizar `_limpiar_entrega_error`).
- **Esfuerzo estimado**: S

---

### [BAJA] Fecha del filename del Excel de cierre en UTC en vez de hora Argentina

- **ID**: BUG-014
- **Ubicación**: `backend/app/services/excel_cierre_cursada.py:414`, mismo patrón en `backend/app/services/consolidacion_service.py:439` y `:500` (`datetime.now()` naive del server)
- **Severidad**: 🟢 Baja
- **Dimensión**: Bug
- **Descripción**: `generar_excel_cierre` arma el nombre del archivo con `datetime.utcnow().strftime("%Y%m%d")`, ignorando el helper `ahora_ar()`/`fmt_fecha_ar` de `app/core/fecha.py` que existe justamente para esto ("si no aparecen +3hs", `fecha.py:5-7`). Entre las 21:00 y las 00:00 hora Argentina, el archivo sale fechado **al día siguiente**. En la consolidación (`consolidacion_service.py:439/500`) se usa `datetime.now()` del server, que en un contenedor UTC tiene el mismo corrimiento en el texto "Fecha de generación" que ve la IA y el tutor.
- **Evidencia**:
  ```python
  fecha = datetime.utcnow().strftime("%Y%m%d")
  filename = excel_estilos.sanitize_filename(f"Cierre_{materia_nombre}_{fecha}.xlsx")
  ```
- **Impacto**: nombres de archivo con fecha corrida (confunde versiones de cierres generados a la noche) y metadata de consolidación con hora incorrecta. Sin pérdida de datos.
- **Reproducción**: generar el Excel de cierre después de las 21:00 (AR) en un server UTC → el filename lleva la fecha de mañana.
- **Fix propuesto**: usar `app.core.fecha.ahora_ar()` para ambos casos.
- **Esfuerzo estimado**: S
