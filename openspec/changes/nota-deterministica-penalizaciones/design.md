## Context

Active-IA corrige entregas con IA (Gemini directo y OpenRouter, builders compartidos) contra rúbricas jerárquicas en JSONB. Estado verificado en el código al 2026-08-19:

- `_nota_deterministica` (`app/services/correccion_service.py:162-193`) calcula `suma = sum(criterio.puntaje_obtenido)`, aplica `min(suma, techo)` **solo** si el modelo declaró una condición de desaprobación cuyo id existe en la rúbrica, y devuelve `penalizaciones` como lista de ids validados.
- `_penalizaciones_validas` (L156-160) filtra ids alucinados y su docstring declara explícitamente: *"No alteran la nota (ya están en los criterios); son solo auditoría/display."*
- `_build_penalizaciones_texto` (`gemini_correction_client.py:143-155`) le pide al modelo aplicar el descuento *"reduciendo el `puntaje_obtenido` del criterio afectado (NO como descuento global sobre la nota)"*.
- El bloque IMPORTANTE del prompt (L772-774) refuerza: *"La nota SIEMPRE es la suma exacta de `puntaje_obtenido` de todos los criterios (las penalizaciones ya están aplicadas dentro de cada criterio, nunca como descuento posterior)"*.
- `Penalizacion` (`app/schemas/rubrica.py:137-165`) tiene `id` (patrón `^P[0-9]+$`), `descripcion` y `descuento_porcentaje` (0-100). **No tiene ningún campo que la ancle a un criterio.**
- El desglose v2 (`subcriterios_evaluados`) se persiste dentro de `criterios_json` tal cual lo devuelve el modelo; el spec archivado `correccion-desglose-subcriterio` declara la invariante "criterio = suma de subcriterios" únicamente como instrucción de prompt.

Restricciones del proyecto: Clean Architecture (Routers → Services → Repositories); sin lógica de negocio en routers; máx 500 LOC/archivo; permisos por rol en cada endpoint. Governance: **ALTA** — este change modifica el número que se le informa a un alumno como su nota. Se propone y se espera revisión explícita del diff antes de aplicar.

## Goals / Non-Goals

**Goals**

- Que ninguna regla aritmética declarada en la rúbrica dependa de que un LLM la ejecute.
- Que la nota sea reproducible: dados los mismos criterios evaluados y la misma rúbrica, la nota final es siempre la misma.
- Que el cálculo sea auditable de punta a punta por el tutor (y por el alumno en el PDF).
- Eliminar el riesgo de doble descuento entre prompt y backend.

**Non-Goals**

- No se recalculan correcciones ya persistidas (ver D5).
- No se cambia la semántica de las condiciones de desaprobación (ya es determinística y correcta).
- No se toca el modelo de datos de `rubricas` ni de `correcciones` (sin migración).
- No se agrega un campo `criterio_id` a `Penalizacion` (ver D1, alternativa descartada).

## Decisions

### D1. La base del descuento es la suma de criterios, no un criterio puntual

`Penalizacion` **no tiene forma de indicar a qué criterio aplica** — el schema solo tiene `id`, `descripcion` y `descuento_porcentaje`. Sin embargo el prompt actual le pide al modelo aplicarlo "al criterio afectado", que el modelo tiene que adivinar. Esa ambigüedad es parte de la causa del bug.

Decisión: `descuento_porcentaje` se interpreta como **porcentaje de la suma de criterios**, aplicado después de sumar y antes del techo por condición de desaprobación:

```
suma        = Σ criterio.puntaje_obtenido
descuento   = Σ (suma × p.descuento_porcentaje / 100)  por cada p declarada y válida
nota_penada = max(0, suma − descuento)
nota_final  = min(nota_penada, techo)   si hay condición de desaprobación
            = nota_penada               si no
```

Rationale: es la única lectura no ambigua con el schema actual, coincide con lo que la rúbrica del caso reportado dice textualmente ("reducción del 30% **del total**"), y reproduce el número esperado del informe (87 → ~61 con 30%).

Alternativa descartada: agregar `criterio_id` a `Penalizacion` y descontar sobre ese criterio. Es más expresivo, pero es un cambio de contrato de rúbrica que rompe las rúbricas existentes y obliga a un backfill manual de decenas de rúbricas en producción. Queda anotado como evolución futura, fuera de este change.

**Redondeo**: se usa `Decimal` en toda la cadena (ya es el tipo de `Correccion.nota`, `Numeric(5,2)`), cuantizando a 2 decimales **una sola vez al final**, no en cada descuento.

### D2. El modelo declara, el backend descuenta

El prompt deja de instruir "aplicá el descuento bajando el criterio" y pasa a instruir "listá en `penalizaciones_aplicadas` los ids de las penalizaciones que el alumno incumplió; **no ajustes ningún puntaje por ellas**".

Rationale: si el modelo bajara el criterio Y el backend descontara, la penalización se aplicaría dos veces. El único punto donde el descuento se materializa tiene que ser el backend. `_penalizaciones_validas` se mantiene tal cual: sigue siendo el filtro de entrada contra ids alucinados.

