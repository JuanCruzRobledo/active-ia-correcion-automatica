# Auditoría QA — 🗃️ CRUDs Mal Implementados

**Sistema:** Active-IA — Corrección Automática (backend FastAPI + frontend React/TS)
**Fecha:** 2026-07-12
**Alcance:** Revisión estática de las operaciones Create / Read / Update / Delete en `backend/app/{routers,services,repositories,models}` contra el contrato CRUD del proyecto, con foco en la regla dura de **soft delete obligatorio** (nunca borrado físico, por auditoría). Se verificó modelo por modelo la existencia del campo de baja lógica y si los repositories lo respetan en todas las queries. No se duplican acá los hallazgos puramente de RBAC/seguridad (los cubre otro auditor), pero sí se reportan reads sin filtro de permisos cuando rompen el contrato CRUD del recurso. El código es la fuente de verdad (N8N fue removido y la doc está desactualizada).

**Resumen del estado del soft delete por modelo** (la regla dice "obligatorio para auditoría"):

| Modelo | Campo de baja lógica | Delete real |
|---|---|---|
| Usuario | `activo` (+ `deleted_at` heredado pero **nunca usado**) | Soft, salvo `ALLOW_HARD_DELETE` |
| Materia / Comision / Rubrica | `activa` | Soft, salvo `ALLOW_HARD_DELETE` (cascada física) |
| TutorNexo | `deleted_at` + `activo` | Soft siempre ✅ |
| **Entrega** | ❌ no tiene (`archivado` es otra cosa) | **Físico siempre** |
| **Correccion** | ❌ no tiene | **Físico siempre** (recorrección) |
| **Cohorte / Cuatrimestre** | `activa` solo en Cohorte | **Físico siempre** |
| **Unidad / ComponenteUnidad / ExamenMateria** | ❌ no tiene | **Físico siempre** |
| EntregaHistorial / Actividad | ❌ (append-only) | Se borran en cascadas físicas |

---

## Índice

| ID | Título | Severidad |
|---|---|---|
| CRUD-001 | Entregas y correcciones se borran físicamente SIEMPRE, sin gate ni ownership | 🔴 Crítica |
| CRUD-002 | `ALLOW_HARD_DELETE` habilita cascadas físicas irreversibles que violan la regla del proyecto | 🟠 Alta |
| CRUD-003 | Recorregir destruye la corrección anterior sin dejar rastro de auditoría | 🟠 Alta |
| CRUD-004 | Los archivos subidos nunca se escriben a disco: `archivo_ruta` es una ruta fantasma | 🟠 Alta |
| CRUD-005 | La sobrescritura de entregas pierde el contenido completo de la versión anterior | 🟠 Alta |
| CRUD-006 | El soft delete del padre no propaga ni se filtra en los hijos (huérfanos lógicos) | 🟠 Alta |
| CRUD-007 | Eliminar una cohorte con cuatrimestres revienta con 500 y el borrado es físico | 🟠 Alta |
| CRUD-008 | Chequeo de duplicados check-then-insert con race → IntegrityError 500 sin handler | 🟡 Media |
| CRUD-009 | `crear_usuario` chequea el username crudo pero guarda `.lower()` → 500 reproducible | 🟡 Media |
| CRUD-010 | Updates parciales con `is not None`: imposible limpiar campos nullable | 🟡 Media |
| CRUD-011 | Los unique constraints quedan ocupados por registros soft-deleted, sin mensaje claro | 🟡 Media |
| CRUD-012 | `GET /entregas` no scopea por rol: contrato de lectura inconsistente con el resto | 🟡 Media |
| CRUD-013 | Cambiar el rol de un usuario deja asignaciones huérfanas (CoordinadorMateria / ComisionTutor) | 🟡 Media |
| CRUD-014 | Unidades y exámenes: borrado físico + `sincronizar` destruye y recrea todo | 🟡 Media |
| CRUD-015 | Tres mecanismos de soft delete conviviendo; `Usuario.deleted_at` es campo muerto | 🟢 Baja |
| CRUD-016 | N+1 en listados y `lazy="selectin"` masivo en Materia | 🟢 Baja |
| CRUD-017 | Inconsistencias menores del contrato: `per_page` 1000, inactivos visibles según endpoint, defaults dispares | 🟢 Baja |

**Conteo:** 🔴 1 · 🟠 6 · 🟡 7 · 🟢 3 — Total: 17

---

### [CRÍTICA] Entregas y correcciones se borran físicamente SIEMPRE, sin gate ni ownership

