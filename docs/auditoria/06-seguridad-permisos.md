# Auditoría de Seguridad y Permisos — Active-IA

> Dimensión: 🔐 **Seguridad y Permisos**
> Auditoría defensiva autorizada del propio sistema. Backend FastAPI (`backend/app`).
> Fecha: 2026-07-12 · Rama `main`

## Alcance

Se auditó la superficie de autenticación, autorización (RBAC) y manejo de secretos del backend:

- **Auth core**: `core/security.py`, `core/dependencies.py`, `core/config.py`, `routers/auth.py`, `services/auth_service.py`
- **Autorización RBAC**: `core/permissions.py` (validadores de rol + guards async por recurso) y su uso endpoint por endpoint en `routers/`
- **Router público sin JWT**: `routers/public_docs.py` + `services/devolucion_link_service.py`
- **Correcciones y fuga entre roles**: `routers/correcciones.py`, `routers/entregas.py`, `routers/documentos.py`, `services/correccion_service.py`
- **Uploads**: `services/consolidacion_service.py`, `services/entrega_service.py`
- **Secretos e integraciones IA**: `integrations/*.py`, almacenamiento de API keys y credenciales Moodle
- **Config de despliegue**: `docker-compose*.yml`, `.gitignore`, seed de admin

Fuera de alcance: frontend (salvo almacenamiento de token, mencionado como contexto), pentesting dinámico, revisión de dependencias (CVEs).

---

## Índice de hallazgos

| ID | Título | Severidad |
|----|--------|-----------|
| SEC-001 | IDOR masivo en correcciones: cualquier usuario ve/edita/borra correcciones ajenas | 🔴 Crítica |
| SEC-002 | IDOR masivo en entregas: cualquier usuario lista, lee, sobrescribe y borra entregas de otras comisiones | 🔴 Crítica |
| SEC-003 | Secretos por defecto inseguros en `config.py` (SECRET_KEY / ENCRYPTION_KEY) | 🔴 Crítica |
| SEC-004 | IDOR en documentos: descarga de PDFs/Excel de cualquier comisión/corrección | 🟠 Alta |
| SEC-005 | Sin límite de tamaño de upload ni protección anti ZIP-bomb (descompresión ilimitada) | 🟠 Alta |
| SEC-006 | Guards placeholder `require_*_of_materia/comision` no consultan la DB | 🟠 Alta |
| SEC-007 | JWT sin expiración práctica (7 días), sin refresh ni revocación; token en localStorage | 🟡 Media |
| SEC-008 | Rate limiting definido en config pero NO implementado (login sin throttle por IP) | 🟡 Media |
| SEC-009 | Token de devolución pública con TTL de 90 días y sin revocación | 🟡 Media |
| SEC-010 | `docker-compose.local.yml` con SECRET_KEY/ENCRYPTION_KEY débiles hardcodeadas | 🟡 Media |
| SEC-011 | Credenciales Moodle: contraseña de usuario real cifrada reversible (AES) en vez de token WS | 🟡 Media |
| SEC-012 | Mensajes de error 500 exponen `str(e)` al cliente | 🟢 Baja |
| SEC-013 | Enumeración de usuarios por mensajes de login diferenciados | 🟢 Baja |
| SEC-014 | Credencial admin por defecto `admin/admin123` en seed | 🟢 Baja |

---

## Fichas

### 🔴 IDOR masivo en correcciones: cualquier usuario ve/edita/borra correcciones ajenas

- **ID**: SEC-001
- **Ubicación**: `backend/app/routers/correcciones.py:202-295` (obtener/editar), `:75-151` (corregir/recorregir)
- **Severidad**: 🔴 Crítica
- **Dimensión**: Seguridad
- **Descripción**: TODOS los endpoints de `correcciones.py` usan únicamente `require_any_authenticated(current_user)` — que, como confirma `permissions.py:236-260`, solo verifica que haya sesión y devuelve al usuario sin más chequeo. No se valida en ningún punto que la corrección/entrega pertenezca a una comisión asignada al tutor ni a una materia del coordinador. Los servicios (`CorreccionService.obtener_correccion`, `editar_correccion`) tampoco reciben el `current_user` para filtrar por pertenencia.
- **Evidencia**:
  - `correcciones.py:222` → `obtener_correccion` solo hace `require_any_authenticated`; llama `service.obtener_correccion(correccion_id)` sin usuario.
  - `correcciones.py:288-295` → `editar_correccion` idem; permite cambiar `nota`, `criterios_json`, `fortalezas` de cualquier `correccion_id`.
  - `correcciones.py:232-253` → `obtener_correccion_por_entrega` expone corrección por `entrega_id` arbitrario.
  - `recorregir_entrega` (`:141`) hace hard-delete de la corrección existente y regenera, sobre cualquier `entrega_id`.
