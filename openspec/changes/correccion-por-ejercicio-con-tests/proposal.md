## Why

AI-Native lo llama "la parte más importante del pedido", y tiene razón.

**AI-Native ejecuta el código del alumno en un sandbox real** (Docker sin privilegios, Java 21, sin red, límite de 10s). Sabe con certeza qué casos pasan y cuáles no, con qué entrada y qué salió.

**Active-IA lee el código con un LLM.** Los modos de fallo documentados del motor salen todos de ahí: 100/100 a una entrega donde ningún producto quedaba vinculado a ninguna categoría (*vio* las piezas); puntaje completo a una "búsqueda" que era `if puntajes[i] == 990` (*leyó* una búsqueda).

**Un test ejecutado no se deja engañar por ninguna de esas dos cosas.** Recibir el resultado de la corrida convierte "el programa funciona" de una inferencia del modelo en un hecho verificado, y libera al motor para juzgar lo que un test no puede medir y que es justamente lo que la rúbrica evalúa: si la excepción es verificada o de runtime, si usó la interfaz o enumeró los tipos concretos, si el encapsulamiento es real.

Y hay una distinción que el cliente agregó el 2026-08-19 y que importa:

| | `compila` | `pasados/total` | Qué le pasó al alumno |
|---|---|---|---|
| No compila | `false` | `0/6` | Un error de sintaxis. Puede ser un punto y coma. |
| Compila y falla todo | `true` | `0/6` | El programa corre y hace otra cosa. |

Son dos situaciones distintas y merecen devoluciones distintas. `compila` **no se deduce de `pasados: 0`**.

El cliente manda el código aunque no compile — antes lo cortaba y lo revirtió, porque un punto y coma que falta no justifica dejar al alumno sin devolución: el juicio sobre el **diseño** sigue siendo útil y es justo lo que un compilador no da. Lo que pide a cambio: **con `compila: false`, que no se cierren criterios del tipo "el programa funciona"**, porque ninguna corrida los respalda.

## What Changes

- **`POST /api/v1/correcciones/ejercicios/{ejercicio_ref}/corregir`** — corrige un ejercicio para un alumno, recibiendo el código y el resultado de los tests ya ejecutados. Devuelve nota y desglose de ese ejercicio.
- **El resultado de los tests viaja al motor como hecho establecido**, no como sugerencia. El prompt gana una sección de RESULTADO DE EJECUCIÓN con la instrucción explícita de no volver a deducir si el programa funciona.
- **Nuevo campo de rúbrica `depende_de_ejecucion` por criterio.** Marca los criterios cuyo cumplimiento requiere que el programa corra. Con `compila: false`, esos criterios se cierran en 0 **determinísticamente en el backend**, con feedback que cita `error_compilacion`. Es el mismo criterio del change `nota-deterministica-penalizaciones`: una regla que la rúbrica declara no se delega a un LLM.
- **Resolución de la comisión** — el hueco que el documento no vio: `entregas.comision_id` es `NOT NULL` y AI-Native no tiene comisiones. Se agrega `Materia.comision_integracion_id`, que un admin configura una vez por materia, y un `comision_external_ref` opcional en el cuerpo para cuando el cliente quiera modelar cohortes. El contrato que su cliente ya implementó **no cambia**.
- **Recorrección en lugar de 409.** Si ya existe una entrega para ese alumno en esa rúbrica, se reusa y se recorrige, guardando la corrección anterior en el historial (mecanismo ya existente). El cliente no tiene que manejar un 409 para el camino de ejercicio.
- **Sin corrección en lote**: se dispara de a un ejercicio, como el cliente pidió.
- **Active-IA no calcula la nota final del TP.** Devuelve nota por ejercicio; el promedio ponderado lo hace el cliente.

## Capabilities

### New Capabilities

- `correccion-ejercicio-endpoint`: endpoint de corrección por ejercicio, identificado por referencia externa, con pseudónimo de alumno, código y resultado de tests; resolución de comisión y reuso de entrega con historial.
- `correccion-resultado-tests`: incorporación del resultado de ejecución al motor como hecho establecido, con la distinción entre no compilar y compilar fallando, y el uso de `error_compilacion` en la devolución.
- `rubrica-criterio-depende-ejecucion`: marca por criterio de dependencia de ejecución, y cierre determinístico en cero de esos criterios cuando el código no compila.

### Modified Capabilities

- `correccion-nota-deterministica`: el cierre en cero por no compilar se integra a la cadena de cálculo determinístico de la nota.
- `correccion-evidencia-verificable`: los criterios cerrados en cero por no compilar quedan exentos de la verificación de evidencia.

## Impact

**Backend**
- `app/routers/correcciones.py` — endpoint nuevo.
- `app/services/correccion_service.py` — flujo de corrección por ejercicio, inyección del resultado de tests al payload, cierre determinístico por `compila: false`.
- `app/schemas/correccion.py` — DTOs de `resultado_tests` y de la respuesta por ejercicio.
- `app/schemas/rubrica.py` — `depende_de_ejecucion` por criterio (opcional, default falso).
- `app/integrations/gemini_correction_client.py` — sección de resultado de ejecución en el prompt.
- `app/models/materia.py` — `comision_integracion_id` (nullable FK).
- `app/models/comision.py` — `external_ref` (nullable), para el camino de cohortes.
- `alembic/versions/` — migración de esas dos columnas.

**Depende de**: `trabajos-practicos-y-external-ref` y `api-escritura-trabajos-practicos`.

**Bloqueante externo, no técnico**: el cliente pide una respuesta sobre la personería —si AI-Native y Active-IA son el mismo responsable de datos frente al consentimiento que firmaron los alumnos del piloto. Si no lo son, mandar código de un alumno es una cesión a un tercero y el consentimiento tiene que decirlo. **Eso bloquea el despliegue con datos reales y no depende de ninguna línea de código.** Ver `design.md`.