**Nota de riesgo aceptada**: el modelo puede seguir bajando el criterio por su cuenta pese a la instrucción. Eso produciría un descuento de más, no de menos — falla hacia la nota baja, no hacia el falso aprobado. La mitigación real es el log de D4, que hace visible la discrepancia.

### D3. En rúbricas v2, el criterio se recomputa como suma de sus subcriterios

Si `rubrica.schema_version >= 2` y el criterio trae `subcriterios_evaluados` no vacío:

```
criterio.puntaje_obtenido = Σ subcriterio.puntaje_obtenido
```

El número que devolvió el modelo para el criterio se **descarta** (se registra en log si difiere). En v1, o cuando el criterio no trae desglose, `puntaje_obtenido` se respeta tal cual — camino intacto.

Rationale: la invariante ya está declarada en el spec `correccion-desglose-subcriterio` como instrucción de prompt; acá deja de ser una sugerencia. Y el recomputo va **antes** de la suma, así que arregla el bug 3 y de paso hace la nota total consistente con el desglose que ve el alumno.

**Techo por subcriterio**: cada subcriterio se capa a su `puntaje_maximo` antes de sumar, y la suma resultante se capa al `peso` del criterio en la rúbrica. Sin eso, un modelo que alucine un subcriterio de más inflaría el criterio por encima de su peso.

### D4. Trazabilidad: el cálculo se persiste, no se reconstruye

La corrección persiste el detalle del cálculo para que el tutor pueda auditarlo sin releer la rúbrica:

- `nota_antes_penalizaciones` (columna existente, `Numeric(5,2)`) pasa a llenarse **siempre que haya descuento o techo**, no solo con condición de desaprobación. Hoy queda `NULL` cuando hay penalización, que es justo el caso donde más se necesita.
- El detalle por descuento (`id`, `descripcion`, `porcentaje`, `puntos_descontados`) se guarda dentro de `criterios_json` bajo una clave hermana de `criterios` (por ejemplo `calculo_nota`). **No se toca `penalizaciones_aplicadas`** (`ARRAY(Text)`), que sigue guardando solo los ids: cambiarle el shape rompería el PDF y el frontend existentes.

Rationale: `criterios_json` es JSONB y ya aloja estructura anidada, así que el detalle entra **sin migración**. Y los consumidores que hoy leen `criterios_json["criterios"]` no se enteran del campo nuevo.

Además se emite un log WARNING en dos casos: (a) el criterio devuelto por el modelo difiere de la suma de sus subcriterios; (b) el modelo declaró penalizaciones con ids que no existen en la rúbrica. Son las dos señales que permiten medir si el motor mejora o empeora con el tiempo.

### D5. Las correcciones existentes no se recalculan

Recalcular en masa cambiaría notas ya comunicadas a alumnos, algunas ya cargadas en Moodle. Decisión: el change aplica solo a correcciones nuevas y a recorrecciones explícitas (que ya generan un `CorreccionHistorial`, así que la nota vieja queda auditada).

Se entrega, en cambio, un **script de diagnóstico read-only** en `backend/scripts/` que recorre las correcciones existentes y reporta cuáles cambiarían de nota y en cuánto. Eso le da al coordinador la lista para decidir a mano, sin que el sistema decida por él.

## Risks / Trade-offs

- **Las notas nuevas van a bajar.** Es el objetivo, pero hay que comunicarlo: una entrega corregida antes y después del change con la misma rúbrica puede diferir. Mitigación: el script de diagnóstico de D5 cuantifica el impacto antes de desplegar, y el PDF muestra el desglose para que el descuento sea explicable al alumno.
- **D1 fija una semántica que la rúbrica no declara explícitamente.** Si alguna rúbrica en producción fue escrita asumiendo "% del criterio", ese descuento va a resultar mayor de lo pensado. Mitigación: el script de diagnóstico lista qué rúbricas tienen penalizaciones y con qué porcentaje, para revisarlas antes.
- **El modelo puede desobedecer y seguir bajando el criterio.** Riesgo aceptado en D2; falla hacia la nota baja y es observable por el log.

## Migration Plan

Sin migración de esquema. Orden de aplicación:

1. Correr el script de diagnóstico contra un dump de producción y revisar el impacto con el coordinador. **Gate de gobernanza ALTA: no se avanza sin ese OK.**
2. Aplicar el cambio de backend (cálculo + persistencia + log).
3. Aplicar el cambio de prompt (dejar de pedir que aplique el descuento) — **en el mismo deploy que el paso 2**, nunca por separado: prompt viejo más backend nuevo da doble descuento.
4. Verificar en staging con una entrega real de rúbrica con penalización.

## Open Questions

- ¿Los descuentos de múltiples penalizaciones se suman sobre la misma base o se aplican en cascada (cada uno sobre el resultado del anterior)? La propuesta asume **suma sobre la misma base** (más predecible: dos penalizaciones del 30% dan 40% restante y no 49%). Confirmar con el coordinador de la cátedra.
- ¿El descuento puede llevar la nota por debajo de 0? La propuesta la capa en 0.
