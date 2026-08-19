> **Gobernanza: 🟡 MEDIA.** Implementar con checkpoints, surfaceando las decisiones no obvias. Sin migración de esquema: `restricciones` va en `metadata_json` y `evidencia` en `criterios_json`, ambos JSONB existentes.

## 1. Backend — Inventario de archivos al prompt (bug 1)

- [ ] 1.1 (RED) Test: `_build_correction_payload` incluye el bloque de entrega con `archivos_incluidos`, `archivo_nombre` y `archivo_tipo`.
- [ ] 1.2 (RED) Test: entrega con `archivos_incluidos` nulo o vacío → el inventario cae al nombre del archivo original.
- [ ] 1.3 Agregar el bloque `entrega` a `_build_correction_payload` (`app/services/correccion_service.py:888-912`) y a `_build_pdf_correction_payload` (L936-960).
- [ ] 1.4 (RED) Test: el payload informa `codigo_truncado`, `caracteres_originales` y `caracteres_enviados` cuando `_truncar_codigo` recorta, y `codigo_truncado: false` cuando no.
- [ ] 1.5 Hacer que `_truncar_codigo` (L130-139) devuelva también el estado del truncado, sin cambiar el marcador textual que ya inyecta.
- [ ] 1.6 Nueva sección de inventario en el prompt (`app/integrations/gemini_correction_client.py`), previa al código, con la regla dura de no descontar por archivos listados y la advertencia de truncado.
- [ ] 1.7 (TRIANGULATE) Test: criterio sobre un archivo NO listado sigue pudiendo señalarse como ausente (la regla no anula la detección de faltantes reales).
- [ ] 1.8 Verificar que el camino PDF y el proveedor OpenRouter heredan la sección.
- [ ] CHECKPOINT: reproducir el caso del 2026-08-04 (materia 22, rúbrica 188) y confirmar que ya no descuenta por archivos presentes.

## 2. Backend — Evidencia por criterio en el contrato de la IA

- [ ] 2.1 (RED) Test: `CriterioGeminiSchema` y `CriterioEvaluado` parsean con y sin `evidencia`.
- [ ] 2.2 Agregar `evidencia: str | None` a `CriterioGeminiSchema`, `CriterioEvaluado`, `SubcriterioEvaluado` y `CorreccionResponse` en `app/schemas/correccion.py`.
- [ ] 2.3 Agregar `evidencia` a los cuatro `responseSchema` de `gemini_correction_client.py` (código v1/v2, PDF v1/v2) y al `response_format` de OpenRouter.
- [ ] 2.4 Instrucción en el prompt: citar de una a tres líneas literales del código entregado por criterio (y por subcriterio en v2).
- [ ] 2.5 (TRIANGULATE) Test: respuesta sin `evidencia` (correcciones viejas o modelo que omite) parsea y persiste sin error.
- [ ] 2.6 Persistir `evidencia` dentro de cada criterio en `criterios_json`, sin migración.
- [ ] CHECKPOINT: el contrato acepta evidencia y tolera su ausencia; ningún camino existente se rompe.

## 3. Backend — Verificación de la evidencia

- [ ] 3.1 (RED) Test del normalizador: cita idéntica salvo espaciado → encontrada; cita con distinta capitalización → no encontrada; cita inexistente → no encontrada.
- [ ] 3.2 Implementar `_verificar_evidencia(cita, codigo_consolidado) -> bool` con colapso de espacios/tabs y saltos de línea ignorados, sensible al case.
- [ ] 3.3 (RED) Test de degradación: criterio de peso 20 con puntaje 20 y cita inexistente → `WARNING`, puntaje 10, feedback anotado, log WARNING.
- [ ] 3.4 (RED) Test: criterio de peso 20 con puntaje 6 y cita inexistente → puntaje se mantiene en 6, solo se marca `WARNING`.
- [ ] 3.5 Implementar la degradación en `correccion_service.py`, aplicada **después** del recomputo por subcriterios del change `nota-deterministica-penalizaciones` si ese change ya está aplicado.
- [ ] 3.6 (TRIANGULATE) Tests de las tres exenciones: criterio en 0 no se degrada; corrección de PDF no verifica; código truncado loguea sin degradar.
- [ ] 3.7 Instrumentar la tasa de citas no verificadas en el log, para poder revisar el umbral del 50% con datos (ver Open Question del design).
- [ ] CHECKPOINT: la verificación degrada sin desaprobar a nadie por un falso negativo. Revisar la tasa observada antes de seguir.

