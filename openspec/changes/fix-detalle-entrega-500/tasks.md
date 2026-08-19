> **Gobernanza: 🟢 BAJA.** Autonomía completa si los tests pasan. No depende de ningún otro change de este lote; se puede aplicar hoy.

## 1. Reproducción

- [x] 1.1 (RED) Test que reproduce el bug: consultar el detalle de una entrega con `subido_por_id` nulo → hoy devuelve 500.
- [ ] 1.2 Confirmar en la base de producción cuántas entregas tienen `subido_por_id` nulo, para dimensionar cuántas filas están hoy inaccesibles por su detalle.
- [x] CHECKPOINT: el bug está reproducido en un test antes de tocar nada.

## 2. Arreglo

- [x] 2.1 Hacer que `EntregaDetailResponse.subido_por` admita nulo en `app/schemas/entrega.py`.
- [x] 2.2 Construir el bloque de forma condicional en `app/services/entrega_service.py:716-720`, solo si la relación existe.
- [x] 2.3 Verificar que el test de 1.1 ahora pasa.
- [x] 2.4 (TRIANGULATE) Test de caracterización: una entrega **con** usuario devuelve exactamente lo mismo que antes del change.
- [x] 2.5 (TRIANGULATE) Test: el resto del detalle (comisión, rúbrica, marca de corrección, conteo de versiones anteriores) llega íntegro en el caso sin usuario.
- [x] 2.6 (TRIANGULATE) Test: una entrega inexistente sigue devolviendo 404.
- [x] CHECKPOINT: el endpoint funciona en los dos caminos, sin regresión en el que ya andaba.

## 3. Frontend

- [x] 3.1 ~~Manejar el campo nulo en la vista de detalle de entrega, mostrando un indicador de origen automático.~~ **No aplica: la vista no existe.** `useEntrega` (`hooks/useEntregas.ts:134`) solo se re-exporta desde `hooks/index.ts` y ningún componente la consume. No hay pantalla de detalle de entrega que renderice quién la subió, así que no hay indicador que agregar. En su lugar se corrigió el **tipo**, que sí estaba mal.
- [x] 3.2 Corregir `EntregaDetail` en `features/entregas/types/index.ts`: `subido_por_id` pasa a `number | null`, y `subido_por_nombre: string` se reemplaza por `subido_por: UsuarioInfo | null` (el campo plano que declaraba **nunca existió** en la respuesta del backend).
- [x] 3.3 `npm run typecheck` sin errores. `npm run lint`: 70 problemas (66 errores, 4 warnings) **preexistentes** — mismo conteo con y sin este change, y cero en el archivo tocado. No son regresión de este change.
- [ ] 3.4 **Deuda detectada, fuera de alcance**: `EntregaDetail` sigue declarando `correccion: CorreccionInfo | null`, campo que el backend tampoco devuelve (devuelve `tiene_correccion` y `num_versiones_anteriores`). El tipo es inerte hoy porque nadie lo consume, pero mentiría en cuanto alguien construya la vista. Anotarlo junto al barrido de 4.5.

## 4. Cierre y comunicación

- [x] 4.1 `pytest` completo en el backend, sin regresiones.
- [ ] 4.2 Verificar el endpoint en staging contra una entrega real importada desde Moodle.
- [ ] 4.3 Avisarle a AI-Native que `GET /entregas/{id}` está arreglado, para que puedan sacar el rodeo de su cliente si quieren.
- [ ] 4.4 En el mismo aviso, corregirles el supuesto de su §7.3: el índice único real de entregas es `(rubrica_id, alumno_nombre)` y **no incluye** `comision_id`. La conclusión operativa que sacaron (comparar el `rubrica_id` en el match no es opcional) es correcta; la clave que asumen, no del todo.
- [x] 4.5 Anotar como candidato a change propio el barrido general de schemas de respuesta con campos obligatorios sobre columnas nullable (Open Question del design).
- [x] 4.6 `openspec validate fix-detalle-entrega-500 --strict`.
