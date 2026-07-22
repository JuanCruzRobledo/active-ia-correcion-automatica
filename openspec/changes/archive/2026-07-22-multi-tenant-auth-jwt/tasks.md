> **Gobernanza: CRÍTICA (auth/JWT).** Este change entrega SOLO artefactos. NO escribir código de producción hasta la aprobación humana línea por línea. Las Open Questions del superadmin (design.md) deben resolverse en el checkpoint ANTES de apply. Orientación **TDD estricto**: cada tarea de código empieza por un test que falla (RED) → mínimo para pasar (GREEN) → segundo caso/edge (TRIANGULATE) → refactor.

## 1. Preparación / red de seguridad

- [x] 1.1 Correr la suite backend actual (`pytest`) y capturar baseline verde de los tests de auth existentes (`tests` de `auth_service`, `security`, `dependencies`). Reportar cualquier fallo pre-existente sin arreglarlo.
- [x] 1.2 Confirmar con el humano las dos Open Questions del superadmin (design.md → Open Questions 1 y 2) y anotar la decisión final en el design antes de codear.

## 2. Repositorio de membresías (ARCH-001)

- [x] 2.1 RED: test de `UsuarioRepository.get_membresias_activas(usuario_id)` que espera solo membresías con `usuario_universidad.activo=true` y `universidades.activa=true`, con la `Universidad` cargada (sin disparar el `lazy="raise"` de `Usuario.universidades`).
- [x] 2.2 GREEN: implementar `get_membresias_activas` en `app/repositories/usuario_repository.py` con `select(...).join(Universidad).where(...).options(selectinload(...))`.
- [x] 2.3 RED+GREEN: `get_membresia(usuario_id, universidad_id)` que devuelve la membresía activa puntual o `None` (usado por select/switch/dependency). Triangular: par inexistente, par con `activo=false`, universidad `activa=false`.
- [x] 2.4 REFACTOR: revisar nombres/duplicación; verificar que ningún método navega la relationship `lazy="raise"` implícitamente.

## 3. `create_access_token` / `decode_token` (`app/core/security.py`)

- [x] 3.1 RED: test que espera la nueva firma keyword-only `create_access_token(user_id, username, *, rol, universidad_activa_id, es_superadmin, expires_delta=None)` y que el payload decodificado contiene `universidad_activa_id`, `rol` y `es_superadmin`.
- [x] 3.2 RED: test que verifica que llamar con `rol`/`universidad_activa_id`/`es_superadmin` posicionales lanza `TypeError`.
- [x] 3.3 GREEN: implementar la nueva firma y payload. Actualizar el docstring de `decode_token` documentando los nuevos claims y su opcionalidad en tokens viejos.
- [x] 3.4 TRIANGULATE: caso superadmin (`universidad_activa_id=None`, `rol=None`, `es_superadmin=True`) y caso normal (todos poblados). Test de retrocompat: un dict tipo "token viejo" (sin los claims) se decodifica sin error.
- [x] 3.5 REFACTOR: limpiar; confirmar que `decode_token` no cambió de firma.

## 4. Schemas del login en dos pasos (`app/schemas/auth.py`)

- [x] 4.1 RED: tests de validación de `UniversidadDisponible` (`id`, `nombre`, `rol`), `SeleccionarUniversidadRequest` (`universidad_id`) y la respuesta intermedia `{requiere_seleccion: true, universidades: [...]}`.
- [x] 4.2 GREEN: definir los schemas nuevos; extender `UserInfo` (`rol: RolEnum | None` = rol en universidad activa, `universidad_activa_id: int | None`, `es_superadmin: bool`); definir el modelo unión de respuesta de login.
- [x] 4.3 TRIANGULATE: `UserInfo` con rol de membresía; `UserInfo` de superadmin (`rol=None`); respuesta intermedia con 2+ universidades. Verificar el `model_rebuild()` de forward refs.

## 5. Dependency `get_universidad_activa` (`app/core/dependencies.py`)