- **ID**: CRUD-001
- **Ubicación**: `backend/app/repositories/entrega_repository.py:244-252` y `:288-314`; `backend/app/services/entrega_service.py:536-554` y `:586-612`; `backend/app/routers/entregas.py:248-265` y `:318-334`
- **Severidad**: 🔴 Crítica
- **Dimensión**: CRUD
- **Descripción**: El modelo `Entrega` (`models/entrega.py:26`) NO tiene campo de baja lógica (`archivado` es un flag de UI, no un soft delete) y `Correccion` tampoco. `DELETE /entregas/{id}` y `DELETE /entregas/masivo` ejecutan `db.delete()` físico incondicional — no dependen de `ALLOW_HARD_DELETE` como sí lo hacen materias/comisiones/rúbricas/usuarios. La cascada ORM (`cascade="all, delete-orphan"` en `models/entrega.py:132-143`) arrastra la `Correccion` (nota del alumno) y TODO el `EntregaHistorial`. Además el endpoint está gated solo por `require_any_authenticated` (`routers/entregas.py:331`): cualquier tutor puede borrar entregas de comisiones ajenas.
- **Evidencia**: `entrega_repository.py:246`: *"Physically delete an entrega (hard delete)"*. Docstring del router (`entregas.py:327`): *"The entrega is physically deleted from the database"*. No existe endpoint de restore para entregas (sí existe para materias, comisiones, rúbricas y usuarios).
- **Impacto**: Pérdida irreversible del trabajo del alumno, de su nota y de todo el historial de versiones — exactamente lo que la regla de soft delete quiere impedir. El borrado masivo (hasta 100 IDs por request) amplifica el daño. La tabla `Actividad` no registra el borrado de entregas (no hay `registrar_actividad` en `eliminar_entrega` ni en `eliminar_entregas_masivo`), así que ni siquiera queda huella de QUIÉN borró.
- **Reproducción**: Login como TUTOR de la comisión X → `DELETE /api/entregas/{id}` con una entrega corregida de la comisión Y → 204, entrega + corrección + historial desaparecen de la DB.
- **Fix propuesto**: Agregar soft delete a `Entrega` (y por extensión a `Correccion`), respetar `ALLOW_HARD_DELETE` como en los otros recursos, registrar la actividad de borrado, y scopear el permiso al tutor/coordinador de la comisión. Como mínimo inmediato: gatear el hard delete a ADMIN.
- **Esfuerzo estimado**: L

---

### [ALTA] `ALLOW_HARD_DELETE` habilita cascadas físicas irreversibles que violan la regla del proyecto

- **ID**: CRUD-002
- **Ubicación**: `backend/app/core/config.py:125`; `backend/app/repositories/materia_repository.py:313-424`; `backend/app/repositories/comision_repository.py:303-355`; `backend/app/repositories/rubrica_repository.py:341-390`; `backend/app/repositories/usuario_repository.py:286-346`
- **Severidad**: 🟠 Alta
- **Dimensión**: CRUD
- **Descripción**: La regla dura del proyecto es "soft delete SIEMPRE, nunca borrado físico, por auditoría". Sin embargo existe un flag global `ALLOW_HARD_DELETE` (default `False`, presente en `.env.example:92` y `docker-compose.local.yml:49`) que, activado, convierte el `DELETE` de materias, comisiones, rúbricas y usuarios en cascadas físicas: `hard_delete_with_cascade` de una materia borra comisiones → entregas → correcciones → historial → archivos en disco → asignaciones (`materia_repository.py:313-424`). Para usuarios, `hard_delete` además borra su historial de `Actividad` (`usuario_repository.py:340-342`), destruyendo el audit log.
- **Evidencia**: `materia_service.py:352-354`: `if settings.ALLOW_HARD_DELETE: await self.materia_repo.hard_delete_with_cascade(materia)`. Mismo patrón en `usuario_service.py:226-228`, `comision_service.py:417-426`, `rubrica_service.py:449-460`.
- **Impacto**: Un solo cambio de variable de entorno degrada TODO el sistema a borrado destructivo, incluyendo el log de auditoría (`Actividad`). Es una bomba de configuración: el mismo `DELETE /materias/{id}` que ayer era reversible hoy destruye un cuatrimestre entero, y el operador no tiene forma de distinguirlo desde la API (mismo endpoint, mismo 204).
- **Reproducción**: Setear `ALLOW_HARD_DELETE=true` → `DELETE /api/materias/{id}` → materia + comisiones + entregas + correcciones + archivos, todo desaparece sin restore posible.
- **Fix propuesto**: Eliminar el flag o, si el negocio exige purga real, moverla a un endpoint explícito separado (`/purge`), solo ADMIN, con registro de actividad previo al borrado y sin tocar la tabla `Actividad`. Nunca sobrecargar el mismo verbo DELETE con dos semánticas opuestas según config.
- **Esfuerzo estimado**: M

---

### [ALTA] Recorregir destruye la corrección anterior sin dejar rastro de auditoría

