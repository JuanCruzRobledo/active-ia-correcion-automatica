## Why

Los tutores tienen que ingresar manualmente a cada asignación en Moodle para detectar entregas pendientes de calificación, lo cual es tedioso y propenso a que se les pasen trabajos sin revisar. Este sistema centraliza esa visibilidad en el dashboard de Active-IA, mostrando en tiempo real todas las entregas pendientes de cada materia y comisión con acceso directo al grader de Moodle.

## What Changes

- Nuevo campo en el perfil del tutor para guardar credenciales Moodle (usuario + password, cifradas AES-256 igual que las API keys de Gemini).
- Nuevo endpoint `GET /api/pendientes/moodle` que autentica contra Moodle Mobile App webservice y agrega el estado de entregas por unidad y comisión.
- Nueva página `/pendientes` en el frontend: acordeón por Unidad → Comisión con stat cards, filtros y links directos al grader de Moodle con parámetros de estado y grupo pre-configurados.
- División de los pendientes por materia (agrupación de nivel superior, no contemplada en el diseño original).
- Banner de alerta en el Dashboard del tutor cuando hay entregas pendientes.
- Nuevo ítem "Pendientes" en el Sidebar (roles: TUTOR, ADMIN).

## Capabilities

### New Capabilities

- `moodle-credentials`: Almacenamiento cifrado de credenciales Moodle por tutor (usuario, password, moodle_host) en el perfil de usuario; obtención de token vía `/login/token.php`.
- `moodle-pendientes`: Endpoint que consulta el Moodle Mobile App webservice para cada asignación (assign) y grupo (comisión), devuelve el conteo de submissions por estado (requiregrading, graded, sin entrega) agrupado por materia → unidad → comisión.
- `pendientes-page`: Página `/pendientes` del frontend con acordeón Materia → Unidad → Comisión, stat cards globales, filtro "Solo con pendientes", y botón "Ver en Moodle" con deep link al grader.

### Modified Capabilities

- `docker-local-env`: Sin cambio de requisitos — solo puede requerir nueva variable de entorno `MOODLE_HOST` en el `.env.example`, no hay cambio de comportamiento.

## Impact

**Backend:**
- `app/models/usuario.py` — agregar campos `moodle_username`, `moodle_password_encrypted`, `moodle_host`
- `app/schemas/usuario.py` — DTOs para guardar/leer credenciales Moodle
- `app/services/moodle_service.py` — lógica de autenticación y consulta al webservice
- `app/routers/pendientes.py` — nuevo router con endpoint `GET /api/pendientes/moodle`
- `app/routers/usuarios.py` — endpoints PATCH para actualizar credenciales Moodle
- Nueva migración Alembic para los campos de credenciales Moodle

**Frontend:**
- `src/features/pendientes/` — módulo completo nuevo (types, services, hooks, components, pages)
- `src/features/dashboard/DashboardTutor.tsx` — agregar banner de alerta
- `src/shared/components/Sidebar.tsx` — nuevo ítem de navegación
- `src/features/profile/` — sección de configuración Moodle en el perfil del tutor

**Dependencias externas:**
- Moodle Mobile App webservice API (REST, autenticación por token)
- AES-256 encryption (ya disponible en `app/core/security.py`)
