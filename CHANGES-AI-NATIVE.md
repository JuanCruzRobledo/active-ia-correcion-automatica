# CHANGES-AI-NATIVE.md — Integración con el tutor socrático AI-Native

> Roadmap operativo de los 8 changes derivados del pedido de AI-Native (`active-ia-pedido-de-cambios.md`, 2026-08-18, actualizado 2026-08-19). Cada change vive en `openspec/changes/<nombre>/` con `proposal.md` + `design.md` + `specs/` + `tasks.md`, todos validados (`openspec validate --strict` → 8/8).
>
> El roadmap de la auditoría de julio está en [`CHANGES.md`](CHANGES.md) y es independiente de este.

## Índice

| # | Change | Cubre del pedido | Gobernanza | Esfuerzo | Depende de |
|---|--------|------------------|:----------:|:--------:|:----------:|
| 1 | [`nota-deterministica-penalizaciones`](openspec/changes/nota-deterministica-penalizaciones/) | Bugs 2 y 3 | 🟠 ALTA | M | — |
| 2 | [`motor-anti-falsos-positivos`](openspec/changes/motor-anti-falsos-positivos/) | Bugs 1, 4, 5, 6 | 🟡 MEDIA | L | — |
| 3 | [`trabajos-practicos-y-external-ref`](openspec/changes/trabajos-practicos-y-external-ref/) | §3.1 + §3.2 | 🟡 MEDIA | L | — |
| 4 | [`api-escritura-trabajos-practicos`](openspec/changes/api-escritura-trabajos-practicos/) | §3.3 + §3.3.1 | 🟡 MEDIA | M | #3 |
| 5 | [`correccion-por-ejercicio-con-tests`](openspec/changes/correccion-por-ejercicio-con-tests/) | §3.4 | 🟡 MEDIA | L | #3, #4 |
| 6 | [`cuenta-de-servicio-integracion`](openspec/changes/cuenta-de-servicio-integracion/) | §3.5 | 🔴 CRÍTICA | L | #4 |
| 7 | [`anonimizacion-datos-alumno`](openspec/changes/anonimizacion-datos-alumno/) | §3.6 | 🔴 CRÍTICA | M | #3 |
| 8 | [`fix-detalle-entrega-500`](openspec/changes/fix-detalle-entrega-500/) | §7.2 (no estaba en su lista de bugs) | 🟢 BAJA | S | — |

**Gobernanza**: 🔴 CRÍTICA = análisis y propuesta, aprobación humana explícita antes de escribir código · 🟠 ALTA = proponer y esperar revisión del diff antes de aplicar · 🟡 MEDIA = implementar con checkpoints, surfaceando decisiones no obvias · 🟢 BAJA = autonomía completa si los tests pasan.

## Grafo de dependencias y paralelismo

```
#1 nota-deterministica-penalizaciones          (independiente)
#2 motor-anti-falsos-positivos                 (independiente)
#8 fix-detalle-entrega-500                     (independiente)

#3 trabajos-practicos-y-external-ref ──┬──▶ #4 api-escritura ──┬──▶ #5 correccion-por-ejercicio
                                       │                      └──▶ #6 cuenta-de-servicio
                                       └──▶ #7 anonimizacion
```

**Track A (motor)**: #1 → #2. Se serializan porque ambos tocan `correccion_service.py` y `gemini_correction_client.py`. #1 primero: reescribe `_nota_deterministica`, y #2 encadena su degradación por evidencia después de ese recomputo.

**Track B (integración)**: #3 → #4 → {#5, #6}. #5 y #6 son paralelizables entre sí.

**Track C**: #7 depende solo de #3, pero su inventario de campos tiene que rehacerse si #2 y #5 ya están aplicados (agregan columnas con datos del alumno). Conviene correrlo **después** de #2 y #5, no antes.

**Track D**: #8 no comparte archivos con nadie. Se puede aplicar hoy.

Los tracks A, B y D son 100% paralelos entre sí.

## Orden de ataque recomendado

**8 → 1 → 2 → 3 → 4 → 6 → 5 → 7**

- **#8 primero** porque cuesta una tarde y hay un endpoint de producción devolviendo 500 hoy, para todos los usuarios y no solo para AI-Native.
- **#1 y #2 antes que la integración**, que es la prioridad que el propio cliente puso: *"Los bugs 1, 2 y 3. Afectan notas reales hoy, con o sin esta integración."*
- **#6 antes que #5** aunque el pedido lo liste último: sin cuenta de servicio, AI-Native no puede probar nada contra un entorno real, y es el punto 2 de lo que pidieron para arrancar.
- **#7 al final** porque su inventario de campos depende de las columnas que agregan #2 y #5.