- **Impacto**: Un TUTOR (o COORDINADOR) autenticado puede leer datos de alumnos de otras comisiones/materias, **alterar notas** de correcciones que no le corresponden, y borrar/regenerar correcciones ajenas. Es una fuga de datos entre roles y una falla de integridad de calificaciones. Iterando IDs secuenciales (`/correcciones/1`, `/2`, …) se enumera todo el sistema.
- **Reproducción**: Autenticarse como tutor A. `GET /api/v1/correcciones/{id}` con un `id` de una comisión de tutor B → 200 con los datos. `PUT /api/v1/correcciones/{id}` con `{"nota": 100}` → modifica la nota ajena.
- **Fix propuesto**: Introducir una verificación de pertenencia por recurso análoga a las funciones `verificar_acceso_*` ya existentes. Resolver la comisión de la entrega asociada a la corrección y validar contra `ComisionTutor` (tutor) o `CoordinadorMateria` (coordinador), con bypass para ADMIN. Aplicarlo en cada endpoint (o en el servicio, recibiendo `current_user`). Reusar el patrón async de `permissions.py:487` (`verificar_acceso_comision`).
- **Esfuerzo estimado**: M

---

### 🔴 IDOR masivo en entregas: cualquier usuario lista, lee, sobrescribe y borra entregas de otras comisiones

- **ID**: SEC-002
- **Ubicación**: `backend/app/routers/entregas.py:40-334` (todos los endpoints)
- **Severidad**: 🔴 Crítica
- **Dimensión**: Seguridad
- **Descripción**: Igual que SEC-001, el router de entregas solo aplica `require_any_authenticated`. No hay filtrado por comisión del tutor ni materia del coordinador en:
  - `listar_entregas` (`:72`) — el filtro `comision_id` es opcional y no restringe a las comisiones propias; sin filtro devuelve entregas de todas las comisiones.
  - `obtener_entrega` (`:286`) y `obtener_contenido_entrega` (`:312`) — leen cualquier entrega por ID, incluido el **código fuente consolidado** del alumno.
  - `crear_entrega` (`:121`) — acepta cualquier `comision_id`/`rubrica_id` en el form sin validar que el tutor esté asignado.
  - `eliminar_entrega` (`:331`), `eliminar_entregas_masivo` (`:262`), `archivar_entregas` (`:242`) — borran/archivan por lista de IDs arbitrarios (hard delete real, ver `entrega_service.py:554,586`).
- **Evidencia**: `entrega_service.py:536-613` — `eliminar_entrega`/`eliminar_entregas_masivo` solo verifican existencia (404), nunca pertenencia. `listar_entregas` en el service no recibe `current_user`.
- **Impacto**: Fuga de datos entre comisiones (código y datos de alumnos), y **destrucción de datos** ajenos: un tutor puede borrar en masa entregas de otras comisiones enviando un rango de IDs. Combinado con el hard delete (`entrega_repo.delete_by_ids`) es irreversible.
- **Reproducción**: Tutor A: `DELETE /api/v1/entregas/masivo` con `{"ids":[1,2,3,...,100]}` → borra entregas sin importar comisión. `GET /api/v1/entregas/{id}/contenido` → código de cualquier alumno.
- **Fix propuesto**: Filtrar `listar_entregas` por las comisiones del usuario (join con `ComisionTutor`/`CoordinadorMateria`) y validar pertenencia por recurso en get/create/delete/archive resolviendo la comisión de cada entrega. ADMIN bypass. Considerar prohibir el hard delete masivo o exigir rol elevado.
- **Esfuerzo estimado**: L

