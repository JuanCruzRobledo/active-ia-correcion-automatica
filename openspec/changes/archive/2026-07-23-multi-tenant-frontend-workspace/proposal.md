## Why

Las Fases 0–4 del plan multi-tenant movieron el contrato del backend (login en dos pasos, `rol` por membresía, `moodle_host` como propiedad de la Universidad, scoping por universidad activa) y **el frontend nunca se tocó**. Hoy no es que "falta el selector": la app está rota contra su propio backend. Un usuario con membresía en dos universidades **no puede iniciar sesión** (crash en `useLogin.onSuccess`), y un superadmin entra a una navegación con un solo item porque su `rol` es `null`.

Además falta el otro extremo: no existe forma de **listar** universidades. `UniversidadDisponible` sólo se construye dentro de `authenticate()` y sólo cuando hay 2+ membresías, así que un usuario con una sola universidad no sabe ni cómo se llama la suya, y un superadmin no puede enumerar ninguna. Sin ese listado no hay selector posible, y sin ABM no hay forma de dar de alta la segunda universidad — que es el punto entero del multi-tenant.

Y un requisito que no es cosmético: al cambiar de universidad hay que invalidar la caché de React Query. No hacerlo deja datos del tenant anterior en pantalla.

## What Changes

Ordenado a propósito: primero las roturas (sin eso no se puede ni probar lo nuevo), después el backend que habilita el selector, después las features.

**Parte 1 — Roturas de integración con Fases 1–4 (frontend)**

- **BREAKING** `auth-service.login()` deja de asumir que la respuesta trae `access_token`. Discrimina entre `TokenResponse` y `SeleccionUniversidadRequerida` (unión discriminada por `requiere_seleccion`) y sólo persiste sesión en el primer caso.
- `LoginPage` gana el segundo paso: cuando el backend pide selección, muestra las universidades disponibles y llama a `POST /auth/select-universidad` con el `token_transicion`.
- El gating por rol deja de excluir al superadmin: `es_superadmin` habilita todo el menú aunque `rol` sea `null`.
- El formulario de credenciales Moodle del perfil deja de enviar y pedir `moodle_host`: el campus pasa a mostrarse read-only desde la universidad activa.
- El interceptor de axios distingue **409 sin universidad activa** y **424 sin credenciales Moodle** del resto, con mensajes accionables.

**Parte 2 — Endpoints de universidades (backend)**

- `GET /universidades/mias`: universidades donde el usuario autenticado tiene membresía activa, con su rol en cada una. Para el superadmin devuelve todas las activas.
- ABM restringido a superadmin: `GET /universidades` (listado con paginación), `POST /universidades`, `PUT /universidades/{id}`, `DELETE /universidades/{id}` (baja lógica, nunca física — regla dura del proyecto).
- Router + service + schemas nuevos; el `UniversidadRepository` ya existe desde la Fase 1 y se extiende.

**Parte 3 — Contexto de universidad activa (frontend)**

- Nuevo `TenantProvider` + `useTenant()`: fuente única y reactiva de `universidad_activa_id`, `rol` y `es_superadmin`.
- Selector de universidad en el layout. Al cambiar: `POST /auth/switch-universidad` → nuevo token → **invalidación total de la caché de React Query** → navegación a `/dashboard`.
- El superadmin opera por defecto en modo global y el selector incluye la opción **"Todas las universidades"**, que emite un token con `universidad_activa_id = null` (lo que el backend ya interpreta como "sin filtro" desde la Fase 4).

**Parte 4 — ABM de Universidades (frontend)**

- Nueva feature `universidades`: listado, alta, edición (`nombre`, `moodle_host`, `activa`) y baja lógica. Visible sólo para superadmin.

## Capabilities

### New Capabilities
- `universidades-abm`: endpoints de listado y administración de universidades, con el bypass de superadmin y baja lógica.
- `frontend-universidad-activa`: contexto de universidad activa en el cliente, selector, modo global del superadmin, cambio de universidad e invalidación de caché entre tenants.
- `frontend-login-dos-pasos`: flujo de login cuando el usuario tiene 2+ membresías, incluyendo el token de transición y la selección de universidad.

### Modified Capabilities
<!-- Ninguna. Las specs existentes describen contrato de backend ya vigente que este
     change consume sin alterar; los endpoints nuevos viven en una capability nueva. -->

## Impact

**Backend**

- Nuevos: `app/routers/universidades.py`, `app/services/universidad_service.py`, `app/schemas/universidad.py`
- Modificados: `app/repositories/universidad_repository.py` (listado y CRUD), `app/main.py` (montaje del router)
- Sin migraciones: la tabla `universidades` existe desde la Fase 0.

**Frontend**

- `src/features/auth/`: `auth-service.ts`, `useLogin.ts`, `useAuth.ts`, `LoginPage.tsx`
- `src/shared/services/api-client.ts`: casos 409 y 424 en `handleResponseError`
- `src/shared/types/index.ts`: `UserInfo` suma `universidad_activa_id` y `es_superadmin`; `rol` pasa a `Rol | null`
- `src/shared/components/layout/`: `navConfig.ts`, `Sidebar.tsx`, `BottomNav.tsx`, `AppLayout.tsx`
- `src/features/perfil/`: `PerfilPage.tsx` y `types/` — `moodle_host` read-only
- `src/app/providers.tsx`: montaje del `TenantProvider`
- Nuevas: `src/features/universidades/`, `src/shared/context/TenantProvider.tsx`
- 31 lecturas de `.rol` en 16 archivos pasan a resolverse por `useTenant()`

**Riesgos**

- `rol: Rol | null` atraviesa toda la app: `npm run typecheck` es la red de seguridad y debe quedar limpio.
- No invalidar React Query al switchear filtra datos entre tenants. Es el requisito más crítico del change.
- El ABM toca creación de tenants: gobernanza HIGH, con el bypass de superadmin como único guard.
- El bug de `passlib`/`bcrypt` en el entorno local impide probar un login real end-to-end.
