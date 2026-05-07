## 1. Migraciones de base de datos

- [x] 1.1 Agregar campos `moodle_username`, `moodle_password_encrypted`, `moodle_host` (nullable) al modelo `Usuario` en `app/models/usuario.py`
- [x] 1.2 Agregar campo `moodle_course_id` (nullable, Integer) al modelo `Materia` en `app/models/materia.py`
- [x] 1.3 Agregar campo `moodle_assign_id` (nullable, Integer) al modelo `Rubrica` en `app/models/rubrica.py`
- [x] 1.4 Agregar campos `moodle_group_id` (nullable, Integer) y `moodle_group_code` (nullable, String) al modelo `Comision` en `app/models/comision.py`
- [x] 1.5 Generar migración Alembic: `alembic revision --autogenerate -m "add moodle fields to usuario, materia, rubrica, comision"`
- [x] 1.6 Verificar migración generada y aplicar: `alembic upgrade head`

## 2. Backend — Credenciales Moodle en Usuario

- [x] 2.1 Agregar schemas Pydantic en `app/schemas/usuario.py`: `MoodleCredentialsUpdate` (username, password, host) y campo `moodle_configured: bool` en `UsuarioRead`
- [x] 2.2 Agregar método `update_moodle_credentials(user_id, username, password_encrypted, host)` en `app/repositories/usuario_repository.py`
- [x] 2.3 Agregar método `update_moodle_credentials(user_id, username, password, host)` en `app/services/usuario_service.py` — cifra el password con `encrypt_api_key` de `app/core/security.py`
- [x] 2.4 Agregar endpoint `PATCH /api/usuarios/me/moodle-credentials` en `app/routers/usuarios.py` — requiere auth JWT, devuelve `{ moodle_username, moodle_host, configured: true }`

## 3. Backend — IDs Moodle en Materia, Rúbrica y Comisión

- [x] 3.1 Agregar campo `moodle_course_id` al schema `MateriaUpdate` en `app/schemas/materia.py`
- [x] 3.2 Agregar campo `moodle_assign_id` al schema `RubricaUpdate` en `app/schemas/rubrica.py`
- [x] 3.3 Agregar campos `moodle_group_id` y `moodle_group_code` al schema `ComisionUpdate` en `app/schemas/comision.py`
- [x] 3.4 Verificar que los endpoints PATCH de Materia, Rúbrica y Comisión persisten los nuevos campos (solo admins)

## 4. Backend — MoodleService

- [x] 4.1 Crear `app/services/moodle_service.py` con clase `MoodleService`
- [x] 4.2 Implementar `get_token(user_id, moodle_host, username, password_encrypted)` — descifra password, llama a `POST {host}/login/token.php`, cachea token con TTL 50min en dict de clase
- [x] 4.3 Implementar `get_submissions_count(token, moodle_host, assign_id, group_id)` — llama a `mod_assign_get_submissions` via `GET {host}/webservice/rest/server.php` con `httpx.AsyncClient`, devuelve `{ espera, corregidos, sinEntrega }`
- [x] 4.4 Implementar manejo de errores: `invalidlogin` → raise `MoodleAuthError`, timeout/red → raise `MoodleConnectionError`
- [x] 4.5 Implementar `get_pendientes(user_id)` — orquesta las llamadas en paralelo con `asyncio.gather` (máx 10 concurrentes con semaphore), construye y devuelve `MateriasPendientesResponse`

## 5. Backend — Router de Pendientes

- [x] 5.1 Crear `app/routers/pendientes.py` con endpoint `GET /api/pendientes/moodle`
- [x] 5.2 Validar que el usuario tiene credenciales Moodle configuradas — devolver HTTP 424 si no
- [x] 5.3 Capturar `MoodleAuthError` → HTTP 424, `MoodleConnectionError` → HTTP 502
- [x] 5.4 Registrar el router en `app/main.py` con prefix `/api/pendientes`
- [x] 5.5 Agregar schemas Pydantic en `app/schemas/pendientes.py`: `ComisionPendiente`, `UnidadPendiente`, `MateriaPendiente`, `MateriasPendientesResponse`

