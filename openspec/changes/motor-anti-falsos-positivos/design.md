## Context

Estado verificado en el código al 2026-08-19:

- `Entrega.archivos_incluidos` (`app/models/entrega.py:80`, `ARRAY(String)`) se puebla en la consolidación (`entrega_service.py:171,331,445,1124`) y se expone en la API (`app/schemas/entrega.py:284`). **Cero referencias** en `app/services/correccion_service.py` y en `app/integrations/`.
- `_build_correction_payload` (`correccion_service.py:888-912`) manda `codigo`, `rubrica` (título, descripción, tipo, puntaje máximo, metadata, criterios, penalizaciones, condiciones, `schema_version`), `api_key` y `contexto` (materia, alumno). Nada sobre archivos.
- `_truncar_codigo` (L130-139, IA-015) capa el código y agrega un marcador textual dentro del propio blob. El modelo puede leer ese marcador, pero no hay ningún campo estructurado que le diga "esto vino truncado".
- Los `responseSchema` (`gemini_correction_client.py` L251, L282 y sus variantes v2) definen por criterio: `nombre`, `puntaje_obtenido`, `puntaje_maximo`, `estado`, `feedback`. **No hay campo de evidencia.**
- `Rubrica.metadata_json` (`app/models/rubrica.py:82`) es JSONB libre, descrito como "materia, carrera, lenguaje, framework, formato_entrega, etc.". Se pasa entero al prompt como `rubrica.metadata`. No hay noción de restricción/prohibición.
- Los builders de prompt los comparten Gemini y OpenRouter (`openrouter_client.corregir()` importa `_build_criterios_texto`).

Governance: **MEDIA** — lógica de negocio del motor de corrección. Implementar con checkpoints, surfaceando las decisiones no obvias.

## Goals / Non-Goals

**Goals**

- Que el motor no pueda descontar por un archivo que el sistema sabe que está entregado.
- Que cerrar un criterio tenga un costo: mostrar la línea que lo respalda.
- Que el backend pueda detectar mecánicamente cuándo el motor citó algo que no existe.
- Que la cátedra pueda declarar qué está prohibido, y que el motor no lo recomiende.

**Non-Goals**

- No se ejecuta código (eso es de AI-Native; ver `correccion-por-ejercicio-con-tests`).
- No se hace análisis estático ni parsing del código del alumno. La verificación de evidencia es una búsqueda de subcadena normalizada, no un AST.
- No se cambia el cálculo de la nota (eso es `nota-deterministica-penalizaciones`).
- No se elimina el truncado de código; se lo hace visible.

## Decisions

### D1. El inventario de archivos es un campo estructurado, no texto dentro del código

Se agrega al payload un bloque `entrega` con `archivos_incluidos` (la lista tal cual está en la base), `archivo_nombre`, `archivo_tipo`, y `codigo_truncado: bool` con `caracteres_originales` / `caracteres_enviados` cuando corresponda.

En el prompt se renderiza como sección propia, antes del código, con una regla dura:

> Los archivos listados en el INVENTARIO están entregados. NO descuentes puntaje por la ausencia de ningún archivo que figure ahí. Si el criterio requiere un archivo que NO figura en el inventario, entonces sí está ausente.

Rationale: el bug 1 es que el modelo infiere ausencia desde un blob concatenado. El inventario convierte una inferencia en un hecho. Y separar el flag de truncado del texto del marcador evita que el modelo lo confunda con código del alumno.

Alternativa descartada: dejar de truncar. El truncado existe por límite de contexto y costo (IA-015); sacarlo reabre un problema resuelto.

### D2. La evidencia es una cita textual, verificada por subcadena normalizada

Cada criterio (y cada subcriterio en v2) devuelve `evidencia`: un fragmento **literal** del código entregado (una a tres líneas) que respalda el puntaje.

El backend verifica la cita normalizando **whitespace** (colapsa espacios y tabs, ignora saltos de línea al comparar) y comparando por subcadena contra el código consolidado. No se normaliza el case ni la puntuación: `if puntajes[i] == 990` tiene que estar tal cual.

Cuando la cita **no** aparece:

- El criterio se degrada: `estado` pasa a `WARNING` y `puntaje_obtenido` se acota al 50% de su peso.
- Se anota en el feedback del criterio que la evidencia no pudo verificarse.
- Se emite log WARNING con el criterio y la cita no encontrada.

Rationale: es la única verificación mecánica posible sin ejecutar ni parsear. Y es asimétrica a propósito — **degrada, no anula**: un falso negativo de la verificación (por ejemplo, el modelo cita código real pero de la parte truncada) no debe desaprobar a nadie.

**Casos exentos de verificación**, donde citar es imposible o carece de sentido:

- Criterios cerrados como no cumplidos (`estado: ERROR` con puntaje 0): no hay qué citar.
- Correcciones de PDF (entregas manuscritas): no hay código consolidado contra el cual verificar. En ese camino la evidencia se pide igual, pero **no se verifica**.
- Código truncado: si `codigo_truncado` es verdadero, la cita no encontrada **solo se loguea**, sin degradar. El modelo pudo haber visto una parte que después no está en el blob guardado.

