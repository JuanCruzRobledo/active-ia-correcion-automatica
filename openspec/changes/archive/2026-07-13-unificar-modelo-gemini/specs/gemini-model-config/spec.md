## ADDED Requirements

### Requirement: Fuente única del modelo Gemini

El sistema SHALL usar `settings.GEMINI_MODEL` como la única fuente del nombre de modelo Gemini para todas las operaciones que dependan de él: validación de API key, corrección de entregas y generación de rúbricas. Ningún camino de código SHALL referenciar un nombre de modelo Gemini hardcodeado distinto de `settings.GEMINI_MODEL`.

#### Scenario: Validación de key y corrección usan el mismo modelo
- **WHEN** un tutor valida su API key y luego corrige una entrega
- **THEN** ambas operaciones usan el mismo modelo (`settings.GEMINI_MODEL`)
- **AND** si la key valida correctamente, el modelo contra el que se validó es el mismo que se usará para corregir

#### Scenario: Override por variable de entorno aplica a todo
- **WHEN** `GEMINI_MODEL` se sobreescribe por variable de entorno
- **THEN** la validación de API key usa el modelo sobreescrito
- **AND** la corrección real usa el mismo modelo sobreescrito

### Requirement: Validación de API key contra el modelo configurado

La validación de una API key de Gemini Studio SHALL construir la URL de health check a partir de `settings.GEMINI_MODEL`, y NO SHALL usar el literal hardcodeado `gemini-2.5-flash` ni ningún otro nombre de modelo fijo.

#### Scenario: La URL de validación referencia el modelo configurado
- **WHEN** se construye la URL de validación de API key
- **THEN** la URL contiene el valor de `settings.GEMINI_MODEL`
- **AND** la URL no contiene un nombre de modelo hardcodeado distinto del configurado

#### Scenario: Key que valida pero cuyo modelo no existe deja de ser falso positivo
- **WHEN** una API key autentica correctamente pero el modelo configurado no es accesible para esa cuenta
- **THEN** la validación refleja el estado real del modelo configurado en lugar de reportar un falso "válido" contra un modelo que no se usará en la corrección

### Requirement: Sin fallback muerto de nombre de modelo

El cliente de corrección Gemini SHALL asignar `self.model = settings.GEMINI_MODEL` directamente, sin un valor por defecto (`getattr(..., default)`) que nunca se dispara, ya que `GEMINI_MODEL` es un campo declarado del `Settings` y siempre está presente.

#### Scenario: El cliente de corrección no tiene default muerto
- **WHEN** se instancia el cliente de corrección Gemini
- **THEN** `self.model` toma directamente el valor de `settings.GEMINI_MODEL`
- **AND** no existe un literal de modelo por defecto que actúe como segunda fuente de verdad
