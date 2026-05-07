## ADDED Requirements

### Requirement: Almacenamiento cifrado de credenciales Moodle por tutor

El modelo `Usuario` SHALL incluir tres campos opcionales: `moodle_username` (texto plano), `moodle_password_encrypted` (cifrado AES-256 con la misma `ENCRYPTION_KEY` que las Gemini API keys) y `moodle_host` (texto plano, URL base del sitio Moodle). Los campos son nullable — un tutor sin credenciales configuradas es un estado válido.

#### Scenario: Tutor guarda credenciales Moodle por primera vez
- **WHEN** el tutor envía `PATCH /api/usuarios/me/moodle-credentials` con `{ moodle_username, moodle_password, moodle_host }`
- **THEN** el sistema cifra `moodle_password` con AES-256 y persiste los tres campos en `Usuario`
- **THEN** el response devuelve `{ moodle_username, moodle_host, configured: true }` — nunca el password

#### Scenario: Tutor actualiza credenciales existentes
- **WHEN** el tutor envía `PATCH /api/usuarios/me/moodle-credentials` con nuevos valores
- **THEN** el sistema sobreescribe los campos existentes con los nuevos valores cifrados

#### Scenario: Tutor consulta si tiene credenciales configuradas
- **WHEN** el tutor consulta `GET /api/usuarios/me`
- **THEN** el response incluye `{ moodle_configured: bool, moodle_username: str | null, moodle_host: str | null }` — sin exponer el password

#### Scenario: Admin configura IDs de Moodle en Materia
- **WHEN** un ADMIN envía `PATCH /api/materias/{id}` con `{ moodle_course_id: int }`
- **THEN** el sistema persiste el `moodle_course_id` en la `Materia`

#### Scenario: Admin configura moodle_assign_id en Rúbrica
- **WHEN** un ADMIN envía `PATCH /api/rubricas/{id}` con `{ moodle_assign_id: int }`
- **THEN** el sistema persiste el `moodle_assign_id` en la `Rubrica`

#### Scenario: Admin configura IDs de Moodle en Comisión
- **WHEN** un ADMIN envía `PATCH /api/comisiones/{id}` con `{ moodle_group_id: int, moodle_group_code: str }`
- **THEN** el sistema persiste ambos campos en la `Comision`

### Requirement: Obtención y cache de token Moodle

El sistema SHALL obtener un token de Moodle vía `POST {moodle_host}/login/token.php` con `username`, `password` y `service=moodle_mobile_app`. El token SHALL ser cacheado en memoria por proceso con TTL de 50 minutos. Si el token expira o es inválido, el sistema SHALL re-autenticar transparentemente.

#### Scenario: Autenticación exitosa con Moodle
- **WHEN** el `MoodleService` necesita un token para un tutor
- **THEN** descifra `moodle_password_encrypted`, llama a `/login/token.php` y cachea el token con TTL 50 min

#### Scenario: Credenciales Moodle incorrectas
- **WHEN** Moodle responde con `{ "error": "invalidlogin" }`
- **THEN** el sistema devuelve HTTP 424 con mensaje `"Credenciales Moodle inválidas. Actualizalas en tu perfil."`

#### Scenario: Tutor sin credenciales configuradas intenta acceder a pendientes
- **WHEN** el tutor llama a `GET /api/pendientes/moodle` y `moodle_username` es null
- **THEN** el sistema devuelve HTTP 424 con mensaje `"Configurá tus credenciales Moodle en tu perfil."`
