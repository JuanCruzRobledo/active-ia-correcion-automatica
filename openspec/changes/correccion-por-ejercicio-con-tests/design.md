## Context

Estado verificado en el código al 2026-08-19:

- `Entrega.comision_id` (`app/models/entrega.py:41-45`) es **`NOT NULL`**, FK a `comisiones.id`. AI-Native no tiene comisiones.
- El índice único de entregas es `uq_entrega_rubrica_alumno` sobre **`(rubrica_id, alumno_nombre)`** con `postgresql_where=text("deleted_at IS NULL")` (L133-140). **Ojo**: el cliente documentó en su §7.3 que el 409 keyea por `(comision_id, rubrica_id, alumno_nombre)`. El índice real **no incluye `comision_id`**. Su conclusión operativa (comparar el `rubrica_id` en el match no es opcional) es correcta; la clave que asumen, no del todo. Conviene avisarles.
- `Entrega.alumno_nombre` es `String(100)`, lo que aloja un pseudónimo sin problema.
- La recorrección ya está resuelta: `_snapshot_de_correccion` (`correccion_service.py:196+`, CRUD-003) guarda la corrección saliente en `CorreccionHistorial` antes de reemplazarla.
- `_build_correction_payload` (L888-912) manda `codigo`, `rubrica`, `api_key` y `contexto`. Nada de ejecución.
- `_nota_deterministica` (L162-193) es el punto único donde se decide la nota. Tras el change `nota-deterministica-penalizaciones` incorpora también los descuentos.
- `Criterio` (`app/schemas/rubrica.py:69-123`) tiene `peso`, `instrucciones_puntuacion` y `subcriterios`. No tiene noción de dependencia de ejecución.

Governance: **MEDIA** en lo técnico. Pero el despliegue con datos reales tiene un gate **externo y no técnico** (ver "Bloqueante de personería").

## Goals / Non-Goals

**Goals**

- Que "el programa funciona" deje de ser una inferencia del modelo cuando existe una corrida que lo responde.
- Que no compilar y compilar fallando produzcan devoluciones distintas.
- Que un criterio que requiere ejecución no pueda cerrarse cuando ninguna corrida lo respalda.
- Que el cliente no tenga que cambiar el contrato que ya implementó.

**Non-Goals**

- Active-IA **no ejecuta** código ni tests. El sandbox es del cliente y funciona.
- No se calcula la nota final del TP. Se devuelve nota por ejercicio.
- No hay corrección en lote.
- No se escribe nada del lado del cliente. La integración es de una sola dirección.

## Decisions

### D1. El hueco de la comisión: `Materia.comision_integracion_id`

`entregas.comision_id` es `NOT NULL` y AI-Native no tiene comisiones. El documento del cliente no lo menciona porque no ve nuestro modelo. Hay que resolverlo o el endpoint no puede persistir nada.

Decisión: dos vías, en este orden de precedencia.

1. Si el cuerpo trae `comision_external_ref` y resuelve a una comisión vigente de la materia → se usa esa. Habilita cohortes cuando el cliente quiera modelarlas.
2. Si no → se usa `Materia.comision_integracion_id`, una FK nullable que un administrador configura **una vez por materia** al dar de alta la integración.
3. Si ninguna de las dos resuelve → `409` con un mensaje que dice exactamente qué falta configurar.

Rationale: el contrato que el cliente ya implementó (`{alumno_ref, codigo, resultado_tests}`) **no cambia** — el campo nuevo es opcional. Y no se inventa una comisión implícitamente: crear entidades por efecto colateral de una corrección es la clase de magia que después nadie puede explicar.

Alternativa descartada: hacer `entregas.comision_id` nullable. Es una tabla caliente, con índices, scoping multi-tenant y consultas en medio proyecto que asumen la comisión. El costo de esa nullabilidad se paga para siempre; una FK de configuración se paga una vez.

`Comision.external_ref` se agrega con el mismo patrón que las demás referencias externas (único por materia, parcial sobre no borrados).

### D2. El resultado de los tests entra al prompt como hecho establecido

El payload gana un bloque `resultado_tests` con `compila`, `error_compilacion`, `total`, `pasados` y `casos[]` (`id`, `paso`, `entrada`, `esperado`, `obtenido`).

En el prompt se renderiza como sección propia, **antes** de los criterios, con la instrucción:

> Este resultado proviene de la ejecución real del código en un sandbox. Es un HECHO ESTABLECIDO, no una sugerencia. NO vuelvas a deducir si el programa funciona: ya está respondido. Concentrate en lo que un test no puede medir y que es lo que la rúbrica evalúa.

Rationale: es el pedido central del cliente y ataca la raíz de los bugs 4 y 5. El motor deja de tener que inferir funcionamiento desde el texto del código, que es exactamente donde falla.

**El resultado es opcional en el contrato.** Si no viene (un cliente que no ejecuta), la corrección procede como hoy y la sección no se renderiza.

### D3. `depende_de_ejecucion` es un campo de rúbrica, y el cierre en cero es determinístico

El cliente pide: con `compila: false`, no cerrar criterios del tipo "el programa funciona". Ponerlo solo en el prompt sería repetir el error del bug 2 — una regla declarada que el motor puede no honrar.

Decisión: `Criterio.depende_de_ejecucion: bool` (opcional, default `false`), y en el backend:

- Si `resultado_tests.compila` es `false`, todo criterio con `depende_de_ejecucion` se fuerza a `puntaje_obtenido: 0`, `estado: ERROR`, con feedback generado que cita `error_compilacion`.
- El forzado ocurre **antes** de la suma, integrado a la cadena determinística del cálculo de la nota.
- Los criterios sin la marca se evalúan normalmente: el juicio sobre diseño sigue siendo útil y es lo que justifica mandar el código aunque no compile.

Rationale: es la única forma de garantizar la regla. Y `depende_de_ejecucion` es información que solo la rúbrica tiene — el backend no puede adivinar qué criterio depende de que el programa corra.

**Default `false` a propósito**: una rúbrica que no marca nada se comporta exactamente como hoy. Nada retroactivo, nada que backfillear.

**Exención de la verificación de evidencia**: un criterio forzado a 0 no se degrada por evidencia no verificable (regla ya prevista en el change `motor-anti-falsos-positivos` para criterios en cero).

### D4. Compilar y fallar todo NO cierra criterios en cero

Con `compila: true` y `pasados: 0`, ningún criterio se fuerza. El resultado se informa como hecho y el motor lo pondera.

Rationale: es la distinción que el cliente agregó el 2026-08-19. "No compila" es un punto y coma; "compila y falla todo" es un programa que corre y hace otra cosa. Forzar en cero los dos casos borraría la diferencia que motivó el pedido.

### D5. Recorrección en lugar de 409

Si ya existe una entrega vigente para ese `(rubrica_id, alumno_nombre)`, el endpoint la reusa: actualiza el código, snapshotea la corrección anterior en `CorreccionHistorial` y corrige de nuevo.

Rationale: el mecanismo ya existe (CRUD-003) y no se pierde nada. Para el cliente, reintentar es una llamada idéntica en vez de un 409 que hay que ramificar. Y por ejercicio la clave `(rubrica_id, alumno_nombre)` es exactamente la granularidad correcta, porque cada ejercicio tiene su propia rúbrica.

### D6. El pseudónimo del alumno se guarda tal cual, sin enriquecerlo

`alumno_ref` va a `alumno_nombre`. Active-IA **no** intenta resolverlo a una persona, ni cruzarlo con su padrón, ni completarlo con datos de Moodle.

Rationale: es un pseudónimo por diseño del cliente, y es lo que hace posible el procedimiento de anonimización del change `anonimizacion-datos-alumno`. Enriquecerlo destruiría la propiedad que lo hace útil.

### D7. Bloqueante de personería — gate externo antes de datos reales

El cliente pregunta si AI-Native y Active-IA son **el mismo responsable de datos** frente al consentimiento que firmaron los alumnos del piloto. Si no lo son, mandar código de un alumno es una **cesión a un tercero** y el consentimiento tiene que decirlo.

Esto no lo resuelve ninguna decisión de diseño. Se registra acá porque condiciona el despliegue: **el endpoint puede construirse, probarse y desplegarse contra datos sintéticos sin ninguna respuesta legal. No puede recibir código de un alumno real hasta que exista.**

La tarea correspondiente está en `tasks.md` con gate explícito y no la cierra el equipo técnico.

## Risks / Trade-offs

- **`depende_de_ejecucion` depende de que alguien marque los criterios.** Una rúbrica sin marcar no gana nada. Mitigación: marcarlos en las rúbricas del piloto como parte de la verificación de este change, y devolver la marca en la respuesta del endpoint de escritura para que el cliente vea qué criterios están cubiertos.
- **El resultado de tests engorda el prompt.** Un ejercicio con muchos casos y salidas largas puede sumar bastante contexto. Mitigación: acotar el largo de `entrada`, `esperado` y `obtenido` por caso, y priorizar los casos que fallaron sobre los que pasaron cuando haya que recortar.
- **Forzar criterios en cero puede sorprender al docente**, que ve un 0 donde el modelo había puesto puntaje. Mitigación: el feedback generado dice explícitamente por qué, y cita el error del compilador.
- **La configuración de `comision_integracion_id` es un paso manual fácil de olvidar**, y su ausencia solo se descubre en la primera corrección. Mitigación: el error 409 dice exactamente qué configurar; conviene además chequearlo al publicar el primer TP de la materia.

## Migration Plan

Migración chica: `materias.comision_integracion_id` (FK nullable) y `comisiones.external_ref` (nullable, único parcial por materia). Ambas aditivas, sin backfill.

Orden de despliegue: (1) migración y configuración de la comisión de integración de las materias del piloto; (2) endpoint contra datos sintéticos; (3) marcado de `depende_de_ejecucion` en las rúbricas del piloto; (4) **gate de personería**; (5) datos reales.

## Open Questions

- ¿Cuál es el límite de tamaño del bloque `resultado_tests`? Hay que fijarlo, y definir la política de recorte (la propuesta sugiere priorizar los casos fallados).
- ¿La respuesta debería incluir qué criterios fueron forzados a cero por no compilar, como campo aparte? Sería útil para que el cliente lo muestre distinto al docente. Confirmar si lo quieren.
- ¿Avisamos al cliente que el índice único real de entregas es `(rubrica_id, alumno_nombre)` y no incluye `comision_id`? Su §7.3 asume lo segundo. La conclusión operativa que sacaron es correcta, pero conviene que el dato esté bien.