---

### 🔴 Secretos por defecto inseguros en `config.py`

- **ID**: SEC-003
- **Ubicación**: `backend/app/core/config.py:53,62`
- **Severidad**: 🔴 Crítica
- **Dimensión**: Seguridad
- **Descripción**: `SECRET_KEY` (firma de JWT) y `ENCRYPTION_KEY` (AES/Fernet de las API keys) tienen valores por defecto en código: `"change-me-in-production-use-openssl-rand-hex-32"` y `"change-me-in-production-use-fernet-generate-key"`. Si el `.env` no los define, la app arranca igual con esos valores. No hay validador que aborte el arranque en producción (`DEBUG=False`) con secretos por defecto.
- **Evidencia**:
  - `config.py:53` → `SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"`
  - `config.py:62` → `ENCRYPTION_KEY: str = "change-me-in-production-use-fernet-generate-key"` (además no es una Fernet key válida base64 de 32 bytes; si se usara, `Fernet()` fallaría — pero el riesgo es un valor débil real).
- **Impacto**: Con `SECRET_KEY` conocida un atacante **forja JWT arbitrarios** (cualquier `user_id`/`rol=ADMIN`) → compromiso total. Con `ENCRYPTION_KEY` conocida se descifran todas las API keys de Gemini/OpenRouter y contraseñas Moodle almacenadas.
- **Reproducción**: Desplegar sin definir las envs; firmar un JWT con la clave pública del repo y payload `{"user_id":1,"rol":"ADMIN","exp":...}`.
- **Fix propuesto**: Validador Pydantic que, si `DEBUG=False`, rechace el arranque cuando `SECRET_KEY`/`ENCRYPTION_KEY` sean los defaults o tengan longitud/entropía insuficiente. Idealmente sin defaults (campo requerido) y documentar generación. Rotar claves ya expuestas en git.
- **Esfuerzo estimado**: S

---

### 🟠 IDOR en documentos: descarga de PDFs/Excel de cualquier comisión/corrección

- **ID**: SEC-004
- **Ubicación**: `backend/app/routers/documentos.py:49-194`
- **Severidad**: 🟠 Alta
- **Dimensión**: Seguridad
- **Descripción**: Todos los endpoints de generación de documentos usan solo `require_any_authenticated`. `descargar_pdf_correccion` (`:61`), `descargar_pdfs_lote` (`:107`), `descargar_pdfs_seleccionados` (`:144`) y `exportar_notas_excel` (`:177`) reciben `correccion_id`/`comision_id`/`rubrica_id`/lista de `entrega_ids` sin validar pertenencia.
- **Evidencia**: `documentos.py:49-87` — genera el PDF de devolución de cualquier `correccion_id`. `pdf_service.py` no recibe usuario para filtrar.
- **Impacto**: Exfiltración de devoluciones (nota, comentarios, datos del alumno) y planillas de notas completas de comisiones ajenas en PDF/Excel. Misma clase que SEC-001 pero sobre documentos exportables.
- **Reproducción**: `GET /api/v1/documentos/comisiones/{X}/rubricas/{Y}/excel` con IDs de otra materia → descarga el Excel de notas.
- **Fix propuesto**: Aplicar la misma verificación de pertenencia por recurso (comisión/materia) antes de generar el documento. Reusar `verificar_acceso_materia_de_comision` / `verificar_acceso_comision`.
- **Esfuerzo estimado**: M

---

### 🟠 Sin límite de tamaño de upload ni protección anti ZIP-bomb

- **ID**: SEC-005
- **Ubicación**: `backend/app/services/consolidacion_service.py:216-288`, `backend/app/services/entrega_service.py:136`, `backend/app/routers/entregas.py:88-221`
- **Severidad**: 🟠 Alta
- **Dimensión**: Seguridad
- **Descripción**: Aunque `config.py:93` define `MAX_UPLOAD_SIZE = 100MB`, **ese valor no se usa en ninguna parte** (grep sin coincidencias fuera de la definición). El endpoint de upload lee el archivo completo en memoria (`await archivo.read()`, `entrega_service.py:136`) sin chequear tamaño, y la consolidación de ZIP (`zf.read(info)` en `consolidacion_service.py:281`) descomprime todas las entradas sin límite de ratio ni de tamaño total descomprimido. No hay tope de cantidad de archivos ni de profundidad.
- **Evidencia**:
  - `config.py:93` define el límite; `MAX_UPLOAD_SIZE` no aparece referenciado en `app/`.
  - `consolidacion_service.py:279-282` lee cada entrada del ZIP a memoria sin verificar `info.file_size`.
  - Carga masiva (`entrega_service.py:669+`) itera carpetas de alumnos y consolida cada una, amplificando el consumo.