- **ID**: CRUD-003
- **Ubicación**: `backend/app/services/correccion_service.py:283-290`; `backend/app/repositories/correccion_repository.py:247-258`
- **Severidad**: 🟠 Alta
- **Dimensión**: CRUD
- **Descripción**: `corregir_individual` (y `recorregir`, que delega en él) hace `correccion_repo.delete(existing_correccion)` — hard delete — antes de crear la nueva corrección. A diferencia de la sobrescritura de entregas (que al menos intenta guardar en `EntregaHistorial`), la recorrección NO guarda ninguna versión previa: la nota anterior, sus criterios, el `raw_response` de la IA y las ediciones manuales (`editado_manualmente`, `editado_por_id`) se pierden.
- **Evidencia**: `correccion_service.py:288-290`: `if existing_correccion: # Delete old correction (hard delete for re-correction)  await self.correccion_repo.delete(existing_correccion)`. El propio repo lo admite en `correccion_repository.py:251`: *"Correcciones do not use soft delete"*.
- **Impacto**: En un sistema cuyo output central es la NOTA del alumno, no queda evidencia de que una entrega tuvo antes otra nota. Ante un reclamo académico ("me habían puesto un 8 y ahora figura un 4") no hay forma de reconstruir qué pasó. Contradice directamente la justificación de la regla de soft delete (auditoría).
- **Reproducción**: Corregir una entrega → editar la nota a mano → `POST /correcciones/entregas/{id}/recorregir` → la edición manual y la nota anterior desaparecen de la DB.
- **Fix propuesto**: Antes de reemplazar, snapshotear la corrección saliente (en `EntregaHistorial.correccion_json`, en una tabla de versiones de corrección, o marcándola inactiva con un campo de baja lógica) y registrar la recorrección en `Actividad`.
- **Esfuerzo estimado**: M

---

### [ALTA] Los archivos subidos nunca se escriben a disco: `archivo_ruta` es una ruta fantasma

- **ID**: CRUD-004
- **Ubicación**: `backend/app/services/entrega_service.py:195-203` (también `:312`, `:894-909`)
- **Severidad**: 🟠 Alta
- **Dimensión**: CRUD
- **Descripción**: En el Create de entregas, `archivo_ruta` se fabrica como string (`f"/uploads/entregas/{hash_sha256[:8]}_{archivo.filename}"`) pero **el contenido del archivo nunca se persiste a disco**: no hay `open()`, `aiofiles`, `shutil` ni escritura alguna en `entrega_service.py`, `consolidacion_service.py` ni `moodle_import_service.py` (verificado por búsqueda). El comentario en `:195-196` lo confiesa: *"archivo_ruta would be updated by file storage service. For now, we keep the same path or generate a new one"*. Solo sobrevive el texto consolidado en la columna `contenido_consolidado` (o el PDF en base64).
- **Evidencia**: `UPLOAD_DIR` está definido en `core/config.py:92` pero ningún service lo usa para escribir. Consecuencia colateral: todos los `os.path.exists(entrega.archivo_ruta)` + `os.remove(...)` de las cascadas de hard delete (`materia_repository.py:363-367`, `comision_repository.py:336-340`, `rubrica_repository.py:376-380`) son código muerto — la ruta jamás existe.
- **Impacto**: (1) El ZIP/PDF original del alumno se pierde en el momento del upload: no hay forma de re-descargar la entrega original ni de re-consolidar con otro modo si el parser tuvo un bug. (2) `archivo_ruta` es un dato mentiroso en la DB y en las respuestas de la API (`EntregaDetailResponse.archivo_ruta`). (3) El "borrado de archivos físicos" documentado en las cascadas es ficción.
- **Reproducción**: Subir una entrega → buscar el archivo en `./uploads/entregas/` → no existe; `archivo_ruta` en la DB apunta a la nada.
- **Fix propuesto**: Decidir el contrato: o se persiste el archivo original en `UPLOAD_DIR` (y entonces las cascadas de limpieza cobran sentido), o se elimina `archivo_ruta` del modelo/respuestas y se blanquea que solo se guarda el consolidado. ⚠️ A confirmar si algún flujo del frontend intenta descargar por esa ruta.
- **Esfuerzo estimado**: M

---

### [ALTA] La sobrescritura de entregas pierde el contenido completo de la versión anterior

- **ID**: CRUD-005
- **Ubicación**: `backend/app/services/historial_service.py:35-80`; `backend/app/models/entrega.py:149-196`
- **Severidad**: 🟠 Alta
- **Dimensión**: CRUD
- **Descripción**: El docstring del modelo promete trazabilidad: *"Se preserva: el archivo anterior, la corrección anterior…"*. En la práctica, `guardar_version_anterior` copia a `EntregaHistorial` solo `contenido_preview` (los primeros 500 caracteres) y `archivo_ruta` (que apunta a un archivo inexistente, ver CRUD-004). El campo `contenido_consolidado` — el único lugar donde vive el contenido real — NO se copia y se pisa en el update siguiente (`entrega_service.py:185`).
- **Evidencia**: `historial_service.py:66-78` construye el registro con `contenido_preview=entrega.contenido_preview` y sin `contenido_consolidado`; `EntregaHistorial` (`models/entrega.py:174-177`) ni siquiera tiene columna para el contenido completo.
- **Impacto**: El "historial de versiones" es cosmético: muestra que HUBO una versión anterior (nombre, tamaño, hash, preview) pero el trabajo del alumno de esa versión es irrecuperable. Combinado con CRUD-004 (no hay archivo físico), la sobrescritura con `sobrescribir=true` es de facto un borrado destructivo de la versión previa.
- **Reproducción**: Subir entrega v1 → subir v2 con `sobrescribir=true` → `GET /entregas/{id}/historial` lista la v1, pero su contenido completo no existe en ningún lado (solo 500 chars de preview).
- **Fix propuesto**: Persistir `contenido_consolidado` (y `pdf_contenido_b64` si aplica) en `EntregaHistorial`, o guardar el archivo original de cada versión en disco con ruta única y conservarlo.
- **Esfuerzo estimado**: S

