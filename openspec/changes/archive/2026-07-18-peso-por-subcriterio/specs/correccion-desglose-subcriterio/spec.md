## ADDED Requirements

### Requirement: Puntaje desglosado por subcriterio en la corrección con IA (v2)

Al corregir una entrega asociada a una rúbrica `schema_version = 2`, el sistema SHALL instruir a la IA para que asigne puntaje por subcriterio y para que el `puntaje_obtenido` de cada criterio sea la suma de los puntajes de sus subcriterios. El prompt enviado SHALL incluir, por cada subcriterio, su identificador y su peso en puntos (por ejemplo `[C2.1] (10 pts) ...`), además de sus evidencias. El comportamiento de corrección de rúbricas `schema_version = 1` SHALL permanecer idéntico al previo (subcriterios como checklist de evidencias, sin desglose de puntaje).

#### Scenario: Prompt v2 incluye peso por subcriterio
- **WHEN** se construye el prompt de corrección para una rúbrica `schema_version = 2`
- **THEN** cada subcriterio aparece con su identificador y su peso en puntos, y las instrucciones piden asignar puntaje por subcriterio con el criterio como suma de sus subcriterios

#### Scenario: Prompt v1 sin cambios
- **WHEN** se construye el prompt de corrección para una rúbrica `schema_version = 1`
- **THEN** el prompt es idéntico al comportamiento previo, sin reparto explícito por subcriterio

### Requirement: Esquema de respuesta de IA con subcriterios evaluados

Para rúbricas `schema_version = 2`, el `responseSchema`/`response_format` enviado a la IA SHALL incluir, dentro de cada criterio, un arreglo `subcriterios_evaluados` con `id`, `puntaje_obtenido`, `puntaje_maximo`, `estado` (`OK`/`WARNING`/`ERROR`) y `feedback`. El schema de parseo de la respuesta SHALL aceptar `subcriterios_evaluados` como opcional, tolerando su ausencia. El campo SHALL comportarse de forma consistente en el nivel de tipos con el nivel criterio (enteros redondeados al parsear la respuesta de la IA; decimales en la respuesta de la API interna).

#### Scenario: Respuesta v2 con subcriterios evaluados
- **WHEN** la IA devuelve una corrección para una rúbrica v2 con `subcriterios_evaluados` por criterio
- **THEN** el sistema parsea y conserva el desglose sin error

#### Scenario: Respuesta sin subcriterios evaluados
- **WHEN** la respuesta de la IA no incluye `subcriterios_evaluados` (rúbrica v1, o modelo que omite el campo)
- **THEN** el sistema parsea la corrección normalmente, sin el desglose

### Requirement: El cambio aplica a todos los proveedores de IA

La construcción del prompt y del esquema de respuesta con desglose por subcriterio SHALL aplicarse tanto al proveedor Gemini como a OpenRouter, que comparten los constructores de prompt.

#### Scenario: Corrección v2 con OpenRouter
- **WHEN** se corrige una entrega de rúbrica v2 usando el proveedor OpenRouter
- **THEN** el prompt y el esquema de respuesta incluyen el desglose por subcriterio igual que con Gemini

### Requirement: Persistencia del desglose sin migración de la corrección

El sistema SHALL persistir `subcriterios_evaluados` dentro de cada criterio en la columna JSONB `criterios_json` de la corrección, sin requerir una migración de esquema de la tabla de correcciones. La nota final SHALL seguir calculándose como la suma de `puntaje_obtenido` de los criterios (los subcriterios desglosan, no alteran el cálculo de la nota).

#### Scenario: Desglose persistido en JSONB
- **WHEN** se guarda una corrección v2 con desglose por subcriterio
- **THEN** `subcriterios_evaluados` queda almacenado dentro de cada criterio en `criterios_json`, sin migración de tabla

#### Scenario: La nota no cambia por el desglose
- **WHEN** se calcula la nota de una corrección v2 sin condición de desaprobación ni penalización
- **THEN** la nota es la suma de `puntaje_obtenido` de los criterios, igual que sin desglose

### Requirement: Visualización del desglose tolerante a su ausencia

El frontend de correcciones SHALL mostrar el desglose por subcriterio dentro de cada criterio cuando `subcriterios_evaluados` esté presente, y SHALL renderizar la corrección sin error cuando el campo esté ausente (correcciones viejas o de rúbricas v1).

#### Scenario: Corrección con desglose
- **WHEN** se visualiza una corrección cuyos criterios tienen `subcriterios_evaluados`
- **THEN** se muestra el detalle por subcriterio (puntaje y feedback) dentro del criterio

#### Scenario: Corrección sin desglose
- **WHEN** se visualiza una corrección cuyos criterios no tienen `subcriterios_evaluados`
- **THEN** la corrección se muestra igual que hoy, sin secciones de subcriterios y sin errores