- **Impacto**: DoS por agotamiento de memoria/CPU: un ZIP-bomb (p.ej. 100KB → varios GB) o un upload muy grande tumba el worker. Sin autenticación fina (SEC-002) cualquier usuario lo dispara.
- **Reproducción**: Subir un ZIP-bomb clásico a `POST /api/v1/entregas/masiva`.
- **Fix propuesto**: Validar `Content-Length` / tamaño leído contra `MAX_UPLOAD_SIZE` antes de procesar; al descomprimir, acumular `info.file_size` y abortar si supera un tope o si la ratio comprimido/descomprimido excede un umbral; limitar cantidad de entradas. Rechazar temprano con 413.
- **Esfuerzo estimado**: M

---

### 🟠 Guards placeholder `require_*_of_materia/comision` no consultan la DB

- **ID**: SEC-006
- **Ubicación**: `backend/app/core/permissions.py:268-363`
- **Severidad**: 🟠 Alta
- **Dimensión**: Seguridad
- **Descripción**: `require_coordinador_of_materia` (`:268`) y `require_tutor_of_comision` (`:317`) son placeholders con `TODO`: solo verifican el ROL genérico (que el usuario sea coordinador/tutor), no que esté asignado a ESA materia/comisión. Las versiones reales async (`verificar_acceso_materia` `:366`, `verificar_acceso_comision` `:487`, etc.) sí consultan `CoordinadorMateria`/`ComisionTutor`. **Verificado**: los placeholders NO están importados en ningún router (grep solo los encuentra definidos y en sus propios docstrings), así que hoy no son explotables directamente. El riesgo es de *trampa latente*: quien los use creyendo que validan pertenencia abrirá un agujero silencioso.
- **Evidencia**: `permissions.py:304-313` — el cuerpo de `require_coordinador_of_materia` termina con `# TODO: Add database check` sin ejecutarlo. La grep de uso muestra que los routers usan exclusivamente las variantes `verificar_acceso_*`.
- **Impacto**: Bajo hoy (sin uso), pero alto si un desarrollador los adopta. Deuda de seguridad peligrosa por nombres que prometen más de lo que hacen.
- **Fix propuesto**: Eliminar los placeholders o convertirlos en `async` que deleguen en las `verificar_acceso_*` reales, para que sea imposible usar la versión falsa. Como mínimo, renombrarlos para que no sugieran validación de pertenencia.
- **Esfuerzo estimado**: S

---

### 🟡 JWT sin expiración práctica, sin refresh ni revocación; token en localStorage

- **ID**: SEC-007
- **Ubicación**: `backend/app/core/config.py:55`, `backend/app/core/security.py:73-116`, `frontend/src/features/auth/services/auth-service.ts:40`
- **Severidad**: 🟡 Media
- **Dimensión**: Seguridad
- **Descripción**: El access token dura `ACCESS_TOKEN_EXPIRE_DAYS = 7` días, es el único token (no hay refresh token de corta vida) y no existe lista de revocación ni `jti`. Deshabilitar un usuario invalida el login futuro (`get_current_user` chequea `activo`), pero un token ya emitido sigue siendo criptográficamente válido hasta 7 días. El frontend lo guarda en `localStorage` (accesible desde JS → expuesto a XSS).
- **Evidencia**: `config.py:55` (7 días); `security.py:100` (`exp` = ahora + delta); `auth-service.ts:40` (`localStorage.setItem(TOKEN_KEY, ...)`). Nota: `get_current_user` sí revalida `user.activo` contra DB en cada request, lo que mitiga parcialmente.
- **Impacto**: Ventana amplia de robo de sesión; un token filtrado (XSS, log, cache) da 7 días de acceso sin forma de cortarlo salvo desactivar la cuenta.
- **Fix propuesto**: Reducir TTL del access token (p.ej. 15–60 min) + refresh token rotatorio; considerar `jti` + blacklist para logout real. Evaluar cookie `HttpOnly`+`SameSite` en vez de localStorage.
- **Esfuerzo estimado**: L

