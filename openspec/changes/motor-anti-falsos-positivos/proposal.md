## Why

Cuatro de los seis bugs reportados por AI-Native son **falsos positivos y falsos negativos del motor**: el modelo cierra un criterio sin tener con qué. No son errores de aritmética (esos son el change `nota-deterministica-penalizaciones`), son errores de **evidencia**.

**Bug 1 — descuenta puntos por archivos que SÍ están en la entrega.** Verificado en el código: `Entrega.archivos_incluidos` (`app/models/entrega.py:80`) guarda el inventario exacto de archivos consolidados, y **nunca llega al prompt** — `grep archivos_incluidos` sobre `correccion_service.py` y `app/integrations/` da **cero** resultados. `_build_correction_payload` (L893-912) manda `codigo`, `rubrica` y un `contexto` con materia y alumno, nada más. El modelo recibe un blob de texto concatenado y tiene que inferir qué archivos entregó el alumno. Cuando el blob viene truncado por `_truncar_codigo` (IA-015), directamente ve menos de lo que hay. Dejó a una alumna desaprobada el 2026-08-04.

**Bug 4 — cuenta presencia, no vínculo.** 100/100 a una entrega con "3 categorías OK" y "10 productos OK" donde ningún producto quedaba vinculado a ninguna categoría. El modelo encontró los sustantivos de la rúbrica en el código y cerró el criterio.

**Bug 5 — elogia como correcto código hardcodeado.** Puntaje completo a una "búsqueda" que era `if puntajes[i] == 990`.

Los bugs 4 y 5 son el mismo mecanismo: **el criterio se cierra por reconocimiento léxico, no por verificación**. Hoy nada en el prompt obliga al modelo a decir *dónde* vio lo que dice que vio, así que no hay costo en afirmarlo.

**Bug 6 — recomienda cosas que la cátedra prohíbe.** Sugirió `try/except` en Programación 1, donde la consigna lo veda y lo repite tres veces. Causa: **la rúbrica no tiene dónde declarar una prohibición**. `metadata_json` es flexible pero nadie escribe restricciones ahí, y el prompt no las renderiza. El modelo recomienda buenas prácticas generales porque nadie le dijo cuáles están vedadas en esta materia.

## What Changes

- **El inventario de archivos viaja al prompt.** `archivos_incluidos` se inyecta como sección explícita, junto con si el código fue truncado y en qué punto. Se agrega la regla dura: *"si un archivo figura en el inventario, está entregado; no descuentes por ausencia de nada que esté listado"*.
- **Evidencia obligatoria por criterio.** El schema de respuesta gana, por criterio (y por subcriterio en v2), un campo `evidencia`: la cita textual del código que respalda el puntaje. Sin evidencia citable, el criterio no puede cerrarse como cumplido. El backend **verifica que la cita exista literalmente en el código entregado** y degrada el criterio a `WARNING` con nota reducida cuando no aparece.
- **Distinción explícita presencia vs. vínculo.** El prompt incorpora la regla de que declarar una entidad no es cumplir un criterio sobre esa entidad: hay que mostrar la línea donde se usa/vincula. Con ejemplos negativos concretos (el caso categorías/productos).
- **Detección de hardcodeo.** El prompt incorpora la heurística de valores literales embebidos que hacen pasar un caso puntual sin implementar el algoritmo, con el ejemplo `if puntajes[i] == 990`, y la instrucción de tratarlo como criterio NO cumplido.
- **Restricciones de cátedra en la rúbrica.** Nuevo bloque `restricciones` en la rúbrica (construcciones, librerías o enfoques prohibidos por la consigna), editable desde el frontend, renderizado en el prompt como restricción dura sobre las **recomendaciones**: el motor no puede recomendar nada que la rúbrica vede.
- **Sin migración de esquema**: `restricciones` vive en `metadata_json` (JSONB ya existente); `evidencia` vive en `criterios_json` (JSONB ya existente).

## Capabilities

### New Capabilities

- `correccion-evidencia-verificable`: evidencia citable y verificada por criterio y subcriterio — el motor debe mostrar la línea de código que respalda cada puntaje, y el backend degrada el criterio cuando la cita no existe en la entrega.
- `correccion-inventario-archivos`: el inventario de archivos consolidados y el estado de truncado del código viajan al prompt, con la regla que prohíbe descontar por ausencia de un archivo listado.
- `rubrica-restricciones-catedra`: declaración de construcciones/librerías/enfoques prohibidos por la consigna en la rúbrica, y su aplicación como restricción dura sobre las recomendaciones del motor.

### Modified Capabilities

- `correccion-desglose-subcriterio`: el desglose por subcriterio gana el campo de evidencia.

## Impact

**Backend**
- `app/services/correccion_service.py` — `_build_correction_payload` (L888-912) y `_build_pdf_correction_payload` (L936-960): inyectar inventario, flag de truncado y restricciones; nueva verificación de evidencia post-respuesta.
- `app/integrations/gemini_correction_client.py` — nueva sección de inventario, reglas de evidencia/vínculo/hardcodeo en las instrucciones, sección de restricciones, y `evidencia` en los cuatro `responseSchema` (código v1/v2, PDF v1/v2).
- `app/integrations/openrouter_client.py` — comparte los builders; verificar herencia.
- `app/schemas/correccion.py` — `evidencia` opcional en `CriterioGeminiSchema`, `CriterioEvaluado`, `SubcriterioEvaluado`, `CorreccionResponse`.
- `app/schemas/rubrica.py` — `restricciones` dentro de `metadata_json`, con validación de shape.
- `app/services/pdf_service.py` — decidir si la evidencia se muestra al alumno (ver design, D5).

**Frontend**
- `features/rubricas/` — editor de restricciones de cátedra (schema Zod, componente, tipos).
- `features/correcciones/` — mostrar la evidencia citada por criterio en el modal de revisión del tutor.

**Sin migración de esquema.** Ambos campos nuevos viven en columnas JSONB existentes.

**Nota de alcance**: este change reduce los bugs 4 y 5, no los elimina. La eliminación real de esos dos modos de fallo es el change `correccion-por-ejercicio-con-tests`, que le da al motor el resultado de tests ejecutados. Los dos son complementarios: la evidencia disciplina el juicio sobre diseño, el test resuelve el juicio sobre funcionamiento.
