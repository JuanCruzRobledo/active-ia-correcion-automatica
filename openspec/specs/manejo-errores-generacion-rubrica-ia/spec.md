# manejo-errores-generacion-rubrica-ia Specification

## Purpose
TBD - created by archiving change capturar-errores-gemini-rubrica-ia. Update Purpose after archive.
## Requirements
### Requirement: Manejo de API key inválida en generación de rúbrica IA

El servicio de generación de rúbrica desde PDF SHALL capturar `APIKeyInvalidError` proveniente del cliente de IA y responder con un HTTP 402 cuyo cuerpo incluya el código `GEMINI_API_KEY_INVALID` y el mensaje del catálogo de errores (`mensaje_error`). El sistema SHALL marcar la API key de Gemini del usuario como inválida en la base de datos (`gemini_api_key_valid = False`).

#### Scenario: El cliente de IA reporta API key inválida
- **WHEN** el cliente de IA lanza `APIKeyInvalidError` al generar la rúbrica
- **THEN** el servicio responde con HTTP 402 con `error_code = "GEMINI_API_KEY_INVALID"` y el mensaje del catálogo
- **AND** NO responde con un HTTP 500 crudo

#### Scenario: Se marca la API key como inválida
- **WHEN** se produce `APIKeyInvalidError` durante la generación de rúbrica
- **THEN** el campo `gemini_api_key_valid` del usuario queda en `False` en la base de datos

### Requirement: Manejo de cuota/rate limit en generación de rúbrica IA

El servicio SHALL capturar `QuotaExceededError` y responder con un HTTP 429 cuyo cuerpo incluya el código `GEMINI_RATE_LIMIT` y el mensaje del catálogo.

#### Scenario: El proveedor alcanza el límite de uso
- **WHEN** el cliente de IA lanza `QuotaExceededError` al generar la rúbrica
- **THEN** el servicio responde con HTTP 429 con `error_code = "GEMINI_RATE_LIMIT"` y el mensaje del catálogo
- **AND** NO responde con un HTTP 500 crudo

### Requirement: Manejo de modelo sobrecargado en generación de rúbrica IA

El servicio SHALL capturar `ModelOverloadedError` y responder con un HTTP 503 cuyo cuerpo incluya el código `GEMINI_OVERLOADED` y el mensaje del catálogo.

#### Scenario: El modelo del proveedor está sobrecargado
- **WHEN** el cliente de IA lanza `ModelOverloadedError` al generar la rúbrica
- **THEN** el servicio responde con HTTP 503 con `error_code = "GEMINI_OVERLOADED"` y el mensaje del catálogo

### Requirement: Manejo de créditos insuficientes en generación de rúbrica IA

El servicio SHALL capturar `InsufficientCreditsError` y responder con un HTTP 402 cuyo cuerpo incluya el código `SIN_CREDITOS` y el mensaje del catálogo.

#### Scenario: La cuenta del proveedor no tiene créditos
- **WHEN** el cliente de IA lanza `InsufficientCreditsError` al generar la rúbrica
- **THEN** el servicio responde con HTTP 402 con `error_code = "SIN_CREDITOS"` y el mensaje del catálogo

### Requirement: Preservación del manejo de errores genéricos y de timeout

El servicio SHALL seguir capturando `N8NTimeoutError` y `N8NError` (fallback genérico) mapeándolos a HTTP 502, sin regresión respecto al comportamiento actual.

#### Scenario: Timeout del servicio de IA
- **WHEN** el cliente de IA lanza `N8NTimeoutError`
- **THEN** el servicio responde con HTTP 502 y un mensaje de timeout

#### Scenario: Error genérico del servicio de IA
- **WHEN** el cliente de IA lanza `N8NError` (fallback genérico, no una subclase de `GeminiError`)
- **THEN** el servicio responde con HTTP 502 con el mensaje de error del servicio de IA

