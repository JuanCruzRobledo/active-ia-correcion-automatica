## Context

Estado verificado en el código al 2026-08-19. Lo que Active-IA guarda de un alumno, por tabla:

- **`entregas`**: `alumno_nombre` (el pseudónimo), `contenido_consolidado` (el código), `contenido_preview`, `pdf_contenido_b64`, `archivos_incluidos`, `archivo_nombre`, `hash_sha256`, `moodle_user_id`.
- **`correcciones`**: `comentario_general`, `fortalezas`, `recomendaciones`, `criterios_json` (que incluye el feedback por criterio y, tras el change `motor-anti-falsos-positivos`, la evidencia citada del código del alumno), `raw_response` (la respuesta cruda del proveedor de IA, que contiene el código en el prompt reflejado).
- **`entregas_historial`**: `alumno_nombre`, `contenido_consolidado`, `contenido_preview`, `pdf_contenido_b64`, `hash_sha256`, `correccion_json`. **Es una copia completa de una entrega anterior.**
- **`correcciones_historial`**: snapshot de correcciones reemplazadas al recorregir (CRUD-003).
- **`actividades`**: log de auditoría, que puede contener el pseudónimo en sus descripciones.

Reglas duras del proyecto en juego:

- **Los DELETE son siempre soft, nunca físicos** (CRUD-002). Se eliminó el toggle `ALLOW_HARD_DELETE` precisamente para que no hubiera forma de saltarla. Una purga física real "debe ser una feature deliberada y auditada, no un toggle de env".
- Toda acción se audita.

Governance: **🔴 CRÍTICA** — destrucción irreversible de datos.

## Goals / Non-Goals

**Goals**

- Que el compromiso de anonimización del cliente pueda cumplirse de punta a punta, incluyendo lo que quedó en Active-IA.
- Que después de la operación no quede en la base ningún dato que remita a la persona.
- Que el registro académico despersonalizado sobreviva.
- Que la operación sea auditable sin ser, ella misma, un registro de quién pidió retirarse.

**Non-Goals**

- No se implementa borrado físico de filas. La regla del proyecto se respeta.
- No se anonimiza por nombre real ni por identificador de Moodle; este procedimiento es para pseudónimos de la integración.
- No se ofrece deshacer. Por definición.
- No se exporta lo que se va a destruir. Si el alumno quiere una copia, la pide antes y por otro canal.

## Decisions

### D1. Anonimizar, no borrar

La operación **sobrescribe** los campos personales y de producción, y **conserva** la fila.

| Campo | Acción |
|---|---|
| Pseudónimo del alumno | Reemplazado por un identificador anónimo estable e irreversible |
| Código consolidado, preview, PDF en base64 | Destruidos |
| Archivos incluidos, nombre de archivo, hash | Destruidos |
| Comentario general, fortalezas, recomendaciones | Destruidos |
| Feedback y evidencia por criterio | Destruidos |
| Respuesta cruda del proveedor de IA | Destruida |
| Resultado de tests | Destruido |
| Identificador de usuario de Moodle | Destruido |
| Nota, puntaje por criterio, rúbrica, comisión, fechas | **Conservados** |

Rationale: cumple el compromiso con el alumno (lo suyo desaparece) sin destruir el registro académico (hubo una entrega, se puso una nota) ni violar la regla del proyecto. Una fila anonimizada ya no es un dato personal: no hay nadie a quien remita.

Alternativa descartada: purga física. Es la excepción que el `CLAUDE.md` contempla, pero destruye la trazabilidad de una calificación que puede impugnarse, y rompe integridad referencial con `moodle_syncs` y con los históricos. La anonimización logra el mismo resultado para el alumno con muchísimo menos daño colateral.

### D2. El identificador anónimo es estable e irreversible

El pseudónimo se reemplaza por un identificador derivado de forma **no reversible**, distinto por cada anonimización, y **estable dentro de una misma operación**: las N entregas del mismo alumno quedan todas con el mismo identificador anónimo.

Rationale de la estabilidad: si cada entrega recibiera un identificador distinto, se perdería la información de que las cuatro entregas eran del mismo alumno, que es un dato académico legítimo y ya no personal.

Rationale de la irreversibilidad: si el identificador se derivara del pseudónimo de forma reproducible, quien conociera el pseudónimo podría recalcularlo y volver a encontrar las filas. Eso no sería anonimización, sería seudonimización de segundo orden.

