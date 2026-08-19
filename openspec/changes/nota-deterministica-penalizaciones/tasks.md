> **Gobernanza: 🟠 ALTA.** Este change modifica el número que se le informa a un alumno como su nota. Los CHECKPOINT marcados con 🛑 requieren OK humano explícito antes de continuar.

## 1. Diagnóstico de impacto (antes de tocar nada)

- [ ] 1.1 Escribir `backend/scripts/diagnostico_nota_deterministica.py` (solo lectura): recorre correcciones existentes, recalcula la nota con la fórmula nueva y reporta id, alumno, rúbrica, nota actual, nota nueva, diferencia.
- [ ] 1.2 Listar las rúbricas de producción que tienen `penalizaciones_json` no vacío, con su `descuento_porcentaje`, para revisar si alguna fue escrita asumiendo "% del criterio" y no "% del total" (ver D1).
- [ ] 1.3 Correr el script contra un dump de producción y armar el resumen de impacto (cuántas correcciones cambian, cuánto baja la nota en promedio y en el peor caso).
- [ ] 🛑 CHECKPOINT: presentar el resumen de impacto y la lista de rúbricas al coordinador. **No avanzar sin OK explícito.** Cerrar acá las dos Open Questions del design (base de descuentos y piso en 0).

## 2. Backend — Recomputo del criterio por subcriterios (bug 3)

- [ ] 2.1 (RED) Test: criterio v2 con `puntaje_obtenido: 0` y `subcriterios_evaluados` que suman 5 → el criterio queda en 5.
- [ ] 2.2 (RED) Test: rúbrica v1 y criterio v2 sin desglose → `puntaje_obtenido` se respeta sin cambios (caracterización del camino actual).
- [ ] 2.3 Implementar helper `_recomputar_criterios_v2(criterios_evaluados, rubrica)` en `app/services/correccion_service.py`: solo actúa con `schema_version >= 2` y `subcriterios_evaluados` no vacío.
- [ ] 2.4 (TRIANGULATE) Test: subcriterio por encima de su `puntaje_maximo` se acota; suma por encima del `peso` del criterio se acota al peso.
- [ ] 2.5 Emitir log WARNING con criterio, valor del modelo y suma de subcriterios cuando difieran.
- [ ] 2.6 Invocar el helper **antes** de `_nota_deterministica` en el flujo de corrección, y verificar que el valor recomputado es el que se persiste en `criterios_json`.
- [ ] CHECKPOINT: el desglose cierra con el criterio; v1 verificado sin regresión.

## 3. Backend — Descuento determinístico por penalización (bug 2)

- [ ] 3.1 (RED) Test de caracterización del comportamiento actual de `_nota_deterministica` (suma limpia, techo por CD) para blindar lo que NO debe cambiar.
- [ ] 3.2 (RED) Test: suma 87 + `P1` al 30% en la rúbrica → `nota_antes_penalizaciones` 87.00, nota final 60.90 (el caso medido el 2026-08-17).
- [ ] 3.3 Implementar `_descuento_por_penalizaciones(rubrica, ids_validos, suma) -> (descuento, detalle)` tomando `descuento_porcentaje` de la rúbrica, todos los descuentos sobre la misma base.
- [ ] 3.4 Reescribir `_nota_deterministica`: `suma → descuento → max(0, ...) → min(..., techo)`, cuantizando a 2 decimales **una sola vez al final**.
- [ ] 3.5 (TRIANGULATE) Tests: dos penalizaciones sobre la misma base (20% + 30% = 50); descuento mayor que la suma → nota 0.00; penalización + condición de desaprobación (el techo manda); id de penalización inexistente → sin descuento y log WARNING.
- [ ] 3.6 `nota_antes_penalizaciones` se puebla siempre que haya descuento o techo; queda `NULL` cuando la nota es la suma limpia.
- [ ] CHECKPOINT: las penalizaciones bajan la nota; el techo sigue funcionando igual que antes.

## 4. Backend — Trazabilidad del cálculo

- [ ] 4.1 (RED) Test: el detalle del cálculo (suma previa, descuentos con id/descripción/porcentaje/puntos) queda persistido en `criterios_json`.
- [ ] 4.2 Persistir el detalle bajo una clave hermana de `criterios` en `criterios_json` (sin migración), dejando `penalizaciones_aplicadas` con su shape actual de lista de ids.
- [ ] 4.3 Exponer el detalle en `app/schemas/correccion.py` (`CorreccionResponse`), como campo opcional para no romper correcciones viejas.
- [ ] 4.4 (TRIANGULATE) Test: una corrección vieja (sin la clave nueva) se serializa sin error y el frontend/PDF encuentran los criterios en la ubicación de siempre.
- [ ] CHECKPOINT: cálculo auditable, consumidores existentes sin romper.

## 5. Prompt — El modelo declara, no descuenta (mismo deploy que 3 y 4)

- [ ] 5.1 (RED) Test de caracterización de `_build_penalizaciones_texto` con la salida actual, para tener el antes.
- [ ] 5.2 Reescribir `_build_penalizaciones_texto` en `app/integrations/gemini_correction_client.py`: listar `id` + descripción, sin instrucción de aplicar descuento.
- [ ] 5.3 Actualizar el bloque IMPORTANTE de ambos prompts (código L772-774 y PDF) — sacar "las penalizaciones ya están aplicadas dentro de cada criterio" y poner la instrucción explícita de NO ajustar puntajes por penalización.
- [ ] 5.4 (TRIANGULATE) Test: el prompt de PDF y el camino OpenRouter (`app/integrations/openrouter_client.py`) heredan el mismo texto — verificar que reusan el builder compartido.
- [ ] 5.5 Verificar que el `responseSchema` de `penalizaciones_aplicadas` (array de strings) no cambia: el contrato de salida es el mismo, cambia la instrucción.
- [ ] 🛑 CHECKPOINT: **el paso 5 y los pasos 3-4 se despliegan juntos.** Prompt viejo con backend nuevo produce doble descuento. Confirmar el plan de deploy atómico.

## 6. PDF de devolución — desglose del cálculo

- [ ] 6.1 (RED) Test: corrección con penalización → el PDF incluye suma previa, descuento con descripción y puntos, y nota final.
- [ ] 6.2 (RED) Test: corrección sin penalización ni techo → el PDF es idéntico al actual (caracterización).
- [ ] 6.3 Implementar el bloque de desglose en `app/services/pdf_service.py`, condicionado a que exista descuento o techo.
- [ ] CHECKPOINT: PDF explicable al alumno; caso limpio sin cambios visuales.

## 7. Verificación y cierre

- [ ] 7.1 `pytest` completo en el backend, sin regresiones.
- [ ] 7.2 Reproducir el caso del 2026-08-17 de punta a punta (rúbrica real con penalización del 30%) y confirmar que la nota da ~61 y no 87.
- [ ] 7.3 Reproducir el caso del criterio C5 (0/10 con subcriterios que suman 5) y confirmar que cierra.
- [ ] 7.4 Verificar en staging con una entrega real, revisando el PDF generado.
- [ ] 7.5 Correr de nuevo el script de diagnóstico post-deploy y confirmar que las correcciones previas siguen con su nota original (no se recalculó nada).
- [ ] 7.6 `openspec validate nota-deterministica-penalizaciones --strict`.
