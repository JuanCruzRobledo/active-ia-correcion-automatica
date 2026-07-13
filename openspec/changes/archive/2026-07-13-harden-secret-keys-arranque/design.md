## Context

`backend/app/core/config.py` centraliza la configuración vía `pydantic-settings`. Hoy `SECRET_KEY` (línea 53) y `ENCRYPTION_KEY` (línea 62) tienen defaults hardcodeados y públicos. Los únicos `@field_validator` presentes son `parse_cors_origins` y `parse_allowed_extensions`; no hay ninguna validación cruzada que compare estos secretos contra su default ni que dependa de `DEBUG`.

Estos valores alimentan rutas críticas de seguridad:
- `security.py:112,141` — firma/verificación de JWT (HS256) con `SECRET_KEY`.
- `security.py:164` — inicialización de Fernet con `ENCRYPTION_KEY` (cifra API keys de Gemini/OpenRouter y contraseñas de Moodle).
- `devolucion_link_service.py:41,48` — JWT de links públicos con `SECRET_KEY`.

Con el default conocido, un atacante forja JWT de ADMIN y descifra todos los secretos almacenados (auditoría **SEC-003, Crítica**).

## Gobernanza — CRÍTICA (dominio Seguridad)

Nivel de gobernanza **CRÍTICO** (JR Stack): "Analysis only; no code written without explicit human approval."

- La fase de `apply` **NO se ejecuta de forma autónoma**.
- **Cada línea de código de producción (el validador en `config.py`) debe mostrarse al usuario y esperar su aprobación explícita ANTES de escribirse.** Aprobar el proposal en general NO habilita a escribir el código.
- Los tests pueden escribirse siguiendo el ciclo TDD, pero el paso GREEN (escribir el validador de producción) requiere el visto bueno humano línea por línea.
- Esfuerzo estimado: **S**.

## Goals / Non-Goals

**Goals:**
- Impedir (fail-fast, en tiempo de construcción de `Settings`) que la app arranque en producción con `SECRET_KEY` o `ENCRYPTION_KEY` default.
- Emitir un mensaje de error accionable con el comando exacto de generación por cada clave.
- Mantener el flujo de desarrollo local intacto (defaults permitidos cuando `DEBUG=True`).

**Non-Goals:**
- No se valida la *fortaleza* de las claves reales (longitud/entropía/formato Fernet válido); solo se rechaza el valor default literal. La validación de formato Fernet queda fuera de alcance.
- No se rotan ni regeneran claves existentes.
- No se modifican `security.py` ni `devolucion_link_service.py` (solo se los cita como impacto).
- No se cambia el comportamiento de ninguna API ni del modelo de datos.

## Decisions

### D1: `@model_validator(mode="after")` sobre un `field_validator` por campo
Se usará un `model_validator(mode="after")` en `Settings` porque la regla depende de **tres campos a la vez** (`DEBUG`, `SECRET_KEY`, `ENCRYPTION_KEY`). Un `field_validator` por campo no tiene acceso garantizado a `DEBUG` ya validado y obligaría a duplicar la lógica. `mode="after"` corre cuando todos los campos ya están poblados y tipados.
- **Alternativa considerada:** `field_validator` con `ValidationInfo.data` para leer `DEBUG` — descartada por orden de evaluación frágil (depende de que `DEBUG` se declare antes) y por duplicación entre las dos claves.

### D2: Rechazo por prefijo `change-me-in-production`, no por igualdad literal

> **Revisado durante apply.** La versión original de D2 exigía comparar contra el valor default literal de `config.py`. Al implementarlo se descubrió que **`.env.example` usa `change-me-in-production`, que NO coincide con los defaults de `config.py`** (`change-me-in-production-use-openssl-rand-hex-32` / `...-use-fernet-generate-key`). Con igualdad literal, el vector de ataque más probable de SEC-003 —el operador copia `.env.example` a `.env` y despliega sin tocar las claves— **pasaba el validador y arrancaba**. La comparación literal cerraba el caso improbable y dejaba abierto el real.