---

### [ALTA] El soft delete del padre no propaga ni se filtra en los hijos (huérfanos lógicos)

- **ID**: CRUD-006
- **Ubicación**: `backend/app/repositories/comision_repository.py:74-135`; `backend/app/repositories/rubrica_repository.py:82-150`; `backend/app/services/materia_service.py:322-362`
- **Severidad**: 🟠 Alta
- **Dimensión**: CRUD
- **Descripción**: `eliminar_materia` (soft) solo setea `Materia.activa=False`; no toca comisiones, rúbricas ni entregas. Y las queries de los hijos nunca joinean contra el estado del padre: `ComisionRepository.get_all` filtra `Comision.activa` pero no `Materia.activa` (`comision_repository.py:104-105`); ídem `RubricaRepository.get_all` (`rubrica_repository.py:115-116`) y `get_by_materia`. Lo mismo pasa un nivel más abajo: las entregas de una comisión soft-deleted siguen listándose (`entrega_repository.get_all` no mira `Comision.activa`).
- **Evidencia**: En `comision_repository.py:100-135` no existe `join(Materia)` con filtro de `activa`; una comisión activa de una materia eliminada aparece en `GET /comisiones` como si nada. Las validaciones de Create sí protegen la creación nueva (`crear_entrega_individual` valida comisión y rúbrica activas, `entrega_service.py:107-120`), pero los Read/Update de hijos existentes ignoran al padre.
- **Impacto**: "Eliminar" una materia no la elimina operativamente: sus comisiones siguen visibles y operables (subir entregas, corregir, archivar) porque la comisión sigue `activa=True`. El usuario cree que dio de baja la cursada y el sistema sigue aceptando trabajo sobre ella. Datos huérfanos lógicos: hijos activos apuntando a padre inactivo, con comportamiento distinto según el endpoint que los mire.
- **Reproducción**: `DELETE /materias/{id}` (soft) → `GET /comisiones` → las comisiones de esa materia siguen en la lista; `POST /entregas` sobre una de ellas → 201.
- **Fix propuesto**: Definir la semántica de cascada lógica: o el soft delete propaga (desactivar comisiones/rúbricas en la misma transacción), o todas las queries de hijos filtran por padre activo (join + `Materia.activa == True` por default). Documentar la decisión y aplicarla uniforme en TODOS los repositories.
- **Esfuerzo estimado**: M

---

### [ALTA] Eliminar una cohorte con cuatrimestres revienta con 500 y el borrado es físico

- **ID**: CRUD-007
- **Ubicación**: `backend/app/repositories/cohorte_repository.py:77-79` y `:125-127`; `backend/app/models/cohorte.py:46-51` y `:67-71`; `backend/app/services/cohorte_service.py:91-102`
- **Severidad**: 🟠 Alta
- **Dimensión**: CRUD
- **Descripción**: Dos problemas en el mismo Delete. (1) `CohorteRepository.delete` y `CuatrimestreRepository.delete` son borrados físicos (`db.delete`) pese a que `Cohorte` tiene campo `activa` — el flag existe pero el DELETE no lo usa; no hay restore. (2) La relación `Cohorte.cuatrimestres` no define `cascade="all, delete-orphan"` y la FK `Cuatrimestre.cohorte_id` es `nullable=False` sin `ON DELETE`: al borrar una cohorte que tiene cuatrimestres (el guard de `eliminar_cohorte` solo bloquea si hay MATERIAS, `cohorte_service.py:93-101`), SQLAlchemy intenta poner `cohorte_id=NULL` en los hijos cargados y la DB rechaza el NOT NULL → `IntegrityError` → 500 sin mensaje útil. ⚠️ A confirmar en runtime (depende del estado de carga de la relación `lazy="selectin"`, que acá siempre viene cargada por `get_by_id`).
- **Evidencia**: `cohorte_service.py:91-102` valida `count_materias > 0` → 409, pero no valida cuatrimestres; `models/cohorte.py:46-51` no tiene cascade; `cohorte_repository.py:78` hace `await self.db.delete(cohorte)` directo.
- **Impacto**: Caso de uso normal (crear cohorte, agregarle cuatrimestres, arrepentirse y borrarla antes de asignar materias) devuelve 500 en vez de borrar o de dar un 409 explicativo. Y cuando el borrado sí procede (cohorte vacía), es físico e irrecuperable, violando la regla de soft delete.
- **Reproducción**: `POST /cohortes` → `POST /cohortes/{id}/cuatrimestres` → `DELETE /cohortes/{id}` → 500 (IntegrityError por NOT NULL en `cuatrimestres.cohorte_id`).
- **Fix propuesto**: Usar el flag `activa` como soft delete real (el `CohorteUpdate` ya permite togglearlo) o, si se mantiene el físico para cohortes vacías, extender el guard a cuatrimestres y definir la cascada explícitamente.
- **Esfuerzo estimado**: S

---

