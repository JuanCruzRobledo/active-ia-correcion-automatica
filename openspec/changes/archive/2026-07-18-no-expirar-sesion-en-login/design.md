## Context

El frontend usa un único `apiClient` de axios (`frontend/src/shared/services/api-client.ts`) con un interceptor de response global que centraliza el manejo de errores. Hoy el bloque `case 401` (líneas 96-105) trata TODO 401 como "sesión expirada": toast + `localStorage.removeItem` + `window.location.href = '/login'` tras 1.5s.

El login (`frontend/src/features/auth/services/auth-service.ts:34-35`) pega a `POST /auth/login` con ese MISMO `apiClient`, sin interceptor propio. El backend (`backend/app/services/auth_service.py:91-97`) devuelve 401 con un `detail` útil (`"Credenciales inválidas. N intentos restantes."`) ante password incorrecta, y 403 (`"Cuenta bloqueada..."`, `"Cuenta deshabilitada"`) para cuenta bloqueada/deshabilitada. El 401 de login es indistinguible, para el interceptor, del 401 de un token expirado, así que el mensaje real se pierde: lo pisa "Sesión expirada" y el reload a `/login` borra el formulario. `useLogin` (`frontend/src/features/auth/hooks/useLogin.ts:67-72`) hoy sólo hace `console.error` y delega todo al interceptor.

La info para diferenciar YA está disponible: `error.config?.url` (el interceptor la usa en el log de dev, línea 158).

**Restricciones del entorno de tests:** vitest corre en el entorno `node` por defecto (no hay `jsdom`, `happy-dom` ni `@testing-library` instalados; no hay bloque `test` en `vite.config.ts`). Los tests existentes (`erroresResumen.test.ts`, `novedades.test.ts`, `modoConsolidacionInicial.test.ts`) son todos de funciones puras. `localStorage` y `window.location` NO existen en node sin stubbing.

**Gobernanza:** MEDIA (mensajería de errores del flujo de login — presentación, no la lógica de autenticación). Implementar con checkpoints. Esfuerzo: **S**.

## Goals / Non-Goals

**Goals:**
- Que un login fallido muestre el mensaje real del backend (con intentos restantes) sin limpiar sesión ni redirigir.
- Mantener intacto el comportamiento de expiración de token para el resto de los endpoints (toast + logout + redirect).
- Que la decisión "¿este 401 es de auth?" sea unitariamente testeable en el entorno node por defecto, alineada con la convención de funciones puras del repo.

**Non-Goals:**
- No se toca la lógica de autenticación del backend (ya devuelve el `detail` correcto).
- No se cambia el contrato de la API ni los códigos de estado.
- No se introduce `jsdom` ni se reconfigura el runner de tests como parte de este change (ver Decisión 2 y Open Questions).
- No se rediseña la UI del formulario de login.

## Decisions

### Decisión 1: Extraer un predicado puro `isAuthEndpoint(url)` para clasificar el 401

El bloque `case 401` llamará a un helper puro `isAuthEndpoint(url: string | undefined): boolean` que devuelve `true` si la URL incluye una ruta de autenticación (`/auth/login`, `/auth/change-password`). El interceptor ramifica:
- `isAuthEndpoint(error.config?.url)` → NO toast, NO limpiar `localStorage`, NO redirect; sólo `return Promise.reject(error)` para que el caller lo maneje.
- caso contrario → comportamiento actual (toast "Sesión expirada" + limpiar sesión + redirect).

**Por qué un helper puro y no lógica inline:** el repo prueba la lógica con tests de funciones puras en entorno node (no hay DOM). Un predicado puro es trivialmente testeable sin stubbear `localStorage`/`window`, y encierra la lista de rutas de auth en un único lugar. Alternativa considerada: interceptor propio en `auth-service` — descartada, duplica configuración y el resto de los 401 igual deben pasar por el interceptor global; un solo punto de decisión es más simple.

### Decisión 2: Cobertura de tests en dos capas

1. **Test puro obligatorio** de `isAuthEndpoint`: casos `/auth/login` y `/auth/change-password` → `true`; `/entregas`, `/auth/me` (si aplica), `undefined` → `false`. Corre en node sin stubs, como los tests existentes.
2. **Test de comportamiento del interceptor** que mockea un `AxiosError` (con `config.url`, `response.status = 401`, `response.data.detail`) y verifica las dos ramas:
   - `config.url` con `/auth/login` → `localStorage.removeItem` NO llamado, sin redirect, promesa rechazada con el error original (mensaje real preservado).
   - `config.url` con otro endpoint → toast + `localStorage` limpiado + redirect disparados.

   Para invocar el handler del interceptor en node se stubbean los globals con `vi.stubGlobal` (`localStorage` con un mock de `removeItem`, `window.location`/`href`, y `react-hot-toast` mockeado con `vi.mock`). El handler se obtiene a través de `apiClient.interceptors.response` o extrayéndolo a una función `handleResponseError(error)` exportada. **Preferencia:** extraer `handleResponseError` para que sea invocable directamente (mismo espíritu que el helper puro), evitando depender de internals de axios.

**Alternativa considerada:** instalar `jsdom` + `@testing-library` para tests de integración de LoginPage. Descartada para este change (esfuerzo S, gobernanza media): agranda el alcance y toca la config del runner. Se deja como Open Question para un change futuro.

### Decisión 3: `useLogin` surfacea el mensaje real

En `onError`, además del `console.error` actual, `useLogin` muestra el mensaje resuelto por `getErrorMessage(error)` (toast de error o estado de error que la LoginPage ya consume vía `loginMutation.isError`/`error`). Como el interceptor ya no dispara toast para los 401 de auth, no hay doble notificación. Se reutiliza `getErrorMessage` (`frontend/src/shared/types/index.ts:278`), que ya sabe extraer `detail` string o array.

## Risks / Trade-offs

- **Riesgo: doble toast (interceptor + `useLogin`) si la rama de auth no se recorta bien.** → El interceptor debe hacer early-return SIN toast para `isAuthEndpoint`; test de comportamiento cubre exactamente que no se dispare el toast global en la rama de auth.
- **Riesgo: matcheo de URL frágil (query params, baseURL).** → `error.config?.url` es la URL relativa pasada a axios (`/auth/login`), estable; el helper usa `includes('/auth/login')`. Test cubre variantes.
- **Riesgo: futuros endpoints de auth (p. ej. refresh, reset-password) que sí deban expirar sesión o no.** → La lista de rutas de auth queda centralizada en `isAuthEndpoint`; documentar el criterio ahí.
- **Trade-off: no cubrir LoginPage end-to-end** por no instalar jsdom. Mitigado con el test de comportamiento del handler + el test puro; la LoginPage sólo consume el estado de `useLogin`.

## Migration Plan

Cambio puramente aditivo de comportamiento en el frontend, sin migración de datos ni de API. Deploy junto al frontend. Rollback = revertir el commit (restaura el `case 401` monolítico). Verificación manual (checkpoint de gobernanza media): (1) login con password incorrecta → se ve el mensaje con intentos restantes, el form no se recarga; (2) token expirado en un endpoint autenticado → toast "Sesión expirada" + redirect a `/login`.

## Open Questions

- ¿Se quiere, en un change futuro, incorporar `jsdom` + `@testing-library/react` para tests de integración de LoginPage y otros flujos con DOM? (Fuera de alcance aquí.)
- ¿Hay otros endpoints de auth (refresh token, forgot/reset password) que deban entrar en `isAuthEndpoint`? Confirmar el set exacto al implementar.
