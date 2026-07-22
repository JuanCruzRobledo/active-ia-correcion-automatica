# 🔍 Auditoría integral Active-IA — Resumen Ejecutivo

> **Fecha**: 2026-07-12
> **Alcance**: backend FastAPI + frontend React/TS + integración IA (Google AI Studio / OpenRouter).
> **Método**: auditoría estática por 9 dimensiones, cada hallazgo con evidencia `archivo:línea`. **No se modificó una sola línea de código de producción** — esto es diagnóstico, no arreglo.
> **Fuente de verdad**: el CÓDIGO. La documentación quedó desactualizada tras la salida de N8N y toda divergencia se registró como hallazgo (dimensión 9).

---

## 1. Tabla de conteo por dimensión y severidad

| # | Dimensión | 🔴 Crítica | 🟠 Alta | 🟡 Media | 🟢 Baja | Total |
|---|-----------|:---------:|:-------:|:-------:|:-------:|:-----:|
| 1 | 🐛 Bugs funcionales | 1 | 3 | 6 | 4 | 14 |
| 2 | 🗃️ CRUDs | 1 | 6 | 7 | 3 | 17 |
| 3 | ⚡ Performance | 3 | 5 | 6 | 4 | 18 |
| 4 | 🎨 UI/UX | 1 | 4 | 5 | 3 | 13 |
| 5 | 📨 Transmisión de errores | 1 | 5 | 7 | 2 | 15 |
| 6 | 🔐 Seguridad y permisos | 3 | 3 | 5 | 3 | 14 |
| 7 | 🏛️ Arquitectura | 1 | 4 | 4 | 3 | 12 |
| 8 | 🤖 Integración IA | 1 | 5 | 6 | 3 | 15 |
| 9 | 📄 Docs desactualizadas | 2 | 7 | 4 | 1 | 14 |
| | **TOTAL** | **14** | **42** | **50** | **26** | **132** |

Informes detallados:
- [01-bugs-funcionales.md](01-bugs-funcionales.md)
- [02-cruds.md](02-cruds.md)
- [03-optimizacion.md](03-optimizacion.md)
- [04-ui-ux.md](04-ui-ux.md)
- [05-errores-transmision.md](05-errores-transmision.md)
- [06-seguridad-permisos.md](06-seguridad-permisos.md)
- [07-arquitectura.md](07-arquitectura.md)
- [08-integracion-ia.md](08-integracion-ia.md)
- [09-documentacion-desactualizada.md](09-documentacion-desactualizada.md)

---

## 2. Top 10 hallazgos críticos (ordenados por impacto)

| # | ID | Título | Dim. | Por qué duele en producción |
|---|----|--------|------|------------------------------|
| 1 | [SEC-001](06-seguridad-permisos.md) / [SEC-002](06-seguridad-permisos.md) | **IDOR en correcciones y entregas** | 🔐 | Cualquier usuario autenticado lee, **altera notas** y **borra** correcciones/entregas de comisiones ajenas iterando IDs. Los servicios ni reciben `current_user` para filtrar. Fuga masiva + adulteración de datos académicos. |
| 2 | [SEC-003](06-seguridad-permisos.md) | **SECRET_KEY / ENCRYPTION_KEY con defaults del repo** | 🔐 | Sin validador que aborte en prod. Con la SECRET_KEY pública se **forjan JWT de ADMIN**; con la ENCRYPTION_KEY se descifran todas las API keys y contraseñas Moodle. |
| 3 | [IA-001](08-integracion-ia.md) | **Condiciones de desaprobación se anulan solas** | 🤖 | El responseSchema nunca devuelve los campos de CD y el autocorrector pisa la nota tope con la suma de criterios: un alumno que debía **desaprobar puede quedar aprobado**. Corrompe la nota, que es el core del producto. |
| 4 | [CRUD-001](02-cruds.md) / [CRUD-004](02-cruds.md) | **Hard delete de entregas + archivos nunca persistidos** | 🗃️ | `DELETE /entregas` borra físico entrega+corrección+historial sin ownership ni auditoría. Y `archivo_ruta` es un string fabricado: **el ZIP/PDF original del alumno se pierde en el upload** (a confirmar, pero gravísimo). |
| 5 | [BUG-002](01-bugs-funcionales.md) / [CRUD-003](02-cruds.md) | **Re-corrección destruye la corrección previa** | 🐛/🗃️ | `corregir_individual` hace `delete + commit` de la corrección vieja y *después* el `create`. Fallo intermedio = **se pierden ediciones manuales del tutor** y la entrega queda PENDIENTE. |
| 6 | [PERF-001](03-optimizacion.md) / [PERF-002](03-optimizacion.md) | **Modelo que carga todo siempre** | ⚡ | `lazy="selectin"` encadenado + listados que arrastran código consolidado y PDFs Base64 por fila: 20 entregas PDF ≈ **>100MB desde Postgres** para un JSON de 10KB. |
| 7 | [PERF-003](03-optimizacion.md) | **ZIP de devoluciones bloquea el backend** | ⚡ | Renderiza hasta 1000 PDFs con reportlab **síncrono dentro del request** + N+1 por corrección: **congela el event loop entero** del backend. |
| 8 | [BUG-001](01-bugs-funcionales.md) / [IA-006](08-integracion-ia.md) | **Modelo Gemini inconsistente (validación ≠ uso)** | 🐛/🤖 | La key se valida contra `gemini-2.5-flash` hardcodeado, pero la corrección usa `gemini-3.5-flash` de config. Si ese ID no existe en la API, **la key valida OK y toda corrección revienta en prod**. |
| 9 | [DOC-004](09-documentacion-desactualizada.md) / [DOC-005](09-documentacion-desactualizada.md) | **Deploy roto por N8N fantasma** | 📄 | El compose de EasyPanel exige `N8N_BASIC_AUTH_PASSWORD:?` → el deploy **aborta** sin password de un servicio muerto. El prod levanta N8N público inútil con `nginx upstream n8n:5678` (sacarlo mal tumba el sitio). |
| 10 | [ERR-001](05-errores-transmision.md) | **Key IA inválida → 500 crudo al generar rúbrica** | 📨 | `rubrica_ia_service` solo captura las excepciones viejas `N8NError`; el cliente real lanza `APIKeyInvalidError`. Resultado: 500 sin mensaje y la key no se marca inválida. |

