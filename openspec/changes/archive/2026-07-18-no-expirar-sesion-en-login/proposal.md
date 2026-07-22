## Why

Todo 401 que atraviesa el interceptor global de axios (`frontend/src/shared/services/api-client.ts`) se trata como "sesión expirada": muestra el toast "Sesión expirada. Por favor, inicia sesión nuevamente.", borra `localStorage` y hace un reload completo a `/login`. Pero el login (`POST /auth/login`) usa el MISMO `apiClient` compartido, así que cuando el backend responde 401 por credenciales incorrectas, el interceptor pisa el mensaje real —que el backend ya arma con los intentos restantes antes del bloqueo (`Credenciales inválidas. N intentos restantes.`)— con "Sesión expirada", y encima recarga la página a `/login` (donde el usuario ya está) borrando el formulario. El usuario nunca ve por qué falló ni cuántos intentos le quedan. Hallazgo de auditoría ERR-004 (severidad alta).

## What Changes

- El interceptor de response distingue el 401 de un endpoint de autenticación (`/auth/login`, `/auth/change-password`) del 401 de un token expirado en cualquier otro endpoint, inspeccionando `error.config?.url` (dato ya disponible; hoy sólo se usa en el log de dev, línea 158).
- 401 en un endpoint de auth: el interceptor NO muestra el toast de "Sesión expirada", NO limpia `localStorage` y NO redirige. Deja pasar el error para que el caller (LoginPage vía `useLogin`) muestre el mensaje real del backend con el helper compartido `getErrorMessage`.
- 401 en cualquier otro endpoint (token realmente expirado): se mantiene el comportamiento actual (toast + limpiar sesión + redirect a `/login`).
- `useLogin` (`frontend/src/features/auth/hooks/useLogin.ts`) surfacea el mensaje real del backend al usuario (hoy sólo hace `console.error`).
- Tests vitest que cubren ambas ramas del 401 (auth vs. no-auth).

Sin cambios en el backend: ya devuelve el `detail` correcto. No hay cambios de contrato de API. No breaking changes.

## Capabilities

### New Capabilities
- `auth-error-feedback`: cómo el frontend clasifica y presenta los errores 401 — diferenciando el fallo de login/cambio de contraseña (mensaje real del backend, sin logout ni redirect) del token expirado en endpoints autenticados (toast + limpiar sesión + redirect).

### Modified Capabilities
<!-- Ninguna: no existe hoy una spec que cubra el manejo de errores del cliente HTTP del frontend. -->

## Impact

- **Frontend (presentación, no lógica de autenticación):**
  - `frontend/src/shared/services/api-client.ts` — bloque `case 401` del interceptor de response.
  - `frontend/src/features/auth/hooks/useLogin.ts` — mostrar el mensaje real en `onError`.
  - Posible extracción de un helper puro (p. ej. `isAuthEndpoint(url)`) para que la decisión sea testeable en el entorno node por defecto de vitest (ver design.md).
- **Backend:** ninguno.
- **Gobernanza:** MEDIA (mensajería de errores del flujo de login; toca presentación, no la lógica de autenticación). Implementar con checkpoints. Esfuerzo estimado: **S**.