---

### 🟡 Rate limiting definido en config pero no implementado

- **ID**: SEC-008
- **Ubicación**: `backend/app/core/config.py:110-117`, `backend/app/routers/auth.py:42`, `backend/app/main.py:71-83`
- **Severidad**: 🟡 Media
- **Dimensión**: Seguridad
- **Descripción**: `config.py` define `RATE_LIMIT_LOGIN_*`, `RATE_LIMIT_API_*`, `RATE_LIMIT_CORRECCION_*`, pero no hay middleware ni dependencia que los aplique (sin `slowapi`/`limiter`; grep sin coincidencias de uso). El login solo tiene bloqueo por cuenta tras 5 intentos (`auth_service.py:32,190`), lo cual es por-usuario, no por-IP: no frena fuerza bruta distribuida ni enumeración de usuarios contra muchas cuentas, ni protege endpoints costosos (corrección IA) de abuso.
- **Evidencia**: `main.py` no registra ningún rate limiter; los settings `RATE_LIMIT_*` no se leen en ningún lado.
- **Impacto**: Fuerza bruta de contraseñas por IP (rotando usernames), abuso de endpoints de corrección (costo de API IA) y DoS aplicativo.
- **Fix propuesto**: Integrar `slowapi` (o rate limit en el reverse proxy/nginx) aplicando los umbrales ya definidos: login por IP, API general y corrección. Es "cablear" config que ya existe.
- **Esfuerzo estimado**: M

---

### 🟡 Token de devolución pública con TTL de 90 días y sin revocación

- **ID**: SEC-009
- **Ubicación**: `backend/app/services/devolucion_link_service.py:22,33-59`, `backend/app/routers/public_docs.py:24-52`
- **Severidad**: 🟡 Media
- **Dimensión**: Seguridad
- **Descripción**: El endpoint público `/api/v1/public/devoluciones/{token}` sirve el PDF de devolución sin JWT, validando solo un token firmado. Auditando la superficie según lo pedido:
  - **¿Expira?** Sí — es un JWT con `exp`, TTL por defecto **90 días** (`DEFAULT_TTL_DIAS = 90`). Firmado con `SECRET_KEY` (HMAC), no adivinable por fuerza bruta si la clave es fuerte (ver dependencia con SEC-003).
  - **¿Enumera recursos?** No directamente: cada token apunta a UN `correccion_id` y el endpoint no acepta el id crudo; sin el token firmado no se sirve nada. El `correccion_id` va dentro del token (no en la URL como parámetro manipulable).
  - **Riesgos reales**: (1) TTL de 90 días es largo para un enlace que viaja por Moodle/email; (2) no hay revocación — si el link se filtra, el PDF (datos del alumno) queda accesible 90 días; (3) depende por completo de la fortaleza de `SECRET_KEY` (si se cumple SEC-003, los tokens son forjables y ahí SÍ se vuelve enumerable: forjando tokens con `correccion_id` 1..N).
- **Evidencia**: `devolucion_link_service.py:22` (`DEFAULT_TTL_DIAS = 90`), `:41` (firma con `settings.SECRET_KEY`), `public_docs.py:31` (valida token, no id).
- **Impacto**: Fuga acotada de una devolución por link filtrado, sin corte posible en 90 días. Escala a crítica solo si `SECRET_KEY` es débil (SEC-003).
- **Fix propuesto**: Reducir TTL (p.ej. 7–14 días) y/o incluir un componente revocable (versión/nonce almacenado en la corrección que se invalide al regenerar). Mantener `SECRET_KEY` robusta es prerequisito.
- **Esfuerzo estimado**: M

---

### 🟡 `docker-compose.local.yml` con claves débiles hardcodeadas como default