## Detalle por change

### 1. `nota-deterministica-penalizaciones` — Bugs 2 y 3 🟠 ALTA
Las penalizaciones declaradas en la rúbrica pasan a descontar **en el backend**, y el criterio se recomputa como suma de sus subcriterios en rúbricas v2. Hallazgo del análisis: el bug 2 **no es que el modelo desobedezca** — el docstring de `correccion_service.py:156-160` dice explícitamente que las penalizaciones *"no alteran la nota, son solo auditoría/display"*. La aplicación del descuento vivía únicamente en el texto del prompt. **Efecto esperado: las notas nuevas sobre rúbricas con penalización van a bajar.** El change incluye un script de diagnóstico read-only para dimensionar el impacto antes de desplegar. Leer antes: `design.md` D1 (base del descuento) y el gate del paso 1.4 de `tasks.md`.

### 2. `motor-anti-falsos-positivos` — Bugs 1, 4, 5, 6 🟡 MEDIA
Hallazgo del análisis: `Entrega.archivos_incluidos` existe en la base y **nunca llega al prompt** (cero referencias en `correccion_service.py` y en `app/integrations/`). Eso explica el bug 1 solo. El change inyecta el inventario de archivos y el estado de truncado, agrega evidencia citable y verificada por criterio (el backend comprueba que la cita exista literalmente en el código y **degrada, no anula**, si no aparece), suma las reglas de presencia-vs-vínculo y de hardcodeo con ejemplos negativos, y agrega restricciones de cátedra a la rúbrica —el bug 6 no era del modelo, era que la rúbrica no tenía dónde declarar una prohibición—. **Honesto sobre el alcance**: reduce los bugs 4 y 5, no los elimina; eso lo hace #5.

### 3. `trabajos-practicos-y-external-ref` — §3.1 + §3.2 🟡 MEDIA
Entidades `TrabajoPractico` y `Ejercicio`, con `external_ref` en materia, TP y ejercicio. **Decisión de arquitectura**: un ejercicio es dueño de una `Rubrica` existente, no de un modelo de rúbrica paralelo — el motor, el PDF, el historial y el frontend de correcciones no se tocan. **Punto no obvio**: `uq_rubrica_materia_tipo_numero_anio` impide hoy que cuatro ejercicios del mismo TP tengan cuatro rúbricas; pasa a ser un índice único **parcial** (`WHERE ejercicio_id IS NULL`), replicando el patrón ya usado en `uq_entrega_rubrica_alumno`. Es el único paso no aditivo del lote y tiene gate propio. `cmid` no se toca.

### 4. `api-escritura-trabajos-practicos` — §3.3 + §3.3.1 🟡 MEDIA
`POST /trabajos-practicos/`, `PUT /by-ref/{ref}` idempotente y `GET /by-ref/{ref}`. La respuesta devuelve `external_ref` + `rubrica_id` por ejercicio. **La decisión que sostiene todo**: los ejercicios se emparejan por `external_ref`, nunca por orden ni por título, y **el `rubrica_id` de un ejercicio es estable de por vida** — si rotara, las correcciones ya hechas quedarían colgando de una rúbrica que el cliente ya no asocia a ese ejercicio. Los casos ocultos con salida esperada se **rechazan** con 422, no se descartan en silencio.

### 5. `correccion-por-ejercicio-con-tests` — §3.4 🟡 MEDIA
`POST /correcciones/ejercicios/{ref}/corregir` con `resultado_tests`, que viaja al prompt como **hecho establecido**. **Hueco que el pedido no vio**: `entregas.comision_id` es `NOT NULL` y AI-Native no tiene comisiones — se resuelve con `Materia.comision_integracion_id` configurable una vez, más un `comision_external_ref` opcional; el contrato que su cliente ya implementó no cambia. **Decisión clave**: la regla *"con `compila: false` no cierren criterios del tipo el programa funciona"* se implementa determinísticamente con un campo de rúbrica `depende_de_ejecucion`, no como instrucción de prompt — mismo criterio que #1. **Tiene un gate no técnico**: la respuesta sobre la personería (§8.1) bloquea el despliegue con datos de alumnos reales, y no la cierra el equipo técnico.