### D3. La regla presencia-vs-vínculo y la heurística de hardcodeo van en el prompt, con ejemplos negativos

Dos bloques nuevos de instrucciones, con los casos reales documentados:

- **Vínculo**: declarar/instanciar una entidad no cumple un criterio sobre esa entidad. Si el criterio dice "los productos se asocian a una categoría", la evidencia tiene que ser la línea donde la asociación ocurre, no la declaración de las dos clases. Ejemplo negativo explícito: 3 categorías y 10 productos existentes, ninguno vinculado, no es 100/100.
- **Hardcodeo**: un valor literal embebido que hace pasar un caso puntual sin implementar el algoritmo NO cumple el criterio. Ejemplo negativo explícito: `if puntajes[i] == 990` no es una búsqueda.

Rationale: son reglas de juicio, no verificables mecánicamente. Van al prompt porque es donde pueden actuar. Pero **el requisito de evidencia de D2 es lo que les da diente**: obligar a citar la línea del vínculo es mucho más difícil de falsear que afirmar que el vínculo existe.

Honestidad sobre el alcance: esto reduce los bugs 4 y 5, no los elimina. La eliminación viene con los tests ejecutados del change `correccion-por-ejercicio-con-tests`.

### D4. Las restricciones de cátedra son un campo de rúbrica, no un texto suelto

`metadata_json.restricciones`: lista de objetos `{ id, descripcion, alcance }` donde `alcance` es `prohibido_en_codigo` (penaliza si el alumno lo usa) o `no_recomendar` (el motor no puede sugerirlo, pero no penaliza si aparece).

Se renderiza en el prompt como restricción dura sobre las **recomendaciones**:

> Las siguientes construcciones están vedadas por la cátedra. NO las recomiendes en `recomendaciones` ni en el feedback de ningún criterio, aunque sean buena práctica general.

Rationale: el bug 6 no es que el modelo se equivoque — `try/except` **es** buena práctica en general. El modelo no tenía forma de saber que en Programación 1 está prohibido. El dato faltaba en la rúbrica, así que el arreglo es un campo, no un prompt más largo.

Va en `metadata_json` y no en una columna nueva: es JSONB existente, y `restricciones` es un concepto de la rúbrica, no de la corrección. Se agrega validación de shape en Pydantic para que no sea texto libre sin estructura.

**Ámbito de aplicación**: `prohibido_en_codigo` NO genera un descuento automático. Si la cátedra quiere que penalice, eso se expresa como una `Penalizacion` (que ya existe y, tras el change `nota-deterministica-penalizaciones`, sí descuenta). La restricción solo informa al juicio del motor y veda la recomendación.

### D5. La evidencia se le muestra al tutor; al alumno, solo si el tutor lo decide

En el modal de revisión del tutor, la evidencia se muestra siempre: es justamente lo que le permite auditar la corrección en segundos.

En el PDF de devolución al alumno, la evidencia **no** se incluye por default. Rationale: son fragmentos del propio código del alumno, así que no filtran nada, pero engordan el PDF sin agregar información que el alumno no tenga. Queda como posible flag futuro, fuera de alcance.

## Risks / Trade-offs

- **La verificación de evidencia puede dar falsos negativos** (el modelo cita código real reformateado por él mismo). Mitigación: normalización de whitespace, degradación en lugar de anulación, y exención total cuando el código viene truncado. Se instrumenta con log para medir la tasa real antes de endurecer la regla.
- **El prompt crece.** Más instrucciones compiten por atención con la rúbrica. Mitigación: las reglas nuevas van agrupadas y con ejemplos negativos cortos, no como párrafos sueltos; se mide el cambio en tokens de entrada (ya hay columnas `tokens_entrada`/`tokens_salida` en `correcciones` desde IA-014).
- **Pedir evidencia aumenta los tokens de salida** y por lo tanto el costo por corrección. Es medible con las mismas columnas y hay que reportarlo.
- **Las restricciones dependen de que alguien las cargue.** Una rúbrica sin restricciones se comporta exactamente como hoy. Mitigación: cargar las de Programación 1 (el caso del bug 6) como parte de la verificación de este change.

## Migration Plan

Sin migración de esquema. `restricciones` y `evidencia` viven en JSONB existentes y son opcionales, así que rúbricas y correcciones previas siguen funcionando sin tocarlas.

Orden: (1) inventario de archivos — es el arreglo del bug con víctima concreta y no depende de nada; (2) evidencia + verificación; (3) reglas de vínculo y hardcodeo; (4) restricciones de cátedra + frontend.

## Open Questions

- ¿El umbral de degradación por evidencia no verificada es 50% del peso del criterio, o directamente `estado: WARNING` sin tocar el puntaje en la primera versión? La propuesta arranca con 50% pero la instrumentación del primer mes debería decidirlo con datos.
- ¿Las restricciones se heredan de la materia hacia todas sus rúbricas, o se declaran rúbrica por rúbrica? La propuesta las pone en la rúbrica (más simple, sin herencia). Si en Programación 1 hay que repetirlas en cada TP, conviene revisarlo.