- **ID**: SEC-010
- **Ubicación**: `docker-compose.local.yml:51,54`
- **Severidad**: 🟡 Media
- **Dimensión**: Seguridad
- **Descripción**: El compose local define `SECRET_KEY: ${SECRET_KEY:-dev-secret-change-in-production}` y `ENCRYPTION_KEY: ${ENCRYPTION_KEY:-dev-encryption-key-32-chars!!}` con fallbacks débiles. Está pensado para dev, pero el patrón `:-default` significa que si alguien reutiliza este compose en un entorno accesible sin exportar las envs, arranca con claves públicas del repo. El de EasyPanel (`docker-compose.easypanel.yml:77,80`) sí usa `:?requerido` (falla si falta) — patrón correcto.
- **Evidencia**: `docker-compose.local.yml:51,54` (fallback débil) vs `docker-compose.easypanel.yml:77,80` (`:?SECRET_KEY requerido`).
- **Impacto**: Mismo vector que SEC-003 si el compose local se expone. Confinado a dev en el uso previsto.
- **Fix propuesto**: Documentar claramente "solo local" y/o alinear con el patrón `:?` de EasyPanel. No versionar valores que parezcan claves reales.
- **Esfuerzo estimado**: S

---

### 🟡 Credenciales Moodle: contraseña real del usuario cifrada de forma reversible

- **ID**: SEC-011
- **Ubicación**: `backend/app/models/usuario.py:72`, `backend/app/routers/usuarios.py:186-193`, `backend/app/services/moodle_service.py:206`, `backend/app/schemas/usuario.py:181-185`
- **Severidad**: 🟡 Media
- **Dimensión**: Seguridad
- **Descripción**: El sistema almacena la **contraseña personal de Moodle** del tutor cifrada con AES/Fernet (`moodle_password_encrypted`) y la descifra en runtime para pedir un token vía `/login/token.php` (`moodle_service.py:206`). Es cifrado reversible con `ENCRYPTION_KEY`: quien acceda a la DB + clave (ver SEC-003) recupera contraseñas de cuentas institucionales reales, no un token acotado.
- **Evidencia**: `usuario.py:72` columna; `moodle_service.py:206` `password = decrypt_api_key(password_encrypted)`; `schemas/usuario.py:182` recibe `moodle_password` en claro por API.
- **Impacto**: Concentra secretos de terceros (credenciales del LMS). Una brecha de DB expone acceso a Moodle de los tutores, con posible reutilización de contraseña en otros sistemas.
- **Fix propuesto**: Preferir almacenar solo el **token de web service de Moodle** (revocable, de alcance limitado) en lugar de la contraseña; si se debe usar login/token, minimizar el TTL de cacheo (ya hay cache en memoria) y reforzar la custodia de `ENCRYPTION_KEY` (KMS/secret manager). Documentar el riesgo al usuario.
- **Esfuerzo estimado**: L

---

### 🟢 Mensajes de error 500 exponen `str(e)` al cliente

- **ID**: SEC-012
- **Ubicación**: `backend/app/routers/perfil.py:169-173`, `backend/app/services/consolidacion_service.py:250-254,317-321,382-385`
- **Severidad**: 🟢 Baja
- **Dimensión**: Seguridad
- **Descripción**: Varios `except Exception as e` devuelven `detail=f"...: {str(e)}"` en respuestas HTTP 500. Filtra detalles internos (rutas, mensajes de librerías, fragmentos de estado) al cliente.
- **Evidencia**: `perfil.py:171` `detail=f"Error al guardar API Key: {str(e)}"`; `consolidacion_service.py:253` `detail=f"Error procesando el archivo ZIP: {str(e)}"`.
- **Impacto**: Fingerprinting del stack y posible filtrado de información sensible en el detalle del error.
- **Fix propuesto**: Loggear el detalle server-side y devolver un mensaje genérico al cliente. Centralizar con un exception handler.
- **Esfuerzo estimado**: S

---

### 🟢 Enumeración de usuarios por mensajes de login diferenciados

