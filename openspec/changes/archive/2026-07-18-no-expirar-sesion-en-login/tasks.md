## 1. Helper puro de clasificación (RED → GREEN)

- [x] 1.1 Escribir test vitest puro `isAuthEndpoint.test.ts` (entorno node, sin stubs) que falle: `/auth/login` → `true`, `/auth/change-password` → `true`, `/entregas` → `false`, `undefined` → `false`. (RED)
- [x] 1.2 Crear el helper puro `isAuthEndpoint(url: string | undefined): boolean` (nueva util en `frontend/src/shared/services/` o `frontend/src/shared/utils/`) con la lista centralizada de rutas de auth (`/auth/login`, `/auth/change-password`). (GREEN)
- [x] 1.3 Triangular: agregar al menos un caso extra (p. ej. URL con query params, otra ruta `/auth/*` que NO deba clasificarse como login si aplica) y generalizar. Correr `npm run test` → verde.

## 2. Ramificación del interceptor 401 (RED → GREEN → REFACTOR)

- [x] 2.1 Escribir test de comportamiento del handler de error del interceptor que mockee un `AxiosError` con `response.status = 401`, `response.data.detail = "Credenciales inválidas. 2 intentos restantes."` y `config.url` conteniendo `/auth/login`; mockear `react-hot-toast` (`vi.mock`) y stubbear `localStorage` (`removeItem` espiado) y `window.location` (`vi.stubGlobal`). Afirmar: `localStorage.removeItem` NO llamado, sin redirect, promesa rechazada con el error original (mensaje preservado). Debe fallar contra el código actual. (RED)
- [x] 2.2 Agregar el caso de 401 en OTRO endpoint (`config.url = '/entregas'`): afirmar que SÍ se dispara toast "Sesión expirada", SÍ se limpia `localStorage` (`auth_token` + `auth_user`) y SÍ se redirige a `/login`. (TRIANGULATE)
- [x] 2.3 Refactor: extraer el manejo del interceptor a una función `handleResponseError(error)` exportada desde `api-client.ts` (invocable directamente por los tests sin depender de internals de axios) e implementar la rama `if (isAuthEndpoint(error.config?.url)) return Promise.reject(error)` dentro del `case 401`, dejando intacto el comportamiento actual para el resto. Correr `npm run test` → todo verde. (GREEN + REFACTOR)
- [x] 2.4 Confirmar que el interceptor sigue registrado con `handleResponseError` y que el resto de los códigos (403/404/409/422/5xx/network) mantienen su comportamiento (no regresión). Correr `npm run test`.

## 3. Surface del mensaje real en useLogin

- [x] 3.1 En `frontend/src/features/auth/hooks/useLogin.ts` `onError`, mostrar el mensaje resuelto por `getErrorMessage(error)` al usuario (toast de error o estado consumido por LoginPage vía `loginMutation.isError`/`error`), sin generar doble notificación con el interceptor.
- [ ] 3.2 Verificación manual (checkpoint gobernanza MEDIA): (a) login con password incorrecta → se ve el mensaje real con intentos restantes y el formulario permanece sin recargarse; (b) forzar 401 de token expirado en un endpoint autenticado → toast "Sesión expirada" + limpieza de sesión + redirect a `/login`.

## 4. Cierre

- [x] 4.1 `npm run test` y `npm run typecheck` en `frontend/` en verde.
- [x] 4.2 `npm run lint` en `frontend/` sin nuevos errores.
