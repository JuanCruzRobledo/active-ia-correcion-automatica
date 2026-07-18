## ADDED Requirements

### Requirement: Clasificación del 401 por origen de endpoint

El interceptor de response del cliente HTTP compartido (`apiClient`) SHALL distinguir un error 401 originado en un endpoint de autenticación de un 401 originado en cualquier otro endpoint, inspeccionando la URL de la request fallida (`error.config?.url`). Se consideran endpoints de autenticación al menos `/auth/login` y `/auth/change-password`.

#### Scenario: 401 de login no expira la sesión
- **WHEN** una request a `POST /auth/login` falla con status 401 (credenciales inválidas)
- **THEN** el interceptor NO muestra el toast "Sesión expirada. Por favor, inicia sesión nuevamente."
- **AND** NO elimina `auth_token` ni `auth_user` de `localStorage`
- **AND** NO redirige el navegador a `/login`
- **AND** rechaza la promesa dejando pasar el error al caller

#### Scenario: 401 de cambio de contraseña no expira la sesión
- **WHEN** una request a `POST /auth/change-password` falla con status 401
- **THEN** el interceptor NO limpia `localStorage` ni redirige
- **AND** deja pasar el error al caller para que lo presente

#### Scenario: 401 de token expirado en otro endpoint sí expira la sesión
- **WHEN** una request a cualquier endpoint que NO es de autenticación (p. ej. `/entregas`) falla con status 401
- **THEN** el interceptor muestra el toast "Sesión expirada. Por favor, inicia sesión nuevamente."
- **AND** elimina `auth_token` y `auth_user` de `localStorage`
- **AND** redirige el navegador a `/login`

### Requirement: Presentación del mensaje real de error de login

Ante un fallo de login, el caller (LoginPage vía el hook `useLogin`) SHALL presentar al usuario el mensaje real provisto por el backend (campo `detail` / `message`), resuelto con el helper compartido `getErrorMessage`, en lugar de un mensaje genérico de sesión expirada.

#### Scenario: Se muestra el detalle del backend con intentos restantes
- **WHEN** el login falla con 401 y el backend responde `detail: "Credenciales inválidas. 2 intentos restantes."`
- **THEN** el usuario ve exactamente ese mensaje (o su equivalente resuelto por `getErrorMessage`)
- **AND** el formulario de login permanece visible y sin recargarse

#### Scenario: Cuenta bloqueada muestra el mensaje del backend
- **WHEN** el login falla con 403 y el backend responde `detail: "Cuenta bloqueada. Intenta en N minutos."`
- **THEN** el usuario ve ese mensaje sin que se limpie la sesión ni se redirija
