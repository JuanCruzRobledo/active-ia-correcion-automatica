## Why

`backend/app/core/config.py` define `SECRET_KEY` y `ENCRYPTION_KEY` con valores default hardcodeados y públicos (`"change-me-in-production-..."`), y no existe ningún validador que impida arrancar en producción con esos defaults. Como el default está en el repositorio, un atacante que lo conozca puede **forjar JWT de ADMIN** (firma HS256 con `SECRET_KEY`) y **descifrar todas las API keys de Gemini/OpenRouter y las contraseñas de Moodle** almacenadas (Fernet/AES-256 con `ENCRYPTION_KEY`). Es el hallazgo de auditoría **SEC-003, severidad Crítica**: hay que cerrar el arranque inseguro antes de que un despliegue de producción quede expuesto por olvido de configuración.

## Gobernanza — CRÍTICA (Seguridad)

Este change pertenece al dominio **Seguridad** y su nivel de gobernanza es **CRÍTICO** según el modelo JR Stack ("Analysis only; no code written without explicit human approval").

- La fase de `apply` de este change **NO debe ejecutarse de forma autónoma**.
- **Cada línea de código de producción debe mostrarse al usuario y esperar aprobación explícita ANTES de escribirla.** Aprobar este proposal en general **no** habilita a escribir código sin revisión línea por línea.
- El esfuerzo estimado es **S** (small): un validador acotado en un único archivo más su test.

## What Changes

- Se agrega un validador Pydantic en `Settings` (`backend/app/core/config.py`) que, cuando `DEBUG=False` (producción), **aborta el arranque de la aplicación** si `SECRET_KEY` o `ENCRYPTION_KEY` siguen teniendo su valor default literal.
- El error de arranque incluye un **mensaje claro y accionable** que indica cómo generar claves reales: `openssl rand -hex 32` para `SECRET_KEY` y `Fernet.generate_key()` para `ENCRYPTION_KEY`.
- En modo desarrollo (`DEBUG=True`) los defaults se siguen permitiendo para no romper el flujo local; la validación es estricta solo en producción.
- Se agregan tests en `backend/tests/unit/core/` que verifican: (a) arranque falla con defaults + `DEBUG=False`, (b) arranque permitido con defaults + `DEBUG=True`, (c) arranque permitido con claves reales + `DEBUG=False`.
- **No** hay cambios de comportamiento de la API ni de datos: el único efecto observable es un fallo temprano de arranque ante una configuración de producción insegura (fail-fast).

## Capabilities

### New Capabilities
- `secret-key-hardening`: Validación de arranque (fail-fast) que impide desplegar la aplicación en producción con `SECRET_KEY` o `ENCRYPTION_KEY` en sus valores default, con guía de remediación en el mensaje de error.

### Modified Capabilities
<!-- Ninguna: no cambian requisitos de capacidades existentes. -->

## Impact

- **Código afectado (escritura):** `backend/app/core/config.py` (nuevo validador en `Settings`).
- **Tests nuevos:** `backend/tests/unit/core/` (test del validador de arranque).
- **Consumidores de estas settings (solo contexto de impacto, no se modifican):**
  - `backend/app/core/security.py:112,141` — JWT firmado con `SECRET_KEY`.
  - `backend/app/core/security.py:164` — Fernet inicializado con `ENCRYPTION_KEY`.
  - `backend/app/services/devolucion_link_service.py:41,48` — JWT de links públicos firmado con `SECRET_KEY`.
- **Operaciones / despliegue:** un entorno de producción que hoy arranca con defaults dejará de arrancar hasta configurar claves reales en `.env`. Es el efecto buscado (fail-fast), pero requiere comunicar el cambio al operador y verificar que `.env.example` documente la generación de claves.
- **Dependencias:** ninguna nueva; `cryptography.Fernet` ya es dependencia del proyecto.
