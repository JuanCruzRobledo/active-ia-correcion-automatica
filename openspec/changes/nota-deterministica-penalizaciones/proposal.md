## Why

Dos bugs reportados el 2026-08-17 producen **una nota plausible y mal**, que es peor que un error visible. Los dos salen de la misma causa raíz: el backend calcula la nota parcialmente de forma determinística y delega el resto en la aritmética del modelo de IA.

**Bug 2 — las penalizaciones declaradas en la rúbrica no bajan la nota.** Está escrito literalmente en el código (`app/services/correccion_service.py:156-160`):

```python
"""IA-001: filtra las penalizaciones informadas por el modelo a las que existen
en la rúbrica (defensa contra ids alucinados). No alteran la nota (ya están en
los criterios); son solo auditoría/display."""
```

`_nota_deterministica` suma `puntaje_obtenido` de los criterios y **nunca aplica `descuento_porcentaje`**. La aplicación del descuento vive únicamente en el texto del prompt, que le pide a la IA que baje el puntaje del criterio afectado. Cuando la IA no lo hace, nadie lo corrige. Caso medido: la rúbrica declaraba "reducción del 30% del total", la nota final fue la suma limpia `48+14+15+10+0 = 87` cuando con el descuento daba ~61.

**Bug 3 — el desglose no cierra con sus subcriterios.** En el mismo caso, el criterio C5 figuraba `0/10` mientras sus `subcriterios_evaluados` sumaban 5. El change `peso-por-subcriterio` (archivado) introdujo el desglose v2 e instruyó a la IA para que "el `puntaje_obtenido` de cada criterio sea la suma de los puntajes de sus subcriterios", pero **esa invariante nunca se verifica ni se impone en el backend**: se persiste lo que devuelve el modelo, criterio y subcriterios por separado.

Es la misma clase de error dos veces: una regla aritmética que la rúbrica declara, delegada a un LLM. El proyecto ya resolvió este patrón bien una vez — las *condiciones de desaprobación* SÍ se aplican determinísticamente (`min(suma, techo)`, con el techo tomado de la rúbrica y no del modelo). Este change extiende ese mismo criterio a las penalizaciones y al desglose.

## What Changes

- **Las penalizaciones se aplican en el backend, no en el prompt.** `_nota_deterministica` calcula `nota = suma_criterios − Σ(descuentos)`, tomando `descuento_porcentaje` de la **rúbrica** (fuente autoritativa), no de la respuesta del modelo. El modelo pasa a informar **qué** penalización se incumplió; **cuánto** descuenta lo decide el backend.
- **El criterio se recomputa como suma de sus subcriterios en rúbricas v2.** Si `schema_version >= 2` y el criterio trae `subcriterios_evaluados`, `puntaje_obtenido` del criterio SHALL ser `sum(subcriterios)`, ignorando el número que haya devuelto el modelo. Se registra la discrepancia en log para observabilidad.
- **El prompt deja de pedirle a la IA que aplique el descuento.** Pasa a pedirle únicamente que **declare** las penalizaciones incumplidas (los ids). Esto elimina el doble descuento: hoy, si la IA sí baja el criterio y mañana el backend también descuenta, se penalizaría dos veces.
- **Trazabilidad completa de la nota.** `nota_antes_penalizaciones` pasa a poblarse siempre que haya penalización o condición aplicada (hoy solo se llena con condición de desaprobación), y la corrección persiste el detalle de cada descuento aplicado (id, descripción, puntos descontados).
- **El PDF de devolución muestra el cálculo.** Suma de criterios → descuentos aplicados → techo por condición → nota final.
- **BREAKING de comportamiento (intencional):** las correcciones nuevas sobre rúbricas con penalizaciones darán notas **más bajas** que hoy. Es el arreglo, no un efecto colateral. Las correcciones ya persistidas **no** se recalculan.

## Capabilities

### New Capabilities

- `correccion-nota-deterministica`: cálculo de la nota final íntegramente en el backend — suma de criterios, criterio recomputado como suma de subcriterios en v2, descuentos por penalización tomados de la rúbrica, techo por condición de desaprobación, y trazabilidad del cálculo en la respuesta y en el PDF.

### Modified Capabilities

- `correccion-desglose-subcriterio`: la invariante "criterio = suma de subcriterios", hoy declarada solo en el prompt, pasa a imponerse en el backend.
- `rubrica-peso-subcriterio`: sin cambio de requisitos; se referencia porque define el contrato de pesos que este change usa como fuente autoritativa.

## Impact

**Backend**
- `app/services/correccion_service.py` — `_nota_deterministica` (L162-193), `_penalizaciones_validas` (L156-160), y el armado de `criterios_json` que persiste el desglose.
- `app/integrations/gemini_correction_client.py` — texto de instrucciones de penalización en el prompt-builder (dejar de pedir que aplique el descuento).
- `app/integrations/openrouter_client.py` — comparte los builders; se verifica que hereda el cambio.
- `app/schemas/correccion.py` — nuevo campo de detalle de descuentos aplicados en la respuesta.
- `app/services/pdf_service.py` — bloque de desglose del cálculo de la nota.

**Sin migración de esquema**: el detalle de descuentos se persiste dentro de `criterios_json` (JSONB) o en `penalizaciones_aplicadas` (ya existe como `ARRAY(Text)`); definir en design cuál.

**Datos existentes**: no se recalculan correcciones ya hechas.
