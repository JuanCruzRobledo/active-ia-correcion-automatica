## Why

El equipo de AI-Native lo reportó al pasar, en la sección "cómo verificamos" de su pedido, y no en la lista de bugs:

> **`GET /entregas/{id}` devuelve 500.** Para saber si una entrega ya se corrigió usamos `GET /correcciones/entregas/{id}`: 200 = corregida, 404 = todavía no.

O sea: rodearon un endpoint roto de producción y siguieron. Pero el endpoint sigue roto **para todo el mundo**, no solo para ellos.

**Causa raíz, confirmada en el código** (`app/services/entrega_service.py:716-720`):

```python
subido_por={
    "id": entrega.subido_por.id,
    "nombre": entrega.subido_por.nombre,
    "email": entrega.subido_por.email,
},
```

`Entrega.subido_por_id` es **nullable** (`app/models/entrega.py:108-111`). Las entregas importadas desde Moodle no tienen usuario que las haya subido: las creó la importación, no una persona. Para esas filas `entrega.subido_por` es `None`, y `entrega.subido_por.id` levanta un `AttributeError` que sale como 500.

El schema lo confirma: `EntregaDetailResponse.subido_por` es `UsuarioInfo` **obligatorio** (`app/schemas/entrega.py:136-138`), sin `| None`. El modelo permite el nulo y el contrato de la API no lo contempla. Es una desalineación entre modelo y schema, no un caso raro.

Consecuencia real: **el detalle de una entrega importada desde Moodle es inaccesible.** Justamente el camino por el que entran casi todas las entregas del sistema.

## What Changes

- **`subido_por` pasa a ser opcional en el detalle de la entrega.** Cuando la entrega no tiene usuario que la haya subido, el campo viaja nulo en lugar de romper la serialización.
- **El servicio deja de asumir la relación cargada.** Construye el bloque solo si existe.
- **El frontend contempla el caso**: donde hoy muestra el nombre de quien subió la entrega, muestra un indicador de origen automático cuando no hay usuario.
- **Test de regresión** con una entrega sin usuario, para que la desalineación no vuelva.

Es un cambio chico. Está separado en su propio change precisamente porque no depende de nada de la integración y se puede aplicar hoy.

## Capabilities

### New Capabilities

- `entrega-detalle-sin-subido-por`: el detalle de una entrega se sirve correctamente cuando no hay usuario que la haya subido, como ocurre con las entregas importadas automáticamente.

## Impact

**Backend**
- `app/schemas/entrega.py` — `EntregaDetailResponse.subido_por` pasa a admitir nulo.
- `app/services/entrega_service.py:716-720` — construcción condicional del bloque.

**Frontend**
- Vista de detalle de entrega: manejo del caso sin usuario.

**Sin migración de esquema.** El modelo ya admite el nulo; lo que se corrige es el contrato de salida.

**Comunicación**: avisarle a AI-Native cuando esté arreglado, para que puedan sacar el rodeo de su cliente si quieren. Y de paso corregirles el supuesto de su §7.3: el índice único real de entregas es `(rubrica_id, alumno_nombre)` y **no incluye** `comision_id`.