- [x] 5.1 RED: test — token con `universidad_activa_id` y membresía activa → contexto `{universidad_id, rol, es_superadmin}` con el rol releído de la base.
- [x] 5.2 RED: test — membresía revocada (`activo=false`) o universidad `activa=false` → 403.
- [x] 5.3 RED: test — el `rol` del contexto viene de la base aunque el claim `rol` del token diga otra cosa.
- [x] 5.4 GREEN: implementar `get_universidad_activa` reusando `get_current_user`; validar membresía vía repo (tarea 2). Definir el tipo de contexto (dataclass/Pydantic interno).
- [x] 5.5 RED+GREEN: fallback de token viejo sin `universidad_activa_id` — 1 membresía → auto-resuelve; 0 o 2+ → error de reautenticación. Triangular las tres ramas.
- [x] 5.6 RED+GREEN: bypass superadmin — cualquier universidad `activa` sin membresía → contexto con `es_superadmin=true`; universidad inexistente/inactiva → error.
- [x] 5.7 REFACTOR: confirmar que `get_current_user`/`get_current_user_optional` quedaron intactos y que el dependency NO está montado en endpoints existentes.

## 6. `AuthService` — flujo de login en dos pasos (`app/services/auth_service.py`)

- [x] 6.1 RED: test — usuario no-superadmin con 1 membresía activa → 200 con token que lleva su `universidad_activa_id` + rol de membresía (no `usuarios.rol`).
- [x] 6.2 RED: test — usuario no-superadmin con 0 membresías → 403 "sin universidad", sin token.
- [x] 6.3 RED: test — usuario no-superadmin con 2+ membresías → 200 con `requiere_seleccion=true` y lista de `UniversidadDisponible` (id/nombre/rol), sin token final.
- [x] 6.4 RED: test — superadmin → 200 token modo superadmin (según decisión OQ1).
- [x] 6.5 GREEN: implementar la ramificación en `AuthService.authenticate` reusando `get_membresias_activas`; mantener intacta la lógica de lockout/deshabilitado; emitir token con la nueva `create_access_token`. Preservar la respuesta 401/403 de credenciales/cuenta.
- [x] 6.6 GREEN: `AuthService.seleccionar_universidad(usuario, universidad_id)` — valida membresía activa (o bypass superadmin) y emite token final. RED antes: membresía válida → token; sin membresía → 403; superadmin a cualquier universidad activa → token con rol sintético ADMIN.
- [x] 6.7 GREEN: `AuthService.switch_universidad(current_user, universidad_id)` — misma validación, re-emite token. RED antes: válido → nuevo token; sin membresía → 403; superadmin → ok.
- [x] 6.8 TRIANGULATE: cubrir cada rama con happy path + edge (membresía inactiva, universidad inactiva, usuario sin membresías).
- [x] 6.9 REFACTOR: extraer la construcción del token/UserInfo a un helper privado si hay duplicación entre login/select/switch. Mantener < 500 LOC.

## 7. Router (`app/routers/auth.py`)

- [x] 7.1 RED: tests de endpoint (`httpx`/`TestClient`) — `POST /auth/login` con 1 universidad (200 + token), 0 universidades (403), 2+ (200 + requiere_seleccion), superadmin.
- [x] 7.2 RED: tests — `POST /auth/select-universidad` (200 con membresía; 403 sin membresía; superadmin cualquier universidad activa) y `POST /auth/switch-universidad` (autenticado: 200 con membresía; 403 sin; superadmin ok).
- [x] 7.3 GREEN: modificar el handler de `login` y agregar los handlers `select-universidad` y `switch-universidad`, delegando al `AuthService` (sin lógica en el router). `switch` usa `Depends(get_current_user)`; `select` usa el portador de identidad decidido en apply (token de transición corto recomendado). Documentar `responses` (200/401/403).
- [x] 7.4 REFACTOR: revisar OpenAPI (`response_model` unión o `response_model=None` tipado) y summaries/descripciones en español.

## 8. Cierre

- [x] 8.1 Correr `pytest` completo — todo verde, incluida la tabla de evidencia TDD por tarea.
- [x] 8.2 Verificar manualmente el flujo con la DB de dev (`docker-compose.local.yml`): login de un usuario TUPaD (1 universidad) sigue funcionando exactamente igual (retrocompat con una sola universidad). [Nota: se verificó end-to-end con router+AuthService+repos+DB reales (SQLite) en vez de contra Docker Postgres — ver reporte final del apply. El bcrypt real de esta máquina está roto por una causa ajena a este change (passlib/bcrypt), documentado en el test.]
- [x] 8.3 Confirmar que NADA de `permissions.py`, services de Moodle, scoping de queries ni frontend fue tocado (alcance de Fase 1).
- [x] 8.4 `openspec validate multi-tenant-auth-jwt --strict` en verde antes de archivar.