## 6. Frontend — Tipos y Servicios

- [x] 6.1 Crear `src/features/pendientes/types/index.ts` con interfaces `ComisionPendiente`, `UnidadPendiente`, `MateriaPendiente`, `MateriasPendientesResponse`
- [x] 6.2 Crear `src/features/pendientes/services/pendientes.service.ts` con función `getPendientesMoodle()` que llama a `GET /api/pendientes/moodle`
- [x] 6.3 Crear `src/features/pendientes/hooks/usePendientesMoodle.ts` — Tanstack Query con `queryKey: ['pendientes-moodle']`, `staleTime: 5 * 60 * 1000`

## 7. Frontend — Componentes

- [x] 7.1 Crear `src/features/pendientes/components/ComisionRow.tsx` — nombre, conteos coloreados (rojo/verde/gris), botón "Ver en Moodle" condicional con ícono `ExternalLink`
- [x] 7.2 Crear `src/features/pendientes/components/UnidadBlock.tsx` — acordeón con `useState(true)`, header con badge de unidad, pills resumen, lista de `ComisionRow`, prop `showUrgentOnly`
- [x] 7.3 Crear `src/features/pendientes/components/MateriaBlock.tsx` — acordeón con `useState(true)`, header con nombre de materia y pills resumen, lista de `UnidadBlock`
- [x] 7.4 Crear `src/features/pendientes/components/index.ts` exportando los 3 componentes

## 8. Frontend — Página Pendientes

- [x] 8.1 Crear `src/features/pendientes/pages/PendientesPage.tsx` con header, 3 stat cards (`<StatCard>`), chips de filtro, lista de `MateriaBlock`
- [x] 8.2 Implementar chips de filtro con estado local `showUrgentOnly: boolean`
- [x] 8.3 Implementar botón "Actualizar" que llama a `queryClient.invalidateQueries(['pendientes-moodle'])`
- [x] 8.4 Implementar estado de loading (skeleton) y estado de error/424 con CTA al perfil
- [x] 8.5 Crear `src/features/pendientes/pages/index.ts` y `src/features/pendientes/index.ts`

## 9. Frontend — Integración en la App

- [x] 9.1 Agregar ruta lazy-loaded `/pendientes` → `PendientesPage` en el router de la app
- [x] 9.2 Agregar ítem en `Sidebar.tsx`: `{ to: '/pendientes', icon: Clock, label: 'Pendientes', roles: ['TUTOR', 'ADMIN'] }` después de "Entregas"
- [x] 9.3 Agregar banner de alerta en `DashboardTutor.tsx` — visible solo si `totalEspera > 0`, botón "Ver pendientes" navega a `/pendientes`

## 10. Frontend — Configuración Moodle en Perfil

- [x] 10.1 Agregar sección "Configuración Moodle" en la página de perfil del tutor con campos `moodle_host`, `moodle_username`, `moodle_password`
- [x] 10.2 Crear servicio `updateMoodleCredentials(data)` en `src/features/profile/services/`
- [x] 10.3 Conectar el form al endpoint `PATCH /api/usuarios/me/moodle-credentials` con React Hook Form + Zod

## 11. Verificación

- [x] 11.1 Escribir tests unitarios para `MoodleService.get_token` (mock httpx) en `backend/tests/`
- [x] 11.2 Escribir test de integración para `GET /api/pendientes/moodle` con credenciales faltantes (espera 424)
- [ ] 11.3 Verificar en dev que el deep link al grader de Moodle funciona con valores reales (assign_id=11237, group_id=4165, group_code=m26)
- [ ] 11.4 Verificar que el banner en el Dashboard aparece y desaparece correctamente según `totalEspera`
