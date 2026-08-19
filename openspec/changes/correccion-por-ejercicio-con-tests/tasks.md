> **Gobernanza: 🟡 MEDIA** en lo técnico. **Pero el paso 8.1 es un gate externo y no técnico**: sin respuesta sobre la personería, este endpoint no puede recibir código de un alumno real. Todo lo demás se construye, prueba y despliega contra datos sintéticos sin esperar esa respuesta.
>
> Depende de `trabajos-practicos-y-external-ref` y `api-escritura-trabajos-practicos`.

## 1. Backend — Resolución de la comisión (el hueco que el pedido no vio)

- [ ] 1.1 Agregar `comision_integracion_id` (FK nullable a `comisiones`) a `app/models/materia.py`.
- [ ] 1.2 Agregar `external_ref` a `app/models/comision.py` (`String(64)`, nullable, índice único parcial sobre `(materia_id, external_ref)` con `deleted_at IS NULL`).
- [ ] 1.3 Generar y aplicar la migración Alembic vía `docker-compose -f docker-compose.local.yml`; verificar el `downgrade`.
- [ ] 1.4 (RED) Tests de resolución: referencia de comisión en el cuerpo → esa comisión; sin referencia y con comisión de integración → esa; ninguna de las dos → 409 con el mensaje de qué configurar; referencia de otra materia → 409.
- [ ] 1.5 Implementar `_resolver_comision(ejercicio, comision_external_ref)` en el servicio, con la precedencia del design.
- [ ] 1.6 (TRIANGULATE) Test: **ninguna comisión se crea implícitamente en ningún camino**.
- [ ] CHECKPOINT: la entrega puede persistirse sin relajar el `NOT NULL` de `comision_id`.

## 2. Backend — Schemas del contrato

- [ ] 2.1 (RED) Test: el cuerpo acepta `alumno_ref`, `codigo`, `resultado_tests` opcional y `comision_external_ref` opcional.
- [ ] 2.2 Definir `ResultadoTests` (`compila`, `error_compilacion`, `total`, `pasados`, `casos[]`) y `CorreccionEjercicioRequest` en `app/schemas/correccion.py`.
- [ ] 2.3 (RED) Test: `compila` es un campo propio y no se deriva de `pasados == 0`; ambos casos de la tabla del pedido parsean distinto.
- [ ] 2.4 Definir la respuesta con nota y desglose por criterio del ejercicio, **sin** nota agregada del TP.
- [ ] CHECKPOINT: el contrato coincide exactamente con el que el cliente ya implementó, más los dos campos opcionales.

## 3. Backend — `depende_de_ejecucion` en la rúbrica

- [ ] 3.1 (RED) Test: criterio con la marca se persiste; rúbrica sin la marca valida y corrige igual que hoy (default negativo).
- [ ] 3.2 Agregar `depende_de_ejecucion: bool = False` a `Criterio` en `app/schemas/rubrica.py`.
- [ ] 3.3 Propagar la marca al payload de rúbrica que arma `correccion_service`.
- [ ] 3.4 Verificar que el endpoint de escritura de TPs devuelve la marca por criterio, para que el cliente vea qué criterios están cubiertos.
- [ ] CHECKPOINT: la marca existe, es opcional y no altera ninguna rúbrica existente.

## 4. Backend — Cierre determinístico por no compilar

- [ ] 4.1 (RED) Test: `compila: false` + dos criterios marcados → los dos en cero con estado de error y feedback que cita `error_compilacion`.
- [ ] 4.2 (RED) Test: el motor devolvió puntaje positivo en un criterio marcado y el código no compila → el puntaje se descarta.
- [ ] 4.3 (RED) Test: los criterios de diseño no marcados conservan el puntaje del motor aunque no compile.
- [ ] 4.4 Implementar `_forzar_criterios_de_ejecucion(criterios, rubrica, resultado_tests)`, aplicado **antes** de la suma, en la cadena determinística.
- [ ] 4.5 (TRIANGULATE) Tests: `compila: true` con `0/6` → ningún criterio forzado; sin `resultado_tests` → ningún criterio forzado aunque la rúbrica tenga marcas.
- [ ] 4.6 Verificar la exención: un criterio forzado en cero no se degrada por evidencia no verificable.
- [ ] CHECKPOINT: la regla que el cliente pidió es determinística, no una instrucción de prompt.

