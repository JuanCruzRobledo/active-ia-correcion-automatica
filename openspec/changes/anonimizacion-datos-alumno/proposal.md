## Why

AI-Native tiene un compromiso de anonimización con los alumnos del piloto: si uno pide retirarse, hay un procedimiento que rota su identificador y borra sus datos. **Ese procedimiento tiene que poder alcanzar también lo que quedó en Active-IA**, o el compromiso se cumple a medias y la parte incumplida es justamente la que tiene el código del alumno y su devolución.

El cliente lo pidió como `DELETE /alumnos/{alumno_ref}/datos`.

Pero acá hay una tensión que hay que resolver de frente, no esquivar: **la regla dura de este proyecto es que los DELETE son siempre soft, nunca físicos** (CRUD-002; se eliminó incluso el toggle `ALLOW_HARD_DELETE` para que no hubiera forma de saltarla). Y no es capricho: las correcciones son el registro académico de una nota, y borrarlas físicamente destruye la trazabilidad de una calificación que puede impugnarse.

La forma correcta de cumplir las dos cosas a la vez no es borrar: es **anonimizar**. Lo que el alumno pide retirar son sus datos personales y su producción — el pseudónimo que lo vincula, el código que escribió, la devolución que recibió. Lo que la institución necesita conservar es que hubo una entrega y qué nota se puso, sin que nada de eso apunte a una persona.

Después de anonimizar, la fila sigue existiendo y ya no es un dato personal: no hay nadie a quien remita.

## What Changes

- **`DELETE /api/v1/alumnos/{alumno_ref}/datos`** — dispara la anonimización de todo lo que Active-IA guarda de ese pseudónimo, dentro de la universidad del solicitante.
- **Qué se destruye, irreversiblemente**: el código entregado (consolidado, preview y PDF en base64), los archivos incluidos, el hash de la entrega, el texto de la devolución (comentario general, fortalezas, recomendaciones, feedback y evidencia por criterio), la respuesta cruda del proveedor de IA, el resultado de tests, y el pseudónimo, que se reemplaza por un identificador anónimo estable e irreversible.
- **Qué se conserva**: que hubo una entrega, contra qué rúbrica, en qué comisión, en qué fecha, y con qué nota y puntaje por criterio. El registro académico sobrevive; la persona desaparece de él.
- **Es irreversible y se dice.** No hay deshacer. Se confirma explícitamente antes de ejecutar.
- **Alcanza al historial.** `EntregaHistorial` y `CorreccionHistorial` guardan copias del código y de las devoluciones anteriores. Anonimizar sin tocarlos dejaría el dato intacto en la tabla de al lado.
- **Auditoría de la anonimización**, sin registrar el pseudónimo original. El registro dice que se anonimizó, cuántas entregas y correcciones alcanzó, quién lo pidió y cuándo — no a quién.
- **Idempotente**: pedirlo dos veces no falla ni cambia nada la segunda vez.

## Capabilities

### New Capabilities

- `anonimizacion-alumno`: destrucción irreversible de los datos personales y la producción de un alumno identificado por pseudónimo, conservando el registro académico despersonalizado, con alcance al historial y auditoría que no registra el identificador.
- `api-anonimizacion-alumno`: endpoint de anonimización por pseudónimo, idempotente, con confirmación explícita y restringido por permisos.

### Modified Capabilities

- `entregas-soft-delete`: se agrega la anonimización como operación distinta de la baja lógica — la baja oculta, la anonimización destruye el contenido personal.
- `historial-correcciones`: el historial de correcciones queda alcanzado por la anonimización.

## Impact

**Backend**
- `app/services/anonimizacion_service.py` — nuevo, orquesta la anonimización en una transacción.
- `app/routers/alumnos.py` — nuevo router con el endpoint.
- `app/repositories/entrega_repository.py`, `correccion_repository.py`, `entrega_historial_repository.py`, `correccion_historial_repository.py` — consultas y escrituras de anonimización.
- `app/services/actividad_service.py` — auditoría sin identificador.

**Sin migración de esquema**: la anonimización escribe sobre columnas existentes.

**Gobernanza: 🔴 CRÍTICA.** Destruye datos de forma irreversible. Es análisis y propuesta; no se escribe código sin aprobación humana explícita, y la operación requiere confirmación en cada uso.

**Relacionado**: el cliente dijo que este punto puede ir después del piloto, pero **antes de que un alumno lo pida**. Esa es la fecha límite real, y no la sabe nadie de antemano.