### [MEDIA] Chequeo de duplicados check-then-insert con race → IntegrityError 500 sin handler

- **ID**: CRUD-008
- **Ubicación**: `backend/app/services/materia_service.py:70-74`; `backend/app/services/comision_service.py:80-88`; `backend/app/services/rubrica_service.py:170-179`; `backend/app/services/usuario_service.py:61-65`; `backend/app/services/cohorte_service.py:61-65`; `backend/app/main.py` (ausencia de handler)
- **Severidad**: 🟡 Media
- **Dimensión**: CRUD
- **Descripción**: Todos los Create siguen el patrón `if await repo.exists(...): raise 409` seguido de `create()` con commit, en requests separados de DB sin lock ni manejo del constraint. Los unique constraints SÍ existen en la DB (`uq_entrega_rubrica_alumno`, `uq_comision_materia_nombre_anio`, `Materia.codigo unique`, etc.), o sea que ante dos requests concurrentes el segundo insert muere con `IntegrityError`. No hay ningún `exception_handler` de `IntegrityError` en el proyecto (verificado por búsqueda en `main.py`, `core/`, `routers/`, `services/`), así que el cliente recibe un 500 genérico en lugar del 409 esperado.
- **Evidencia**: Búsqueda de `IntegrityError|exception_handler` en todo `backend/app` → cero resultados fuera de imports de SQLAlchemy.
- **Impacto**: La carga masiva de entregas y la importación desde Moodle (flujos con concurrencia real: doble click, dos tutores importando la misma comisión) pueden devolver 500 intermitentes difíciles de diagnosticar, con la transacción a medio hacer según el punto de fallo.
- **Reproducción**: Dos `POST /materias` simultáneos con el mismo `codigo` → uno recibe 201, el otro 500 (no 409).
- **Fix propuesto**: Handler global (o try/except en repos de create) que traduzca `IntegrityError` de constraint único a `HTTPException 409` con detalle. Mantener el pre-chequeo solo como UX temprana.
- **Esfuerzo estimado**: S

---

### [MEDIA] `crear_usuario` chequea el username crudo pero guarda `.lower()` → 500 reproducible

- **ID**: CRUD-009
- **Ubicación**: `backend/app/services/usuario_service.py:61` y `:72`
- **Severidad**: 🟡 Media
- **Dimensión**: CRUD
- **Descripción**: El chequeo de duplicados usa el valor tal como vino: `exists_username(data.username)` (case-sensitive, `usuario_repository.py:154-170` compara igualdad exacta), pero el insert guarda `username=data.username.lower()`. Si existe el usuario `jperez` y el admin crea `JPerez`, el exists da falso (no hay "JPerez"), el insert intenta guardar "jperez" y muere contra el unique de `usuarios.username` (`models/usuario.py:38-43`) → 500 (ver CRUD-008: no hay handler). El caso inverso también confunde: el admin cree haber validado "JPerez" pero el sistema materializa otro identificador ("jperez").
- **Evidencia**: `usuario_service.py:61`: `if await self.repo.exists_username(data.username)` vs `:72`: `username=data.username.lower()`. Nótese que el login sí es consistente porque `get_by_username` se llama con lo que el usuario tipea — ⚠️ A confirmar si `auth_service` normaliza a lower antes de buscar.
- **Impacto**: Alta de usuarios con mayúsculas → 500 aleatorio según exista o no la variante lowercase. Error de contrato Create básico: la validación y la escritura operan sobre valores distintos.
- **Reproducción**: `POST /usuarios` con `username="Admin"` teniendo ya al seed `admin` → 500 IntegrityError.
- **Fix propuesto**: Normalizar a lowercase en el schema Pydantic (validator) para que chequeo, insert y login operen sobre el mismo valor canónico.
- **Esfuerzo estimado**: S

---

### [MEDIA] Updates parciales con `is not None`: imposible limpiar campos nullable

- **ID**: CRUD-010
- **Ubicación**: `backend/app/services/materia_service.py:272-278`; `backend/app/services/usuario_service.py:185-191`; `backend/app/services/cohorte_service.py:83-86` y `:143-144`; `backend/app/services/comision_service.py:381-384`; `backend/app/services/rubrica_service.py:392-422`
- **Severidad**: 🟡 Media
- **Dimensión**: CRUD
- **Descripción**: Casi todos los Update resuelven el parcial con `if data.campo is not None: entidad.campo = data.campo`. Eso confunde "no vino el campo" con "vino null": un cliente que manda `{"descripcion": null}` para VACIAR la descripción de una materia es ignorado silenciosamente (200 OK, sin cambio). Aplica a `Materia.descripcion`/`moodle_course_id`, `Usuario.email`, `Cohorte.nombre`, `Cuatrimestre.nombre`, `Comision.moodle_group_id/code`, `Rubrica.descripcion`, etc. El propio codebase ya reconoció el bug y lo arregló para UN solo campo: `rubrica_service.py:413-416` usa `"moodle_assign_id" in data.model_fields_set` con el comentario *"Con `is not None` un null explícito se ignoraba y no se podía vaciar"* — pero el fix no se generalizó.
- **Evidencia**: `rubrica_service.py:413-414` (patrón correcto, aislado) vs `materia_service.py:275-276` (patrón roto, generalizado). El único service que usa `model_dump(exclude_unset=True)` es `correccion_service.py:425`.
- **Impacto**: Campos nullable que una vez seteados no se pueden desetear vía API (hay que tocar la DB a mano). Respuestas 200 que mienten: el cliente cree que limpió el campo. Update contract roto de forma silenciosa, la peor variante.
- **Reproducción**: `PUT /materias/{id}` con `{"descripcion": null}` → 200 → `GET /materias/{id}` → la descripción sigue ahí.
- **Fix propuesto**: Estandarizar el patrón `model_fields_set` / `model_dump(exclude_unset=True)` en todos los Update, distinguiendo "ausente" de "null explícito".
- **Esfuerzo estimado**: M

