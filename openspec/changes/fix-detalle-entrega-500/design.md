## Context

Causa raíz confirmada en el código al 2026-08-19:

- `Entrega.subido_por_id` (`app/models/entrega.py:108-111`) es `Mapped[int | None]`, `nullable=True`. Las entregas importadas desde Moodle no tienen usuario que las haya subido.
- `EntregaDetailResponse.subido_por` (`app/schemas/entrega.py:136-138`) es `UsuarioInfo` **obligatorio**, sin admitir nulo.
- `EntregaService.obtener_entrega` (`app/services/entrega_service.py:716-720`) construye el bloque accediendo directo a `entrega.subido_por.id`, sin comprobar que la relación exista. Con la relación en `None`, eso levanta `AttributeError` y sale como 500.

Es una desalineación entre el modelo (que permite el nulo) y el contrato de salida (que no lo contempla). No es un caso raro: el camino de importación desde Moodle es por donde entra la mayoría de las entregas del sistema.

Governance: **🟢 BAJA** — arreglo puntual, sin cambio de modelo, con test de regresión. Autonomía completa si los tests pasan.

## Goals / Non-Goals

**Goals**

- Que el detalle de una entrega importada deje de dar 500.
- Que la desalineación entre modelo y schema no vuelva.

**Non-Goals**

- No se hace obligatorio `subido_por_id` en el modelo. Que una entrega importada no tenga usuario humano es correcto, no un defecto de datos.
- No se rellena `subido_por_id` con el usuario que disparó la importación. Sería información falsa: esa persona no subió la entrega, la importó.
- No se revisan otros endpoints en este change (ver Open Questions).

## Decisions

### D1. Se corrige el contrato de salida, no el modelo

`subido_por` pasa a admitir nulo en la respuesta, y el servicio construye el bloque solo si la relación existe.

Rationale: el modelo ya expresa la realidad correctamente — hay entregas sin persona que las suba. El que miente es el schema, que promete un objeto que no siempre hay.

Alternativa descartada: hacer `subido_por_id` obligatorio y backfillear con el usuario que corrió la importación. Registraría como autor de una entrega a alguien que no la subió, y ensuciaría la auditoría para siempre a cambio de no tocar dos líneas.

### D2. El frontend distingue "sin usuario" de "usuario vacío"

Donde hoy muestra el nombre, muestra un indicador de origen automático cuando el campo viene nulo.

Rationale: un nombre en blanco parece un error de datos. Decir que el origen es automático es información útil para el tutor, y es la verdad.

### D3. Test de regresión con una entrega sin usuario

El test que reproduce el 500 se escribe **antes** del arreglo y queda en la suite.

Rationale: es exactamente la clase de bug que vuelve cuando alguien agrega un campo obligatorio nuevo al detalle sin mirar la nulabilidad de la columna de origen.

## Risks / Trade-offs

- **Riesgo bajo.** El cambio es aditivo sobre el contrato: un campo que antes siempre venía poblado ahora puede venir nulo. Cualquier consumidor que asuma que siempre viene poblado se rompe — pero hoy ese consumidor no puede ni recibir la respuesta, porque el endpoint devuelve 500 para esas filas.
- **El caso podría repetirse en otros endpoints** que serialicen relaciones opcionales. Este change no los busca; ver Open Questions.

## Migration Plan

Sin migración. Cambio de schema de salida y de servicio, más el ajuste del frontend.

## Open Questions

- ¿Vale la pena un barrido de todos los schemas de respuesta buscando campos obligatorios cuya columna de origen es nullable? Es la versión generalizada de este bug y probablemente encuentre más de uno. Queda fuera de alcance de este change, pero se anota como candidato propio.
