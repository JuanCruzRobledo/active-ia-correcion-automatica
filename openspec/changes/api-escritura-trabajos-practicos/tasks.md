> **Gobernanza: 🟡 MEDIA.** Depende de `trabajos-practicos-y-external-ref` (modelo, validación, resolución por identificador externo). No arrancar hasta que ese change esté aplicado.

## 1. Schemas de request y response

- [x] 1.1 (RED) Test: el request de alta acepta `external_ref`, `materia_external_ref`, `titulo` y `ejercicios[]` anidados con rúbrica y casos.
- [x] 1.2 Definir `TrabajoPracticoWriteRequest` y `EjercicioWriteRequest` en `app/schemas/trabajo_practico.py`, reusando el `TestCase` validado en el change anterior.
- [x] 1.3 (RED) Test: el response incluye por ejercicio `external_ref`, `id`, `orden`, `titulo`, `peso` y `rubrica_id`.
- [x] 1.4 Definir `TrabajoPracticoResponse` y `EjercicioResponse` con esos campos.
- [x] 1.5 (RED) Test: identificadores externos de ejercicio duplicados dentro del mismo cuerpo → error de validación con el identificador nombrado.
- [x] 1.6 Implementar el validador de duplicados intra-push.
- [x] CHECKPOINT: el contrato de entrada y salida cerrado, con el `rubrica_id` por ejercicio garantizado.

## 2. Servicio — Alta atómica

- [x] 2.1 (RED) Test: alta de un TP con cuatro ejercicios crea TP + 4 ejercicios + 4 rúbricas.
- [x] 2.2 (RED) Test: cuerpo con el tercer ejercicio inválido → nada persistido (ni TP ni los dos primeros).
- [x] 2.3 Implementar el alta atómica en `app/services/trabajo_practico_service.py`, en una sola transacción.
- [x] 2.4 (RED) Test: `materia_external_ref` inexistente → error de no encontrado con el identificador en el mensaje; no se crea ninguna materia.
- [x] 2.5 Implementar la resolución de materia por identificador externo, acotada a la universidad activa.
- [x] CHECKPOINT: atomicidad verificada — un fallo intermedio no deja residuos.

## 3. Servicio — Upsert y reconciliación

- [x] 3.1 (RED) Test: primer push por `external_ref` inexistente → crea; segundo push idéntico → no duplica nada.
- [x] 3.2 (RED) Test: ejercicios reordenados entre pushes → se actualizan por identificador externo, ninguno se recrea.
- [x] 3.3 (RED) Test: **el `rubrica_id` de cada ejercicio es el mismo antes y después del upsert** (la garantía que sostiene todo el resto).
- [x] 3.4 Implementar la reconciliación: emparejar por `external_ref`, actualizar en su lugar conservando `rubrica_id`, crear los nuevos, dar de baja lógica los ausentes.
- [x] 3.5 (RED) Test: un ejercicio que deja de venir queda de baja lógica junto con su rúbrica y desaparece de la respuesta.
- [x] 3.6 (RED) Test: las entregas y correcciones de un ejercicio dado de baja se conservan y siguen consultables; nada se borra físicamente.
- [x] 3.7 (TRIANGULATE) Test: reenviar el identificador externo de un ejercicio dado de baja lo deja vigente otra vez.
- [x] 3.8 (RED) Test: un fallo durante la reconciliación deja el TP exactamente como estaba.
- [x] 🛑 CHECKPOINT: la reconciliación es el punto donde una decisión floja rompe notas. Revisar la tabla de casos del design contra los tests antes de seguir.

## 4. Router y códigos de respuesta

- [x] 4.1 (RED) Tests de endpoint: `POST /` → 201; `PUT /by-ref/{ref}` que crea → 201; que actualiza → 200; `GET /by-ref/{ref}` inexistente o dado de baja → 404.
- [x] 4.2 Crear `app/routers/trabajos_practicos.py` con los tres endpoints, sin lógica de negocio (solo HTTP + Pydantic + delegación al servicio).
- [x] 4.3 Registrar el router en `app/main.py`.
- [x] 4.4 (RED) Tests de contrato: caso oculto con salida esperada → 422 nombrando ejercicio y caso; tipo de caso desconocido → 422; ids de caso duplicados → 422.
- [x] 4.5 Mapear los errores del servicio a los códigos del proyecto (422 validación, 404 no encontrado, 403 prohibido).
- [x] CHECKPOINT: los códigos y los mensajes de error coinciden con lo que el cliente ya tiene codificado en su doble HTTP.

## 5. Permisos y auditoría

- [x] 5.1 (RED) Tests: escritura con rol tutor → 403; consulta con rol tutor y acceso a la materia → 200; coordinador sin acceso a la materia → 403 sin revelar existencia.
- [x] 5.2 Aplicar `require_coordinador_or_admin` + `verificar_acceso_materia` en las escrituras, y el acceso de tutor en la consulta.
- [x] 5.3 (RED) Test: un upsert que crea uno, actualiza dos y da de baja uno registra una actividad con esos tres contadores.
- [x] 5.4 Registrar la auditoría en `app/services/actividad_service.py`.
- [x] CHECKPOINT: permisos y auditoría verificados.

## 6. Límites y robustez

- [x] 6.1 Fijar un límite explícito de ejercicios por TP y de tamaño de body, y devolver un error claro al excederlo (cerrar la Open Question del design con el cliente).
- [ ] 6.2 Medir el tiempo de respuesta de un `PUT` con un TP de tamaño realista y confirmar que entra cómodo en el timeout de 90s del cliente.
- [x] 6.3 Verificar que un `PUT` concurrente sobre el mismo `external_ref` no crea duplicados (el índice único parcial del change anterior es la red).

## 7. Verificación y cierre

- [x] 7.1 `pytest` completo en el backend, sin regresiones.
- [x] 7.2 Escribir un test de integración que reproduzca el ciclo del cliente: publicar, republicar idéntico, republicar con un ejercicio menos, republicarlo de vuelta.
- [ ] 7.3 Documentar el contrato (OpenAPI + ejemplo de cuerpo) y entregárselo al equipo de AI-Native antes del deploy, para que apunten su cliente a staging y no a producción.
- [ ] 7.4 Confirmar con ellos que el contrato coincide con su doble HTTP (`tests/e2e/smoke/test_smoke_activeia_doble.py`), que cubre camino feliz, 409, motor saturado, credencial inválida y respuesta sin id.
- [ ] 7.5 `openspec validate api-escritura-trabajos-practicos --strict`.