## 4. Backend — Reglas de vínculo y hardcodeo en el prompt (bugs 4 y 5)

- [ ] 4.1 (RED) Test de caracterización del prompt actual, para tener el antes.
- [ ] 4.2 Agregar el bloque de presencia-vs-vínculo con el ejemplo negativo de categorías/productos sin asociar.
- [ ] 4.3 Agregar el bloque de hardcodeo con el ejemplo negativo de la búsqueda resuelta con un literal.
- [ ] 4.4 Verificar que ambos bloques llegan al camino PDF y a OpenRouter.
- [ ] 4.5 Medir el delta de `tokens_entrada` contra una corrección de referencia (columnas de IA-014) y dejarlo anotado.
- [ ] CHECKPOINT: correr los dos casos control documentados (100/100 sin vínculo, y `if puntajes[i] == 990`) y reportar el resultado honestamente — este change los reduce, no los elimina.

## 5. Backend — Restricciones de cátedra en la rúbrica (bug 6)

- [ ] 5.1 (RED) Test: restricción válida se persiste; alcance desconocido falla; restricción sin descripción o sin id falla; rúbrica sin restricciones valida igual que hoy.
- [ ] 5.2 Definir el modelo Pydantic `RestriccionCatedra` (`id`, `descripcion`, `alcance`) y validar la lista dentro de `metadata_json` en `app/schemas/rubrica.py`.
- [ ] 5.3 (RED) Test: el prompt lista las restricciones y prohíbe recomendarlas; sin restricciones, la sección no aparece.
- [ ] 5.4 Renderizar la sección de restricciones en el prompt (código y PDF) como restricción dura sobre `recomendaciones` y sobre el feedback.
- [ ] 5.5 (TRIANGULATE) Test: una restricción `prohibido_en_codigo` NO genera descuento automático; el descuento sigue siendo responsabilidad de una `Penalizacion`.
- [ ] CHECKPOINT: verificar contra una rúbrica real de Programación 1 con la restricción de manejo de excepciones cargada, y confirmar que el motor deja de recomendarla.

## 6. Frontend

- [ ] 6.1 Schema Zod y tipos de `RestriccionCatedra` en `features/rubricas/`.
- [ ] 6.2 Sección de restricciones en el editor de rúbricas (alta, edición, baja), con validación en el cliente y componente < 200 LOC.
- [ ] 6.3 Verificar que una rúbrica preexistente abre con la sección vacía y guarda sin declarar restricciones.
- [ ] 6.4 Mostrar la evidencia por criterio en el modal de revisión del tutor (`features/correcciones/`), tolerando su ausencia.
- [ ] 6.5 Confirmar que el PDF de devolución NO incluye la evidencia.
- [ ] 6.6 `npm run typecheck` y `npm run lint` sin errores; sin `any`.
- [ ] CHECKPOINT: flujo completo de tutor — corregir, revisar evidencia, generar PDF.

## 7. Verificación y cierre

- [ ] 7.1 `pytest` completo en el backend, sin regresiones.
- [ ] 7.2 Correr los cuatro casos control (bugs 1, 4, 5, 6) y documentar el resultado de cada uno, incluidos los que sigan fallando.
- [ ] 7.3 Reportar el delta de costo por corrección (`tokens_entrada` / `tokens_salida`) contra la línea de base.
- [ ] 7.4 Cargar las restricciones de Programación 1 en sus rúbricas de producción.
- [ ] 7.5 `openspec validate motor-anti-falsos-positivos --strict`.
