> **Gobernanza: 🔴 CRÍTICA.** Esta operación destruye datos de forma irreversible. **No se escribe código sin aprobación humana explícita**, y cada bloque se revisa antes de darlo por cerrado. Los CHECKPOINT con 🛑 son bloqueantes.
>
> El riesgo principal de este change no es de lógica, es de **exhaustividad**: un campo olvidado deja el dato vivo. El inventario del `design.md` es la lista de verificación, y el barrido del paso 6 es lo que la comprueba.

## 0. Gate de arranque

- [ ] 🛑 0.1 Aprobar explícitamente la decisión de fondo: **anonimizar en lugar de borrar**, y la tabla de qué se destruye y qué se conserva del `design.md`.
- [ ] 🛑 0.2 Cerrar las tres Open Questions: retención de respaldos, quién puede pedir la anonimización (administrador y/o identidad automatizada con permiso propio), y si hay que notificar el resultado.
- [ ] 0.3 **Rehacer el inventario de campos** del `design.md` contra el código actual, incluyendo cualquier columna agregada por los changes `motor-anti-falsos-positivos` (evidencia citada) y `correccion-por-ejercicio-con-tests` (resultado de tests) si ya están aplicados.
- [ ] 🛑 0.4 Aprobar el inventario resultante. Es la lista contra la que se implementa y se verifica.

## 1. Identificador anónimo

- [ ] 1.1 (RED) Test: el identificador generado no permite recalcularse a partir del pseudónimo original.
- [ ] 1.2 (RED) Test: dentro de una misma operación, las cuatro entregas del alumno reciben el **mismo** identificador.
- [ ] 1.3 (RED) Test: dos anonimizaciones distintas producen identificadores distintos.
- [ ] 1.4 Implementar la generación del identificador anónimo.
- [ ] 🛑 CHECKPOINT: revisar que la generación es efectivamente irreversible y no una derivación disfrazada del pseudónimo.

## 2. Anonimización de entregas y correcciones

- [ ] 2.1 (RED) Test por campo, uno por cada entrada del inventario aprobado en 0.4: tras la operación, el campo está destruido.
- [ ] 2.2 (RED) Test: nota, puntaje por criterio, rúbrica, comisión, fechas y estado **se conservan**.
- [ ] 2.3 (RED) Test: ninguna fila se elimina físicamente.
- [ ] 2.4 Implementar la anonimización de entregas y correcciones en `app/services/anonimizacion_service.py`.
- [ ] 2.5 (TRIANGULATE) Test: entrega sin corregir → se anonimiza igual y la operación no falla por ausencia de corrección.
- [ ] CHECKPOINT: el inventario de entregas y correcciones está cubierto campo por campo.

## 3. Anonimización del historial

- [ ] 3.1 (RED) Test: una entrega sobrescrita deja copia en el historial → el código y la corrección del historial también quedan destruidos.
- [ ] 3.2 (RED) Test: una corrección reemplazada al recorregir → el snapshot del historial también queda anonimizado.
- [ ] 3.3 (RED) Test: los registros del historial reciben el mismo identificador anónimo que las filas vivas.
- [ ] 3.4 Implementar la anonimización de `entregas_historial` y `correcciones_historial`.
- [ ] 🛑 CHECKPOINT: sin este bloque el change es un placebo. Verificar explícitamente que el código del alumno no quedó en la tabla de al lado.

## 4. Atomicidad y alcance

- [ ] 4.1 (RED) Test: un fallo después de anonimizar las entregas y antes del historial deja todo como estaba.
- [ ] 4.2 Envolver toda la operación en una sola transacción.
- [ ] 4.3 (RED) Tests de alcance: coincidencia exacta sí; coincidencia parcial o por prefijo no; distinta capitalización no; misma identificación en otra universidad no.
- [ ] 4.4 Implementar el acotamiento por coincidencia exacta y por universidad.
- [ ] CHECKPOINT: la operación no puede alcanzar a nadie que no deba.

## 5. Auditoría

- [ ] 5.1 (RED) Test: el registro de auditoría contiene solicitante, fecha, conteos e identificador anónimo, y **no** el pseudónimo original.
- [ ] 5.2 (RED) Test: los registros de auditoría previos que mencionaban el pseudónimo quedan anonimizados.
- [ ] 5.3 Implementar la auditoría de la operación y el barrido de los registros previos.
- [ ] CHECKPOINT: anonimizar a alguien no deja su nombre en el log diciendo que se lo anonimizó.

## 6. Verificación de exhaustividad

- [ ] 6.1 Cargar en un entorno de pruebas un alumno sintético con: dos entregas, una corregida y recorregida (con historial), una sobrescrita (con historial de entrega), evidencia citada, resultado de tests y registros de auditoría.
- [ ] 6.2 Ejecutar la anonimización.
- [ ] 6.3 🛑 **Barrido completo de la base** buscando el pseudónimo sintético en todas las tablas y todas las columnas de texto y JSONB. **El resultado tiene que ser cero coincidencias.**
- [ ] 6.4 Barrido buscando un fragmento distintivo del código entregado. También cero coincidencias.
- [ ] 6.5 Verificar que la nota y el puntaje por criterio siguen ahí.
- [ ] 🛑 CHECKPOINT: si el barrido devuelve una sola coincidencia, el change no está listo. Volver al inventario.

## 7. Endpoint

- [ ] 7.1 (RED) Test: sin confirmación explícita → devuelve el conteo de lo que alcanzaría y **no destruye nada**.
- [ ] 7.2 (RED) Test: con confirmación → ejecuta.
- [ ] 7.3 (RED) Tests de idempotencia: segunda llamada sobre el mismo pseudónimo → éxito con cero entregas; pseudónimo inexistente → éxito con cero entregas.
- [ ] 7.4 Implementar `app/routers/alumnos.py` con el endpoint, sin lógica de negocio.
- [ ] 7.5 (RED) Tests de permisos: administrador → permitido; coordinador → 403; identidad automatizada con permiso de escritura pero sin permiso de anonimización → 403.
- [ ] 7.6 (RED) Test: la respuesta no incluye el pseudónimo original ni ningún dato destruido.
- [ ] 🛑 CHECKPOINT: revisión final del diff completo del change.

## 8. Cierre

- [ ] 8.1 `pytest` completo en el backend, sin regresiones.
- [ ] 8.2 Documentarle al cliente la limitación de los respaldos: la anonimización cubre la base viva, no los respaldos históricos. Acordar la política de retención decidida en 0.2.
- [ ] 8.3 Dejar anotado en el `design.md` que **toda columna nueva que pueda contener datos del alumno obliga a volver al inventario del paso 0.3**.
- [ ] 8.4 `openspec validate anonimizacion-datos-alumno --strict`.