### D3. El historial se anonimiza también

`entregas_historial` guarda `contenido_consolidado`, `pdf_contenido_b64` y `correccion_json` completos de entregas anteriores. `correcciones_historial` guarda correcciones reemplazadas.

**Anonimizar solo las filas vivas sería un placebo**: el código del alumno seguiría entero en la tabla de al lado.

Los históricos reciben el mismo tratamiento de D1, con el mismo identificador anónimo de la operación.

### D4. Todo en una transacción

Entregas, correcciones e históricos se anonimizan en una sola transacción. Un fallo a mitad de camino deja todo como estaba.

Rationale: una anonimización parcial es el peor resultado posible — el alumno cree que sus datos se fueron y una parte quedó.

### D5. La auditoría registra la operación, no a quién alcanzó

Se registra: que hubo una anonimización, cuántas entregas y correcciones alcanzó, quién la solicitó, cuándo, y el identificador anónimo resultante. **No se registra el pseudónimo original.**

Rationale: es contradictorio anonimizar a alguien y dejar su identificador en el log de auditoría diciendo "a este lo anonimizamos". El identificador anónimo alcanza para vincular la operación con sus filas si hiciera falta auditarla.

Y hay que revisar el log de auditoría preexistente: si `actividades` ya contiene el pseudónimo en descripciones de acciones anteriores, esas descripciones también hay que anonimizarlas, o el dato sobrevive donde nadie lo busca.

### D6. Idempotente y explícito

Pedir la anonimización de un pseudónimo ya anonimizado —o inexistente— responde éxito informando que alcanzó cero entregas, sin error.

Rationale: el procedimiento del cliente puede reintentarse, y un error en el reintento haría creer que algo falló.

La operación exige una **confirmación explícita** en la petición. Rationale: es irreversible, y una llamada accidental no debería poder destruir nada.

### D7. Alcance acotado a la universidad y a los pseudónimos

La anonimización alcanza únicamente entregas cuya identificación de alumno coincida exactamente con el pseudónimo dado, dentro de la universidad del solicitante.

Rationale: los pseudónimos son opacos y podrían colisionar con un nombre real cargado por el flujo de Moodle. Sin el acotamiento por universidad, una operación podría alcanzar entregas de otra institución.

**Riesgo residual reconocido**: si un nombre real coincidiera exactamente con un pseudónimo dentro de la misma universidad, la operación alcanzaría a esa persona. Es improbable dado el formato de los pseudónimos, pero la mitigación es real: la operación devuelve **primero** un conteo de qué va a alcanzar, y solo ejecuta con la confirmación de D6.

## Risks / Trade-offs

- **Es irreversible.** No hay mitigación posible, solo la confirmación explícita de D6 y la previsualización del conteo.
- **Un campo olvidado deja el dato vivo.** Es el riesgo principal y es de exhaustividad, no de lógica. Mitigación: el inventario por tabla del "Context" es la lista de verificación, y hay que rehacerlo cada vez que una columna nueva pueda contener datos del alumno. La tarea de verificación incluye un barrido de la base buscando el pseudónimo después de anonimizar.
- **Las columnas nuevas de otros changes.** `resultado_tests` (de `correccion-por-ejercicio-con-tests`) y la evidencia citada (de `motor-anti-falsos-positivos`) contienen datos del alumno. Si esos changes se aplican después de este, hay que volver acá.
- **Los backups.** Este procedimiento no alcanza los respaldos de base de datos. Es una limitación real que hay que declararle al cliente, no esconder: la anonimización cubre la base viva.

## Migration Plan

Sin migración de esquema. Se escribe sobre columnas existentes.

Antes de habilitarlo: correr la operación contra un entorno de pruebas con datos sintéticos y verificar con un barrido completo de la base que el pseudónimo no aparece en ninguna tabla.

## Open Questions

- ¿Los respaldos de base de datos deben tener una política de retención que acote cuánto sobrevive ahí un dato anonimizado? Es la limitación de la que hay que avisarle al cliente. La respuesta es operativa, no de código.
- ¿Quién puede pedir una anonimización: solo un administrador, o también la cuenta de servicio de la integración? El cliente la necesita desde su procedimiento automatizado, lo que apunta a la cuenta de servicio con un permiso propio y separado. Confirmar.
- ¿Hay que notificar al cliente el resultado de la operación, o le alcanza con la respuesta de la llamada?