---

### [MEDIA] Los unique constraints quedan ocupados por registros soft-deleted, sin mensaje claro

- **ID**: CRUD-011
- **Ubicación**: `backend/app/repositories/materia_repository.py:212-228`; `backend/app/repositories/rubrica_repository.py:231-261`; `backend/app/repositories/comision_repository.py:212-239`
- **Severidad**: 🟡 Media
- **Dimensión**: CRUD
- **Descripción**: El soft delete por booleano (`activa=False`) deja la fila en la tabla, y los unique constraints (`Materia.codigo`, `(materia, tipo, numero, anio)` en rúbricas, `(materia, nombre, anio)` en comisiones) no discriminan por estado. Los `exists()` de pre-chequeo tampoco filtran por `activa`. Resultado: no se puede crear una materia con el código de una materia "eliminada" — el 409 dice "El código de materia ya existe" sin mencionar que el conflicto es contra un registro borrado, y el registro borrado no aparece en el listado default, así que para el usuario el código está "libre".
- **Evidencia**: `materia_repository.exists_codigo` (`:212-228`) cuenta sin filtro de `activa`; `GET /materias` default excluye inactivas (`:119-121`) → el usuario no puede ver contra qué choca.
- **Impacto**: Flujo trabado y confuso: "eliminé PROG1 y no me deja crear PROG1 de nuevo, pero PROG1 no existe en el sistema". La única salida es descubrir `include_inactive=true` y el endpoint de restore, nada de lo cual sugiere el mensaje de error. Es la tensión clásica soft-delete-vs-unique sin resolver.
- **Reproducción**: `DELETE /materias/{id}` (soft) → `POST /materias` con el mismo `codigo` → 409 "ya existe", pero `GET /materias` no la muestra.
- **Fix propuesto**: Decidir el contrato: (a) el 409 detecta que el conflicto es con un registro inactivo y ofrece restaurar; o (b) unique parcial (`WHERE activa`) + renombrado del código al soft-deletar (p.ej. sufijo `-deleted-{id}`). Documentar la decisión.
- **Esfuerzo estimado**: M

---

### [MEDIA] `GET /entregas` no scopea por rol: contrato de lectura inconsistente con el resto

- **ID**: CRUD-012
- **Ubicación**: `backend/app/routers/entregas.py:40-85`; comparar con `backend/app/routers/comisiones.py:62-77` y `backend/app/routers/rubricas.py:64-77`
- **Severidad**: 🟡 Media
- **Dimensión**: CRUD
- **Descripción**: El contrato de lectura del sistema es scoping por rol: `GET /comisiones` filtra `tutor_id`/`coordinador_id` según el usuario (`comisiones.py:65-66`), `GET /rubricas` filtra por coordinador (`rubricas.py:65`), `GET /usuarios` restringe a coordinadores. Pero `GET /entregas` — el recurso más sensible — solo exige `require_any_authenticated` y lista TODO: un tutor ve (y puede paginar, filtrar y abrir con `GET /entregas/{id}` + `/contenido`) las entregas y notas de comisiones ajenas. `EntregaService.listar_entregas` ni siquiera acepta un parámetro de scoping (`entrega_service.py`, firma sin `tutor_id`). Los detalles de explotación RBAC los cubre el otro auditor; acá se reporta la ruptura del contrato CRUD de lectura respecto de los recursos hermanos.
- **Evidencia**: `entregas.py:70-72`: docstring *"Authorization: Any authenticated user"* + `require_any_authenticated(current_user)` sin pasar `current_user.id` al service. Contraste directo con `comisiones.py:65-66`.
- **Impacto**: El mismo dato (entregas de la comisión X) está protegido cuando se llega por `/comisiones/{id}` (403 si el tutor no está asignado, `comisiones.py:132-137`) y desprotegido cuando se llega por `/entregas?comision_id=X`. Inconsistencia de contrato que además filtra notas entre comisiones.
- **Reproducción**: Tutor de la comisión A → `GET /entregas?comision_id=B` → 200 con las entregas de B.
- **Fix propuesto**: Replicar el patrón de comisiones: derivar `tutor_id`/`coordinador_id` del `current_user` en el router y filtrar en el repo (join `ComisionTutor` / `CoordinadorMateria`), como ya hace `get_subidas_ids_by_tutor` (`entrega_repository.py:316-347`).
- **Esfuerzo estimado**: M