Se rechaza cualquier `SECRET_KEY`/`ENCRYPTION_KEY` que **empiece con** `_PREFIJO_SECRETO_INSEGURO = "change-me-in-production"`. Cubre de una vez los defaults de `config.py`, el placeholder de `.env.example` y cualquier variante futura del mismo prefijo.

Es técnicamente una heurística, pero **el falso positivo que la D2 original quería evitar tiene probabilidad cero**: ninguna clave generada con `openssl rand -hex 32` (hex) ni con `Fernet.generate_key()` (base64) puede empezar con `change-me-in-production`. No hay clave real legítima que este prefijo rechace.

- **Alternativa considerada:** igualdad literal contra ambos valores (default + placeholder de `.env.example`) — descartada por frágil: cada nuevo placeholder que alguien agregue a un `.env.*` habría que recordar sumarlo a la lista. El prefijo los cubre a todos por construcción.
- **Alternativa considerada:** validar entropía/longitud mínima — mayor alcance, riesgo de romper entornos legítimos, fuera del objetivo puntual del hallazgo.

### D5: Mensaje de error sin acentos (ASCII)
El mensaje del `ValueError` se redacta sin tildes (`produccion`, `Configura`, `Genera`). Se lee en logs de deploy (EasyPanel), contenedores con locale mínimo y consolas Windows (cp1252), donde los acentos UTF-8 salen corruptos. El spec exige que el operador pueda remediar la falla **leyendo únicamente el mensaje**: un mensaje ilegible en el entorno donde efectivamente se lo lee no cumple ese requisito.

### D3: Gate por `DEBUG=False` (producción)
La validación solo aborta cuando `DEBUG=False`. `DEBUG` ya es la señal de entorno del proyecto (default `False`). Esto mantiene DX local y hace estricta la producción.
- **Alternativa considerada:** una variable `ENVIRONMENT` dedicada — se descarta por no existir hoy y por no querer ampliar la superficie de configuración en un change S.

### D4: Excepción que aborta el arranque
El validador lanza `ValueError` (Pydantic lo envuelve en `ValidationError` al construir `Settings`), lo que hace fallar `get_settings()` y, por lo tanto, el import de `settings` en el arranque de la app. Fail-fast real: la app no llega a servir requests. El mensaje enumera todas las claves inseguras detectadas (no solo la primera) con su comando de remediación.

## Risks / Trade-offs

- **Un despliegue de producción que hoy arranca con defaults dejará de arrancar** → Es el efecto buscado; mitigar comunicando el cambio al operador y verificando que `.env.example` documente `openssl rand -hex 32` y `Fernet.generate_key()`.
- **`settings` es un singleton a nivel de módulo (`get_settings()` con `lru_cache`)** → el fallo ocurre en el primer import; los tests deben instanciar `Settings(...)` directamente (o limpiar el cache) para no chocar con el singleton ya construido. Se contempla en tasks.
- **Falso sentido de seguridad**: rechazar el default no garantiza una clave fuerte (Non-Goal explícito). Se documenta para no sobre-prometer.
- **Riesgo de gobernanza**: escribir el validador sin aprobación humana violaría la política CRÍTICA → mitigar respetando el checkpoint de `apply` (mostrar el diff del validador y esperar OK).

## Migration Plan

1. (apply, con aprobación humana línea por línea) Agregar constantes de default reutilizables + `model_validator(mode="after")` en `Settings`.
2. Ejecutar los tests de `backend/tests/unit/core/` (TDD: RED antes de escribir el validador).
3. Verificar/actualizar que `.env.example` documente la generación de ambas claves.
4. Comunicar al operador que producción exige claves reales antes del próximo deploy.

**Rollback:** revertir el commit del validador restablece el comportamiento anterior sin efectos de datos (cambio puramente de arranque, sin migración de schema).

## Open Questions

- ¿Se desea, en un change futuro, validar también el *formato* de `ENCRYPTION_KEY` (Fernet base64 de 32 bytes) además de rechazar el default? Fuera de alcance aquí.
