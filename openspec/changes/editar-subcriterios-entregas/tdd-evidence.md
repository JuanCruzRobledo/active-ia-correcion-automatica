# TDD Cycle Evidence

## Safety net

- Backend: cuatro suites existentes de persistencia, política, SQLite y PDF: **26 passed**, antes de cambiar producción.
- Frontend: `CorreccionViewEditModal.politica.test.tsx` y `correcciones-service.test.ts`: **8 passed**, antes de cambiar producción. Se restauraron dependencias con `npm ci --no-audit --no-fund`; el lockfile no cambió.
- Los warnings del baseline son deprecaciones existentes de Pydantic y `datetime.utcnow`.

## Ciclos por tarea

Las rutas de tests de backend de esta tabla son relativas a `backend/tests/unit/`; las de frontend a `frontend/src/features/correcciones/`.

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | suites de persistencia/política/PDF y modal/servicio existentes | Regresión | 26 backend + 8 frontend | N/A: baseline | 34/34 | Backend y frontend | N/A: sin producción |
| 1.2 | `services/test_edicion_subcriterios.py` | Unit | 26/26 backend | Import inexistente; luego 13 fallos de reglas; bypass sin snapshot reproducido | 21/21 | 0/máximo/decimales, negativos/exceso/NaN/Infinity, comentario, estructura, traslado, omisión e historia | Helper puro; pruebas verdes |
| 1.3 | `services/test_correccion_edicion_manual.py` | Service | 26/26 backend | 7 fallos: suma, omisión y rechazo sin persistencia | 7/7 | Snapshot, metadatos hermanos, lectura, PDF, nota independiente y cinco rechazos atómicos | Orquestación extraída; 52/52 al integrar con baseline |
| 1.4 | `routers/test_correcciones_subcriterios_http.py`, `routers/test_correcciones_authz.py` | HTTP/Autorización | Baseline backend verde | Rechazo/atomicidad cubiertos por RED de 1.3; contrato HTTP añadido tras GREEN | 29/29 | PUT válido, tres errores 400, pertenencia 403 y universidad/recurso 404 | Sin cambio de lógica de permisos ni endpoint |
| 2.1 | `utils/edicionSubcriterios.test.ts` | Unit | 8/8 frontend | Import de utilidad inexistente; restauración histórica reproducida | 19/19 | Copia, IDs, decimales, límites, sin desglose e ida/vuelta al snapshot | Cálculo y validación fuera del render; verde |
| 2.2 | `components/CorreccionViewEditModal.subcriterios.test.tsx` | UI | 8/8 frontend | Controles inexistentes: 19 fallos del primer grupo de 20 | 24/24 | Modo consulta/edición, dos criterios, desglose y v1 | Modal 863→116 LOC; componentes nuevos menores a 200 |
| 2.3 | `components/CorreccionViewEditModal.subcriterios.test.tsx` | UI | 8/8 frontend | Validación/reset/pending del grupo RED; edición pendiente reproducida en revisión | 24/24 | Cancelar/cerrar/cambiar corrección, payload, error conserva borrador, pending bloquea edición | Estado inmutable y fieldset bloqueado; verde |
| 2.4 | `components/CorreccionViewEditModal.subcriterios.test.tsx`, `components/CorreccionViewEditModal.politica.test.tsx` | UI/Regresión | 4/4 política | Controles/cálculo faltantes en RED modal; ida/vuelta histórica reproducida | 28/28 modal + política | Nota manual, Recalcular, comentario solo, académica 82/final 50 | Ayuda actualizada; política y nota explícita conservadas |
| 3.1 | `services/test_edicion_subcriterios_sqlite.py`, `services/test_pdf_devolucion_subcriterios.py` | Integración/PDF | Baseline PDF y SQLite verde | N/A: verificación integral del comportamiento implementado; ajuste test-only de ARRAY SQLite | 3/3 SQLite; PDF en suite 127/127 | Desglose editado, omitido y v1; guardar/recargar, JSONB y tope 82/50 | Sin cambios de producción para el harness |
| 3.2 | suites anteriores más permisos existentes | Validación | Baseline verde | N/A: validación final | Backend 127/127; nuevos 37/37 tras limpieza de imports | Permisos, política, PDF, HTTP, v1 y cliente anterior | Ruff nuevo código/tests verde; typecheck/lint frontend documentados abajo |

## Verificación final

- Backend: **127 passed**, 75 warnings de deprecación, ejecutando las suites nuevas, baseline, autorización y pertenencia/universidad.
- Después de ordenar imports y fechas de fixtures: las cuatro suites nuevas **37 passed**; no cambió producción después de la suite de 127.
- Ruff de los dos módulos nuevos y cuatro archivos nuevos de test: sin errores.
- `git diff --check -- backend frontend openspec/changes/editar-subcriterios-entregas`: sin errores de whitespace.
- Se mantienen `PUT /correcciones/{id}`, JSONB y permisos existentes; sin migraciones, cambios de rúbrica/prompts, envío Moodle, commits ni push.

- Frontend final: **51 passed** (19 utilidades + 24 modal nuevo + 4 política + 4 servicio); `npm run typecheck` exit 0 y `npx eslint` sobre los nueve archivos tocados exit 0.

## Decisiones y límites verificados

- Excepción de tamaño aprobada explícitamente por el usuario para `correccion_service.py`: **1606→1526 LOC**, delegando edición sin ampliar el servicio. El nuevo módulo de edición tiene 53 LOC, el helper 79 y el schema 405. Los demás archivos nuevos/tocados cumplen el límite aplicable.
- Las referencias iniciales a PATCH en propuesta/diseño/tareas eran incorrectas: el método existente es PUT. Se corrigieron mecánicamente para conservar el contrato real.
- El fixture antiguo de persistencia creaba un desglose sobre `criterios: []`; se ajustó para representar el snapshot ya persistido, manteniendo sus aserciones. La API rechaza agregar subcriterios sin snapshot.
- El harness SQLite compila ARRAY de PostgreSQL como JSON pero devuelve texto. El test integral adapta únicamente esos campos de la respuesta; repositorios, guardado/lectura JSONB, política y PDF siguen siendo reales. No se modificó producción por esta diferencia del harness.
- No se repara un total histórico al editar solo texto. Si los puntajes vuelven al snapshot, cliente y servidor restauran/conservan el total original. Durante una mutación pendiente no se permiten ediciones nuevas que pudieran perderse con la respuesta.