---

### [MEDIA] Cambiar el rol de un usuario deja asignaciones huérfanas

- **ID**: CRUD-013
- **Ubicación**: `backend/app/services/usuario_service.py:185-195`
- **Severidad**: 🟡 Media
- **Dimensión**: CRUD
- **Descripción**: `actualizar_usuario` permite cambiar `rol` sin ninguna consecuencia sobre las tablas de asignación: un COORDINADOR degradado a TUTOR conserva sus filas en `CoordinadorMateria`, y un TUTOR promovido conserva sus `ComisionTutor`. El sistema valida el rol al CREAR la asignación (`materia_service.py:301-305` exige rol COORDINADOR) pero nunca re-valida las existentes. Además, `obtener_materia` filtra los coordinadores mostrados solo por `activo` (`materia_service.py:225`), no por rol vigente: el ex-coordinador sigue figurando como coordinador de la materia. Lo mismo con el soft delete: desactivar un usuario no limpia ni marca sus asignaciones (se ocultan en materias pero se muestran en comisiones, ver CRUD-017).
- **Evidencia**: `usuario_service.py:188-189`: `if data.rol is not None: user.rol = data.rol` — sin ningún side-effect. `materia_service.py:225`: `if coordinador and coordinador.activo:` (no chequea `rol == COORDINADOR`).
- **Impacto**: Estado inconsistente entre la identidad del usuario y sus permisos materializados: los filtros por `coordinador_id` (`materia_repository.get_by_coordinador`, scoping de rúbricas) siguen matcheando al degradado si algún flujo lo trata como coordinador, y la UI muestra responsables que ya no lo son. Datos huérfanos en tablas N:M.
- **Reproducción**: Asignar coordinador a una materia → `PUT /usuarios/{id}` con `rol=TUTOR` → `GET /materias/{id}` → sigue listado como coordinador.
- **Fix propuesto**: Al cambiar rol (o desactivar), decidir política: limpiar las asignaciones incompatibles en la misma transacción, o bloquear el cambio con 409 mientras existan asignaciones (como hace cohortes con materias).
- **Esfuerzo estimado**: S

---

### [MEDIA] Unidades y exámenes: borrado físico + `sincronizar` destruye y recrea todo

- **ID**: CRUD-014
- **Ubicación**: `backend/app/repositories/unidad_repository.py:76-110`; `backend/app/repositories/examen_repository.py:59-62`; `backend/app/services/unidad_service.py:129-133`
- **Severidad**: 🟡 Media
- **Dimensión**: CRUD
- **Descripción**: `Unidad`, `ComponenteUnidad` y `ExamenMateria` no tienen soft delete y sus Delete son físicos. `UnidadRepository.delete` desvincula las rúbricas (`unidad_id=NULL`) y borra; `sincronizar` (`:82-110`) directamente BORRA todas las unidades de la materia y las recrea desde Moodle — los IDs cambian en cada sync, las rúbricas quedan desvinculadas (`desvincular_rubricas` en el loop, `:93`) y los componentes configurados a mano se pierden con la unidad. `ExamenRepository.delete` borra confiando en FK CASCADE para los recuperatorios que apuntan al examen (`:60`: *"caen por FK CASCADE"*).
- **Evidencia**: `unidad_repository.py:91-95`: `for u in actuales: await self.desvincular_rubricas(u.id); await self.db.delete(u)`. El comentario justifica el borrar+recrear para evitar choques del unique al renumerar.
- **Impacto**: Re-sincronizar unidades desde Moodle desarma silenciosamente la vinculación rúbrica↔unidad (queda `unidad_id=NULL`) y elimina la configuración de componentes/exámenes asociada a las unidades viejas; nada de esto es recuperable ni queda registrado en `Actividad`. Para el dashboard de gestores, el avance histórico calculado contra las unidades viejas pierde su referencia.
- **Reproducción**: Configurar componentes de la unidad 1 → `POST /materias/{id}/unidades/sincronizar` → las unidades tienen IDs nuevos, las rúbricas quedaron sin unidad y los componentes viejos desaparecieron.
- **Fix propuesto**: Sincronizar por upsert (matchear por `moodle_section_id`, actualizar número/nombre in place, crear solo las nuevas, desactivar las ausentes) en lugar de delete+insert; conservar así IDs, vínculos de rúbricas y componentes.
- **Esfuerzo estimado**: M

---

### [BAJA] Tres mecanismos de soft delete conviviendo; `Usuario.deleted_at` es campo muerto