## 5. Backend — Resultado de tests en el prompt

- [ ] 5.1 (RED) Test: con `resultado_tests`, el prompt incluye la sección de resultado de ejecución antes de los criterios, con la instrucción de hecho establecido.
- [ ] 5.2 (RED) Test: sin `resultado_tests`, la sección no aparece.
- [ ] 5.3 Implementar `_build_resultado_tests_texto` en `app/integrations/gemini_correction_client.py` y sumarlo a los prompts de código.
- [ ] 5.4 (RED) Test de acotamiento: resultado que excede el límite → se priorizan los casos fallados y el prompt indica el recorte.
- [ ] 5.5 Implementar el acotamiento con priorización de fallados.
- [ ] 5.6 Verificar que el proveedor OpenRouter hereda la sección.
- [ ] 5.7 Persistir el `resultado_tests` recibido junto con la corrección, para auditabilidad posterior.
- [ ] CHECKPOINT: el motor recibe la corrida como hecho, no como sugerencia.

## 6. Backend — Endpoint y reuso de entrega

- [ ] 6.1 (RED) Tests de endpoint: ejercicio vigente → 200 con nota y desglose; referencia inexistente o dada de baja → 404; sin acceso a la materia → 403 sin revelar existencia.
- [ ] 6.2 Implementar `POST /correcciones/ejercicios/{ejercicio_ref}/corregir` en `app/routers/correcciones.py`, sin lógica de negocio.
- [ ] 6.3 (RED) Test: segunda corrección del mismo alumno y ejercicio → reusa la entrega, snapshotea la corrección anterior en el historial, **no** devuelve 409.
- [ ] 6.4 Implementar el reuso apoyándose en `_snapshot_de_correccion` (CRUD-003, ya existente).
- [ ] 6.5 (TRIANGULATE) Test: el mismo alumno en dos ejercicios del mismo TP genera dos entregas independientes, una por rúbrica.
- [ ] 6.6 (RED) Test: el pseudónimo se almacena literal, sin ninguna resolución contra el padrón ni contra Moodle.
- [ ] 6.7 Registrar la auditoría con actor, referencia del ejercicio y pseudónimo.
- [ ] CHECKPOINT: flujo completo contra datos sintéticos.

## 7. Verificación técnica

- [ ] 7.1 `pytest` completo en el backend, sin regresiones.
- [ ] 7.2 Reproducir los dos casos control con tests provistos: la entrega de "3 categorías y 10 productos sin vincular" y la búsqueda hardcodeada, y reportar si el resultado de ejecución los corrige.
- [ ] 7.3 Marcar `depende_de_ejecucion` en las rúbricas de los ejercicios del piloto.
- [ ] 7.4 Configurar `comision_integracion_id` en las materias del piloto.
- [ ] 7.5 Medir el impacto en `tokens_entrada` de la sección de resultado de ejecución y fijar el límite de tamaño definitivo.
- [ ] 7.6 Avisarle al cliente que el índice único real de entregas es `(rubrica_id, alumno_nombre)` y no incluye `comision_id`, para que corrijan el supuesto de su §7.3.
- [ ] 7.7 `openspec validate correccion-por-ejercicio-con-tests --strict`.

## 8. Gate de despliegue con datos reales

- [ ] 🛑 8.1 **Obtener una respuesta escrita sobre la personería**: ¿AI-Native y Active-IA son el mismo responsable de datos frente al consentimiento que firmaron los alumnos del piloto? Si no lo son, enviar código de un alumno es una cesión a un tercero y el consentimiento tiene que decirlo. **Esta tarea no la cierra el equipo técnico.** Hasta que esté resuelta, el endpoint solo opera con datos sintéticos.
- [ ] 8.2 Documentar la respuesta obtenida y la fecha, junto al change.
- [ ] 8.3 Recién entonces, habilitar el flujo con entregas de alumnos reales del piloto.