### 6. `cuenta-de-servicio-integracion` — §3.5 🔴 CRÍTICA
Identidad de máquina con credencial hasheada de larga duración, alcance **por materia** (no por rol), permisos explícitos, expiración obligatoria, revocación inmediata, clave de IA propia y auditoría atribuible. **Punto de inserción**: como todos los guards de `permissions.py` consumen `ContextoUniversidad` y no el `Usuario`, un contexto compatible hereda el sistema de permisos sin reescribirlo. **Regla dura verificada con tests**: una cuenta de servicio NO satisface ninguna verificación de rol humano. En este change los tests negativos se escriben y pasan **antes** que los positivos.

### 7. `anonimizacion-datos-alumno` — §3.6 🔴 CRÍTICA
El pedido dice `DELETE /alumnos/{ref}/datos`, y la regla dura del proyecto dice que los DELETE son siempre soft (CRUD-002). Se resuelve **anonimizando**: se destruye código, devolución, evidencia, respuesta cruda del proveedor y el pseudónimo; se conserva el registro académico despersonalizado (nota, rúbrica, comisión, fechas). **Alcanza al historial** — `entregas_historial` guarda copias completas del código, y anonimizar solo las filas vivas sería un placebo. El riesgo principal es de **exhaustividad**, no de lógica: el paso 6.3 de `tasks.md` es un barrido completo de la base que tiene que devolver cero coincidencias.

### 8. `fix-detalle-entrega-500` — §7.2 🟢 BAJA
AI-Native reportó al pasar que `GET /entregas/{id}` devuelve 500 y lo rodearon. Causa raíz confirmada: `entrega_service.py:716-720` accede a `entrega.subido_por.id` sin comprobar la relación, y `subido_por_id` es nullable — las entregas importadas desde Moodle no tienen usuario que las suba. El schema promete un objeto que no siempre hay. **El detalle de una entrega importada es hoy inaccesible para todo el mundo**, y por ahí entra la mayoría de las entregas del sistema.

## Lo que NO está en estos changes

Del propio pedido (§5), y respetado tal cual:

- Active-IA **no ejecuta código**. El sandbox es de AI-Native.
- Active-IA **no calcula la nota final del TP**. Devuelve nota por ejercicio.
- Active-IA **no escribe nada** del lado del cliente. La integración es de una sola dirección.
- **No hay cambios en el flujo de Moodle.** `cmid` sigue funcionando igual.
- **No hay corrección en lote.** Se dispara de a un ejercicio.

## Bloqueantes que no resuelve ninguna línea de código

1. **Personería / responsable de datos (§8.1).** ¿AI-Native y Active-IA son el mismo responsable frente al consentimiento que firmaron los alumnos del piloto? Si no lo son, mandar código de un alumno es una cesión a un tercero y el consentimiento tiene que decirlo. Bloquea el despliegue de #5 con datos reales. Está como tarea con gate en `openspec/changes/correccion-por-ejercicio-con-tests/tasks.md` §8.
2. **Canal de entrega de la credencial de servicio.** No por correo ni por chat. Definirlo antes de generarla (`cuenta-de-servicio-integracion/tasks.md` §0.2).
3. **Política de retención de respaldos.** La anonimización cubre la base viva, no los respaldos históricos. Hay que declarárselo al cliente, no esconderlo.

## Cosas para avisarle a AI-Native

- **Su §7.3 tiene un supuesto inexacto**: el índice único real de entregas es `(rubrica_id, alumno_nombre)` y **no incluye** `comision_id`. La conclusión operativa que sacaron (comparar el `rubrica_id` en el match no es opcional) es correcta; la clave que asumen, no del todo.
- **`GET /entregas/{id}` se arregla en #8**, por si quieren sacar el rodeo de su cliente.
- **El contrato de #4 conviene entregárselo antes del deploy**, para que apunten su cliente a staging y no directamente a producción.
- **Confirmar el contrato contra su doble HTTP** (`tests/e2e/smoke/test_smoke_activeia_doble.py`), que cubre camino feliz, 409, motor saturado, credencial inválida y respuesta sin id.

## Verificación general al cerrar los 8

- Backend: `pytest` completo sin regresiones (Strict TDD: safety net → RED → GREEN → triangulate → refactor por change).
- Frontend: `npm run typecheck` y `npm run lint` sin errores, sin `any`.
- Test de no regresión del flujo de Moodle completo: importar → corregir → devolver, sin tocar TPs ni ejercicios.
- Reproducir los seis casos control del pedido y **reportar el resultado de cada uno, incluidos los que sigan fallando**.
- Cada change se archiva (`openspec archive`) al terminar.