- **ID**: CRUD-015
- **Ubicación**: `backend/app/models/base.py:65-83`; `backend/app/models/usuario.py:25` y `:111`; `backend/app/models/tutor_nexo.py:21`
- **Severidad**: 🟢 Baja
- **Dimensión**: CRUD
- **Descripción**: Conviven tres convenciones: (1) `SoftDeleteMixin.deleted_at` (timestamp) — usado de verdad solo por `TutorNexo`; (2) booleanos `activo`/`activa` — Usuario, Materia, Comision, Rubrica, Cohorte; (3) nada — Entrega, Correccion, Unidad, Examen, Cuatrimestre. `Usuario` hereda el mixin (`usuario.py:25`) pero **ninguna parte del código setea `Usuario.deleted_at`** (verificado por búsqueda: solo tutor_nexo lo escribe): su soft delete real es `activo=False` (`usuario_repository.py:202-216`). El campo existe en la tabla, siempre NULL, y confunde — de hecho `get_active_by_id` dice "not soft-deleted" pero mira `activo`.
- **Evidencia**: `rg "deleted_at"` fuera de `base.py` solo matchea `tutor_nexo_repository.py`. El booleano además pierde información que el timestamp sí da: CUÁNDO se borró (relevante para auditoría, la razón de ser de la regla).
- **Impacto**: Deuda de consistencia: cada modelo nuevo elige convención a dedo (los últimos — cohortes, unidades, exámenes — directamente no implementaron ninguna, ver CRUD-007/014). Queries "activos" con tres formas distintas de escribirse.
- **Reproducción**: N/A (revisión de esquema).
- **Fix propuesto**: Unificar en una sola convención (idealmente `deleted_at`, que aporta el "cuándo"), migrar los booleanos, y aplicar el mixin a los modelos que hoy no tienen baja lógica.
- **Esfuerzo estimado**: L

---

### [BAJA] N+1 en listados y `lazy="selectin"` masivo en Materia

- **ID**: CRUD-016
- **Ubicación**: `backend/app/services/materia_service.py:166-177`; `backend/app/services/comision_service.py:178-191` y `:243-254`; `backend/app/models/materia.py:100-130`
- **Severidad**: 🟢 Baja
- **Dimensión**: CRUD
- **Descripción**: `listar_materias` ejecuta una query extra de coordinadores POR CADA materia de la página (`materia_service.py:169-171`) y `listar_comisiones` una de tutores por cada comisión (`comision_service.py:181-183`); `obtener_comision`/`obtener_materia` hacen además un `get_by_id` de usuario por cada asignación en un loop. En paralelo, `Materia` declara `lazy="selectin"` en TODAS sus relaciones (`materia.py:100-130`: coordinadores, comisiones, rubricas, unidades, examenes), así que cualquier `select(Materia)` — incluso el `get_by_id` para validar existencia — dispara 5 queries adicionales y carga colecciones enteras que el caller no usa; el conteo de comisiones del listado se hace en Python sobre esa colección (`materia_service.py:175-177`) en vez de un COUNT.
- **Evidencia**: Con 20 materias por página: 1 (lista) + 1 (count) + 20 (coordinadores) + 5×20 implícitas de selectin ≈ 120 queries para un listado.
- **Impacto**: Degradación lineal de los listados con el tamaño de página; no rompe funcionalidad (por eso Baja) pero es el anti-patrón N+1 clásico en el corazón del CRUD de lectura.
- **Reproducción**: Activar `DEBUG=true` (echo SQL) y pedir `GET /materias?per_page=100`.
- **Fix propuesto**: Conteos con `func.count` agrupado en la query del listado; relaciones `lazy="raise"` o `"select"` por default y eager loading explícito (`selectinload`) solo donde el caso de uso lo necesita.
- **Esfuerzo estimado**: M

---

### [BAJA] Inconsistencias menores del contrato CRUD entre endpoints

- **ID**: CRUD-017
- **Ubicación**: `backend/app/routers/usuarios.py:38`; `backend/app/services/comision_service.py:243-254` vs `backend/app/services/materia_service.py:220-231`; `backend/app/repositories/usuario_repository.py:104-125`
- **Severidad**: 🟢 Baja
- **Dimensión**: CRUD
- **Descripción**: El mismo recurso o patrón se maneja distinto según el endpoint: (1) `GET /usuarios` acepta `per_page` hasta **1000** (`usuarios.py:38`) mientras todos los demás listados topean en 100 — outlier sin justificación. (2) `GET /usuarios` por default lista TODOS incluyendo soft-deleted (`activo=None` → sin filtro), mientras materias/comisiones/rúbricas excluyen inactivos por default y piden `include_inactive=true` explícito — dos convenciones de visibilidad para el mismo concepto. (3) `obtener_materia` oculta coordinadores inactivos (`materia_service.py:225`: `if coordinador and coordinador.activo`) pero `obtener_comision` muestra tutores inactivos sin filtro (`comision_service.py:245-246`: `if tutor:`) — un usuario deshabilitado desaparece de una pantalla y sigue en la otra.
- **Evidencia**: Citada por ítem.
- **Impacto**: Sorpresas de UX y de integración (el frontend debe conocer la excepción de cada endpoint); superficie para bugs futuros por copiar el patrón "equivocado".
- **Reproducción**: Soft-deletar un tutor asignado → `GET /comisiones/{id}` lo sigue listando; `GET /materias/{id}` ocultaría al coordinador equivalente.
- **Fix propuesto**: Definir convención única (default excluye borrados, cap de paginación uniforme, asignados inactivos siempre visibles-pero-marcados o siempre ocultos) y alinearla en todos los routers/services.
- **Esfuerzo estimado**: S
