# secret-key-hardening Specification

## Purpose
TBD - created by archiving change harden-secret-keys-arranque. Update Purpose after archive.
## Requirements
### Requirement: Fail-fast ante SECRET_KEY o ENCRYPTION_KEY default en producción

El sistema SHALL abortar el arranque de la aplicación cuando `DEBUG` sea `False` y `SECRET_KEY` o `ENCRYPTION_KEY` conserven su valor default literal (`"change-me-in-production-use-openssl-rand-hex-32"` y `"change-me-in-production-use-fernet-generate-key"` respectivamente). La validación SHALL ejecutarse durante la construcción de `Settings`, de modo que ninguna instancia de la aplicación pueda quedar operativa con secretos conocidos en producción.

#### Scenario: Arranque bloqueado con SECRET_KEY default en producción
- **WHEN** `DEBUG=False` y `SECRET_KEY` tiene su valor default literal
- **THEN** la construcción de `Settings` lanza una excepción y la aplicación no arranca

#### Scenario: Arranque bloqueado con ENCRYPTION_KEY default en producción
- **WHEN** `DEBUG=False` y `ENCRYPTION_KEY` tiene su valor default literal
- **THEN** la construcción de `Settings` lanza una excepción y la aplicación no arranca

#### Scenario: Arranque permitido con claves reales en producción
- **WHEN** `DEBUG=False` y tanto `SECRET_KEY` como `ENCRYPTION_KEY` tienen valores distintos de sus defaults
- **THEN** la construcción de `Settings` se completa sin error y la aplicación arranca normalmente

### Requirement: Guía de remediación en el mensaje de error

El mensaje de la excepción de arranque SHALL indicar de forma clara cuál clave es insegura y cómo generar un valor real: `openssl rand -hex 32` para `SECRET_KEY` y `Fernet.generate_key()` para `ENCRYPTION_KEY`. El operador MUST poder remediar la falla leyendo únicamente el mensaje, sin consultar el código fuente.

#### Scenario: El mensaje nombra la clave y su comando de generación
- **WHEN** el arranque falla por `SECRET_KEY` default
- **THEN** el mensaje de error nombra `SECRET_KEY` e incluye la instrucción `openssl rand -hex 32`

#### Scenario: El mensaje cubre ENCRYPTION_KEY
- **WHEN** el arranque falla por `ENCRYPTION_KEY` default
- **THEN** el mensaje de error nombra `ENCRYPTION_KEY` e incluye la instrucción `Fernet.generate_key()`

### Requirement: Defaults permitidos en desarrollo

El sistema SHALL permitir el arranque con los valores default de `SECRET_KEY` y `ENCRYPTION_KEY` cuando `DEBUG` sea `True`, para no romper el flujo de desarrollo local. La validación estricta SHALL aplicarse únicamente en modo producción (`DEBUG=False`).

#### Scenario: Arranque permitido con defaults en desarrollo
- **WHEN** `DEBUG=True` y `SECRET_KEY`/`ENCRYPTION_KEY` conservan sus valores default
- **THEN** la construcción de `Settings` se completa sin error y la aplicación arranca

