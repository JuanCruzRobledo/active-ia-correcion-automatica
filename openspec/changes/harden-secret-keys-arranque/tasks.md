> **Gobernanza CRÍTICA (Seguridad):** la fase de apply NO es autónoma. Cada línea del validador de producción (tareas del grupo 3) debe mostrarse al usuario y esperar aprobación explícita ANTES de escribirse. Los tests (grupo 2) se escriben primero (TDD, RED).

## 1. Preparación

- [x] 1.1 Confirmar el directorio de tests `backend/tests/unit/core/` (crearlo con `__init__.py` si no existe) y revisar el patrón de tests existentes del proyecto para respetar estilo
- [x] 1.2 Correr la suite existente de `config`/`core` como safety net y capturar el baseline ("N tests passing")

## 2. Tests (RED — escribir antes del código de producción)

- [x] 2.1 Test: `Settings(DEBUG=False, SECRET_KEY=<default>, ENCRYPTION_KEY=<real>)` lanza `ValidationError`
- [x] 2.2 Test: `Settings(DEBUG=False, ENCRYPTION_KEY=<default>, SECRET_KEY=<real>)` lanza `ValidationError`
- [x] 2.3 Test: `Settings(DEBUG=True, SECRET_KEY=<default>, ENCRYPTION_KEY=<default>)` construye sin error (defaults permitidos en dev)
- [x] 2.4 Test: `Settings(DEBUG=False, SECRET_KEY=<real>, ENCRYPTION_KEY=<real>)` construye sin error
- [x] 2.5 Test: el mensaje de error para `SECRET_KEY` nombra `SECRET_KEY` e incluye `openssl rand -hex 32`
- [x] 2.6 Test: el mensaje de error para `ENCRYPTION_KEY` nombra `ENCRYPTION_KEY` e incluye `Fernet.generate_key()`
- [x] 2.7 Ejecutar los tests y confirmar que fallan (RED) porque el validador aún no existe

## 3. Implementación del validador (GREEN — requiere aprobación humana línea por línea)

- [x] 3.1 Extraer los defaults a constantes reutilizables (`_DEFAULT_SECRET_KEY`, `_DEFAULT_ENCRYPTION_KEY`) y usarlas como default de los campos en `Settings` — MOSTRAR diff y esperar OK
- [x] 3.2 Agregar `@model_validator(mode="after")` en `Settings` que, si `DEBUG is False`, verifica `SECRET_KEY`/`ENCRYPTION_KEY` contra sus defaults y lanza `ValueError` acumulando todas las claves inseguras — MOSTRAR diff y esperar OK
- [x] 3.3 Redactar el mensaje de error con guía de remediación por clave (`openssl rand -hex 32`, `Fernet.generate_key()`) — MOSTRAR diff y esperar OK
- [x] 3.4 Ejecutar los tests del grupo 2 y confirmar GREEN

## 4. Verificación y cierre

- [x] 4.1 TRIANGULATE: confirmar que hay al menos happy-path + edge case por comportamiento y que ningún test es tautológico
- [x] 4.2 REFACTOR si aplica (nombres/duplicación) manteniendo los tests en verde
- [x] 4.3 Correr la suite completa de backend (`pytest`) y confirmar que no se rompió nada preexistente
- [ ] 4.4 Verificar/actualizar que `.env.example` documente la generación de `SECRET_KEY` y `ENCRYPTION_KEY`
- [x] 4.5 Verificación manual: intentar arrancar con `DEBUG=False` y defaults → la app debe abortar con el mensaje accionable