---

## 3. Quick wins (alto impacto, bajo esfuerzo — atacar primero)

| Prioridad | Hallazgo | Esfuerzo | Impacto |
|:---------:|----------|:--------:|---------|
| 1 | **SEC-003** — validar en el arranque que `SECRET_KEY`/`ENCRYPTION_KEY` no sean los defaults y abortar si lo son | **S** | Desactiva el peor escenario (forja de JWT ADMIN + descifrado de todas las keys) con pocas líneas. |
| 2 | **BUG-001 / IA-006** — unificar el ID del modelo Gemini entre `config.py` y los clientes; validar contra el mismo modelo que se usa | **S** | Evita que toda corrección falle en prod pese a una key "válida". |
| 3 | **DOC-005 / DOC-004** — quitar el servicio N8N de los compose de prod/easypanel y el `upstream n8n` de nginx | **S** | Destraba el deploy que hoy aborta o levanta un contenedor inútil. |
| 4 | **UI-001** — agregar ConfirmDialog + onError al "Eliminar usuario" (el patrón ya existe en el resto del CRUD) | **S** | Elimina borrados accidentales sin feedback. |
| 5 | **ERR-001** — ampliar el `except` de `rubrica_ia_service` para capturar las excepciones reales del cliente IA | **S** | Convierte un 500 crudo en un mensaje útil + marca la key inválida. |
| 6 | **ERR-004** — que el interceptor axios no trate el 401 del login como "sesión expirada" | **S** | El usuario ve "credenciales inválidas / intentos restantes" en vez de un reload confuso. |
| 7 | **PERF-008 / SEC-005** — aplicar `MAX_UPLOAD_SIZE` (ya definido pero nunca usado) + límite anti ZIP-bomb | **S** | Cierra un DoS trivial por upload y respeta un config que hoy es decorativo. |

> Los IDOR (**SEC-001/002**) son la urgencia #1 de seguridad pero su fix es **M** (hay que inyectar `current_user` y validar pertenencia endpoint por endpoint en correcciones y entregas), por eso no entran como "quick win" pese a ser lo más grave.

---

## 4. Evaluación general de salud del sistema

Active-IA es un sistema **funcionalmente rico pero estructuralmente frágil**, atrapado a mitad de una migración que nunca se terminó de limpiar. La lógica de dominio está mayormente en su lugar y hay decisiones sanas (catálogo de errores provider-aware, auditoría de MoodleSync, cifrado real de las API keys), pero tres problemas transversales lo comprometen: **(1) la autorización es inline y con agujeros** —los IDOR en el recurso más sensible (notas y entregas) permiten leer y adulterar datos ajenos—; **(2) el "soft delete obligatorio" es casi ficción** —la mitad de las entidades borran físico, incluidas Entrega y Correccion, y en el peor caso ni siquiera se persiste el archivo original del alumno—; y **(3) la salida de N8N dejó escombros peligrosos** que llegan hasta romper el deploy y a inducir a agentes a reconstruir la arquitectura removida. Sumado a un modelo de datos que carga todo siempre y hace trabajo pesado en el event loop, el sistema hoy **funciona en el camino feliz pero se cae, filtra o corrompe datos apenas se sale de él**. La buena noticia: los tres críticos de performance son la misma enfermedad y varios quick wins de seguridad y deploy son de esfuerzo S. Con una tanda enfocada de correcciones S/M se neutraliza la mayoría del riesgo crítico. **Prioridad absoluta: cerrar los IDOR y los defaults de claves antes de cualquier cosa nueva.**