- **ID**: SEC-013
- **Ubicación**: `backend/app/services/auth_service.py:67-97`
- **Severidad**: 🟢 Baja
- **Dimensión**: Seguridad
- **Descripción**: El login devuelve mensajes distintos: usuario inexistente → "Credenciales inválidas"; contraseña incorrecta → "Credenciales inválidas. N intentos restantes."; cuenta bloqueada → "Cuenta bloqueada. Intenta en N minutos"; deshabilitada → "Cuenta deshabilitada". Las diferencias permiten distinguir si un username existe y su estado. Además, el contador de intentos restantes facilita evadir el lockout.
- **Evidencia**: `auth_service.py:68-70` vs `:94-96` vs `:85-87` vs `:75-78`.
- **Impacto**: Enumeración de usuarios válidos y de su estado de cuenta; información útil para fuerza bruta dirigida (agravado por SEC-008).
- **Fix propuesto**: Mensaje genérico uniforme para credenciales inválidas / usuario inexistente. No revelar intentos restantes ni distinguir "deshabilitada" en el mismo canal.
- **Esfuerzo estimado**: S

---

### 🟢 Credencial admin por defecto `admin/admin123` en seed

- **ID**: SEC-014
- **Ubicación**: `backend/scripts/init_db.py:65`
- **Severidad**: 🟢 Baja
- **Dimensión**: Seguridad
- **Descripción**: El seed crea un admin con contraseña `admin123` (documentado también en CLAUDE.md). Si no se fuerza el cambio en el primer login en producción, queda una credencial trivial. Existe el flag `primer_login` en el modelo, lo que mitiga si el flujo lo obliga.
- **Evidencia**: `init_db.py:65` `"password": "admin123"`.
- **Impacto**: Acceso ADMIN trivial si el despliegue no rota la contraseña inicial.
- **Fix propuesto**: Generar contraseña aleatoria en el seed y mostrarla una vez, o exigir cambio forzado en el primer login (verificar que `primer_login=True` bloquee todo hasta el cambio). Nunca versionar la contraseña por defecto.
- **Esfuerzo estimado**: S

---

## Notas de verificación (lo que SÍ está bien)

- **`.env` no está commiteado**: `git ls-files` solo muestra `.env.example` / `.env.production.example` / `.env.easypanel.example` (plantillas). `.gitignore` cubre `.env*`. ✅
- **API keys IA cifradas con AES/Fernet** antes de persistir (`perfil.py:151`, `security.py:167-192`); no se loggean keys ni secrets (grep de logs sin fugas). El único log de API key marca "inválida" con el `user_id`, no la key (`correccion_service.py:214`). ✅
- **Guards `verificar_acceso_*` reales** (materia/comisión/unidad/examen/rúbrica) sí consultan `CoordinadorMateria`/`ComisionTutor` y se usan correctamente en `materias.py`, `comisiones.py`, `unidades.py`, `examenes.py`, `cierre_cursada.py` y `moodle_grade_service.py`. ✅
- **Sin SQL crudo ni format-string en queries**: todo vía SQLAlchemy ORM (`select(...)`). Los `.format()` encontrados son de plantillas de texto/HTML con `html.escape`. ✅
- **CORS acotado**: orígenes explícitos (localhost:3000/5173), no `*`, con métodos/headers restringidos (`main.py:71-78`). Revisar que en prod `CORS_ORIGINS` no se abra. ✅
- **El rol NO se confía del body**: el rol sale del `Usuario` de DB vía JWT (`dependencies.py`), no de payloads del cliente. ✅
- **Docs de API deshabilitadas si `DEBUG=False`** (`main.py:64-66`). ✅
- **Importación Moodle correctamente scopeada** por `ComisionTutor.tutor_id == user_id` (`moodle_import_service.py:366`). ✅

---

## Recomendación de priorización

1. **SEC-003** (secretos por defecto) — barato de arreglar, habilita el peor escenario (forja de JWT/descifrado). Va primero.
2. **SEC-001 + SEC-002 + SEC-004** (IDOR en correcciones/entregas/documentos) — misma raíz: `require_any_authenticated` no valida pertenencia. Diseñar UN helper de verificación por recurso y aplicarlo en los tres routers.
3. **SEC-005** (ZIP-bomb / tamaño) y **SEC-008** (rate limit) — exposición a DoS, config ya definida sin cablear.
