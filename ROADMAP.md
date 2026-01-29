# ROADMAP - Active-IA

> **Instrucciones**: Marca `[x]` cuando completes una tarea. Trabaja en orden secuencial.
> Cada tarea deberia tomar 1-2 archivos maximo.

---

## Fase 0: Setup Inicial

**Objetivo**: Preparar la estructura base del proyecto.

### Backend Setup

- [x] **0.1** Crear estructura de carpetas del backend

  ```
  backend/
  ├── app/
  │   ├── __init__.py
  │   ├── api/
  │   │   ├── __init__.py
  │   │   ├── v1/
  │   │   │   ├── __init__.py
  │   │   │   └── routers/
  │   │   └── deps.py
  │   ├── services/
  │   ├── repositories/
  │   ├── models/
  │   ├── schemas/
  │   ├── core/
  │   ├── db/
  │   ├── utils/
  │   ├── integrations/
  │   └── main.py
  ├── alembic/
  │   └── versions/
  ├── tests/
  │   ├── unit/
  │   │   ├── services/
  │   │   └── repositories/
  │   └── integration/
  │       └── api/
  ├── requirements.txt
  ├── alembic.ini
  ├── pyproject.toml
  ├── Dockerfile
  └── .env.example
  ```

  **Ref**: `docs/specs/05-ARQUITECTURA-STACK.md` seccion 3.5
  **Archivos**: estructura de carpetas + `__init__.py` vacios

- [x] **0.2** Crear `requirements.txt` con dependencias
      **Ref**: `docs/specs/05-ARQUITECTURA-STACK.md` seccion Tech Stack
      **Archivos**: `backend/requirements.txt`

- [x] **0.3** Crear `backend/app/core/config.py` con settings
      **Incluir**: DATABASE_URL, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE, ENCRYPTION_KEY, N8N settings, CORS, Rate Limiting
      **Ref**: `docs/specs/05-ARQUITECTURA-STACK.md` seccion 11.1, `docs/specs/11-SEGURIDAD.md`
      **Archivos**: `backend/app/core/config.py`, `backend/.env.example`

- [x] **0.4** Crear `backend/app/main.py` base con FastAPI
      **Incluir**: app instance, CORS, health endpoint, lifespan manager, factory function
      **Ref**: `docs/specs/05-ARQUITECTURA-STACK.md` seccion 3
      **Archivos**: `backend/app/main.py`

### Frontend Setup

- [x] **0.5** Inicializar proyecto Vite + React + TypeScript
      **Comando**: `npm create vite@latest frontend -- --template react-ts`
      **Archivos**: proyecto frontend inicializado (package.json, tsconfig.json, vite.config.ts, etc.)

- [x] **0.6** Instalar dependencias frontend
      **Incluir**: tailwindcss, @tailwindcss/vite, react-router-dom, @tanstack/react-query, axios, react-hook-form, zod, lucide-react, react-hot-toast, date-fns, clsx, tailwind-merge
      **Ref**: `docs/specs/05-ARQUITECTURA-STACK.md` seccion 2.2
      **Archivos**: `frontend/package.json`

- [x] **0.7** Configurar Tailwind CSS
      **Nota**: Tailwind v4 usa @tailwindcss/vite plugin y configuracion en CSS (@theme) en lugar de tailwind.config.js
      **Ref**: `docs/specs/08-SISTEMA-DISENO-ESTILOS.md`
      **Archivos**: `frontend/vite.config.ts`, `frontend/src/index.css`, `frontend/tsconfig.app.json`

- [x] **0.8** Crear estructura de carpetas frontend
  ```
  frontend/src/
  ├── app/
  ├── features/
  ├── shared/
  │   ├── components/
  │   ├── hooks/
  │   ├── services/
  │   ├── types/
  │   └── utils/
  └── assets/
  ```
  **Archivos**: estructura de carpetas, types/index.ts, services/api-client.ts, utils/cn.ts

---

## Fase 1: Backend - Auth + Modelos Base

**Objetivo**: Implementar modelos SQLAlchemy y autenticacion JWT.
**Ref principal**: `docs/specs/06-MODELO-DATOS.md`

### Modelos SQLAlchemy

- [x] **1.1** Crear `backend/app/models/base.py`
      **Incluir**: Base declarativa, engine, async_session_maker, TimestampMixin, SoftDeleteMixin, get_async_session
      **Archivos**: `backend/app/models/base.py`, `backend/app/models/__init__.py`

- [x] **1.2** Crear `backend/app/models/enums.py`
      **Incluir**: RolEnum, TipoRubricaEnum, EstadoEntregaEnum, FuenteRubricaEnum
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 3
      **Archivos**: `backend/app/models/enums.py`

- [x] **1.3** Crear `backend/app/models/usuario.py`
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 3.1
      **Archivos**: `backend/app/models/usuario.py`

- [x] **1.4** Crear `backend/app/models/materia.py`
      **Incluir**: Materia, CoordinadorMateria
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 3.2, 3.3
      **Archivos**: `backend/app/models/materia.py`

- [x] **1.5** Crear `backend/app/models/comision.py`
      **Incluir**: Comision, ComisionTutor
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 3.4, 3.5
      **Archivos**: `backend/app/models/comision.py`

- [x] **1.6** Crear `backend/app/models/rubrica.py`
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 3.6
      **Archivos**: `backend/app/models/rubrica.py`

- [x] **1.7** Crear `backend/app/models/entrega.py`
      **Incluir**: Entrega, EntregaHistorial
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 3.7, 3.9
      **Archivos**: `backend/app/models/entrega.py`

- [x] **1.8** Crear `backend/app/models/correccion.py`
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 3.8
      **Archivos**: `backend/app/models/correccion.py`

- [x] **1.9** Configurar Alembic y crear migracion inicial
      **Archivos**: `alembic.ini`, `alembic/env.py`, primera migracion

### Auth Core

- [x] **1.10** Crear `backend/app/core/security.py`
      **Incluir**: hash_password, verify_password, create_access_token, decode_token, encrypt_api_key, decrypt_api_key
      **Ref**: `docs/specs/11-SEGURIDAD.md`
      **Archivos**: `backend/app/core/security.py`

- [x] **1.11** Crear `backend/app/core/dependencies.py`
      **Incluir**: get_db, get_current_user, get_current_active_user
      **Archivos**: `backend/app/core/dependencies.py`

- [x] **1.12** Crear `backend/app/core/permissions.py`
      **Incluir**: require_admin, require_coordinador, require_tutor, require_any_role
      **Ref**: `docs/specs/11-SEGURIDAD.md`
      **Archivos**: `backend/app/core/permissions.py`

---

## Fase 2: Backend - CRUD Basico

**Objetivo**: Implementar endpoints de usuarios, materias y comisiones.
**Ref principal**: `docs/specs/03-REQUISITOS-FUNCIONALES.md`

### Auth Module

- [x] **2.1** Crear `backend/app/schemas/auth.py`
      **Incluir**: LoginRequest, TokenResponse, ChangePasswordRequest
      **Archivos**: `backend/app/schemas/auth.py`

- [x] **2.2** Crear `backend/app/services/auth_service.py`
      **Incluir**: authenticate_user, change_password
      **Archivos**: `backend/app/services/auth_service.py`

- [x] **2.3** Crear `backend/app/routers/auth.py`
      **Endpoints**: POST /auth/login, POST /auth/change-password
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 2
      **Archivos**: `backend/app/routers/auth.py`

### Usuarios Module

- [x] **2.4** Crear `backend/app/schemas/usuario.py`
      **Incluir**: UsuarioCreate, UsuarioUpdate, UsuarioResponse, UsuarioList
      **Archivos**: `backend/app/schemas/usuario.py`

- [x] **2.5** Crear `backend/app/repositories/usuario_repository.py`
      **Incluir**: create, get_by_id, get_by_username, get_all, update, soft_delete, restore
      **Archivos**: `backend/app/repositories/usuario_repository.py`

- [x] **2.6** Crear `backend/app/services/usuario_service.py`
      **Incluir**: crear_usuario, listar_usuarios, obtener_usuario, actualizar_usuario, eliminar_usuario, restaurar_usuario, resetear_password
      **Archivos**: `backend/app/services/usuario_service.py`

- [x] **2.7** Crear `backend/app/routers/usuarios.py`
      **Endpoints**: GET, POST, GET/:id, PUT/:id, DELETE/:id, POST/:id/restore, POST/:id/reset-password
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 3
      **Archivos**: `backend/app/routers/usuarios.py`

### Materias Module

- [x] **2.8** Crear `backend/app/schemas/materia.py`
      **Incluir**: MateriaCreate, MateriaUpdate, MateriaResponse, MateriaList
      **Archivos**: `backend/app/schemas/materia.py`

- [x] **2.9** Crear `backend/app/repositories/materia_repository.py`
      **Archivos**: `backend/app/repositories/materia_repository.py`

- [x] **2.10** Crear `backend/app/services/materia_service.py`
      **Incluir**: crear_materia, listar_materias, asignar_coordinadores
      **Archivos**: `backend/app/services/materia_service.py`

- [x] **2.11** Crear `backend/app/routers/materias.py`
      **Endpoints**: GET, POST, GET/:id, PUT/:id, DELETE/:id, POST/:id/coordinadores
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 4
      **Archivos**: `backend/app/routers/materias.py`

### Comisiones Module

- [x] **2.12** Crear `backend/app/schemas/comision.py`
      **Archivos**: `backend/app/schemas/comision.py`

- [x] **2.13** Crear `backend/app/repositories/comision_repository.py`
      **Archivos**: `backend/app/repositories/comision_repository.py`

- [x] **2.14** Crear `backend/app/services/comision_service.py`
      **Incluir**: crear_comision, listar_comisiones, asignar_tutores
      **Archivos**: `backend/app/services/comision_service.py`

- [x] **2.15** Crear `backend/app/routers/comisiones.py`
      **Endpoints**: GET, POST, GET/:id, PUT/:id, DELETE/:id, POST/:id/restore, POST/:id/tutores
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 5
      **Archivos**: `backend/app/routers/comisiones.py`

---

## Fase 3: Backend - Rubricas + Entregas

**Objetivo**: Implementar gestion de rubricas y carga de entregas.
**Ref principal**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` secciones 6-7

### Rubricas Module

- [x] **3.1** Crear `backend/app/schemas/rubrica.py`
      **Incluir**: RubricaCreate, RubricaUpdate, CriterioSchema, RubricaResponse
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 4.1
      **Archivos**: `backend/app/schemas/rubrica.py`

- [x] **3.2** Crear `backend/app/repositories/rubrica_repository.py`
      **Archivos**: `backend/app/repositories/rubrica_repository.py`

- [x] **3.3** Crear `backend/app/services/rubrica_service.py`
      **Incluir**: crear_rubrica_manual, duplicar_rubrica, validar_criterios (suma=100)
      **Archivos**: `backend/app/services/rubrica_service.py`

- [x] **3.4** Crear `backend/app/routers/rubricas.py`
      **Endpoints**: GET, POST, GET/:id, PUT/:id, DELETE/:id, POST/:id/restore, POST/:id/duplicar
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 6
      **Archivos**: `backend/app/routers/rubricas.py`

### Entregas Module

- [x] **3.5** Crear `backend/app/schemas/entrega.py`
      **Incluir**: EntregaCreate, EntregaResponse, CargaMasivaResponse
      **Archivos**: `backend/app/schemas/entrega.py`

- [x] **3.6** Crear `backend/app/repositories/entrega_repository.py`
      **Archivos**: `backend/app/repositories/entrega_repository.py`

- [x] **3.7** Crear `backend/app/services/consolidacion_service.py`
      **Incluir**: consolidar_zip, extraer_codigo, MODOS_CONSOLIDACION
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 7.3
      **Archivos**: `backend/app/services/consolidacion_service.py`

- [x] **3.8** Crear `backend/app/services/entrega_service.py`
      **Incluir**: crear_entrega_individual, crear_entregas_masivas, manejar_duplicados
      **Archivos**: `backend/app/services/entrega_service.py`

- [x] **3.9** Crear `backend/app/routers/entregas.py`
      **Endpoints**: GET, POST (individual), POST /masiva, GET/:id, DELETE/:id, GET/:id/contenido
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 7
      **Archivos**: `backend/app/routers/entregas.py`

### Historial Module

- [x] **3.10** Crear `backend/app/repositories/entrega_historial_repository.py`
      **Archivos**: `backend/app/repositories/entrega_historial_repository.py`

- [x] **3.11** Crear `backend/app/services/historial_service.py`
      **Incluir**: guardar_version_anterior
      **Archivos**: `backend/app/services/historial_service.py`

### Tests Fase 3

- [x] **3.12** Tests para rubrica_service
      **Archivos**: `backend/tests/unit/services/test_rubrica_service.py`

- [x] **3.13** Tests para consolidacion_service
      **Archivos**: `backend/tests/unit/services/test_consolidacion_service.py`

- [x] **3.14** Tests para entrega_service
      **Archivos**: `backend/tests/unit/services/test_entrega_service.py`

---

## Fase 4: Backend - Correccion IA

**Objetivo**: Implementar integracion con N8N y Gemini.
**Ref principal**: `skills/correccion-ia/SKILL.md`, `docs/specs/10-INTEGRACIONES.md`

### Integracion N8N

- [x] **4.1** Crear `backend/app/integrations/n8n_client.py`
      **Incluir**: enviar_correccion, reintentos, timeout 90s
      **Ref**: `skills/correccion-ia/SKILL.md` seccion N8N Client
      **Archivos**: `backend/app/integrations/n8n_client.py`

- [x] **4.2** Crear `backend/app/schemas/correccion.py`
      **Incluir**: CorreccionCreate, CorreccionResponse, CriterioCorreccionSchema, GeminiResponse
      **Ref**: `docs/specs/06-MODELO-DATOS.md` seccion 4.2
      **Archivos**: `backend/app/schemas/correccion.py`

### Correccion Module

- [x] **4.3** Crear `backend/app/repositories/correccion_repository.py`
      **Archivos**: `backend/app/repositories/correccion_repository.py`

- [x] **4.4** Crear `backend/app/services/correccion_service.py`
      **Incluir**: corregir_individual, corregir_lote, recorregir, parsear_respuesta_gemini
      **Ref**: `skills/correccion-ia/SKILL.md` seccion Flujo Completo
      **Archivos**: `backend/app/services/correccion_service.py`

- [x] **4.5** Crear `backend/app/routers/correcciones.py`
      **Endpoints**: POST /entregas/:id/corregir, POST /entregas/corregir-lote, POST /correcciones/:id/recorregir, GET /correcciones/:id, PUT /correcciones/:id
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 8
      **Archivos**: `backend/app/routers/correcciones.py`

### Generacion Rubricas desde PDF

- [x] **4.6** Crear `backend/app/services/rubrica_ia_service.py`
      **Incluir**: generar_rubrica_desde_pdf
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` HU-RUB-02
      **Archivos**: `backend/app/services/rubrica_ia_service.py`

- [x] **4.7** Agregar endpoint POST /rubricas/desde-pdf
      **Archivos**: `backend/app/routers/rubricas.py` (modificar)

### Documentos Module

- [x] **4.8** Crear `backend/app/services/pdf_service.py`
      **Incluir**: generar_pdf_devolucion, generar_zip_pdfs
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` seccion 10.2
      **Archivos**: `backend/app/services/pdf_service.py`

- [x] **4.9** Crear `backend/app/services/excel_service.py`
      **Incluir**: exportar_notas_excel
      **Archivos**: `backend/app/services/excel_service.py`

- [x] **4.10** Crear `backend/app/routers/documentos.py`
      **Endpoints**: GET /correcciones/:id/pdf, GET /comisiones/:id/rubricas/:rubrica_id/pdfs, GET /comisiones/:id/rubricas/:rubrica_id/excel
      **Archivos**: `backend/app/routers/documentos.py`

---

## Fase 5: Frontend - Setup + Auth

**Objetivo**: Configurar frontend y implementar autenticacion.
**Ref principal**: `frontend/AGENTS.md`, `skills/react-typescript/SKILL.md`

### Configuracion Base

- [x] **5.1** Configurar React Router con rutas base
      **Incluir**: Layout principal, rutas publicas/protegidas
      **Archivos**: `frontend/src/app/router.tsx`, `frontend/src/app/App.tsx`

- [x] **5.2** Configurar React Query
      **Archivos**: `frontend/src/app/providers.tsx`

- [x] **5.3** Crear cliente Axios con interceptors
      **Incluir**: baseURL, token injection, error handling
      **Archivos**: `frontend/src/shared/services/api-client.ts`

- [x] **5.4** Crear tipos compartidos
      **Incluir**: User, Rol, ApiResponse, ApiError
      **Archivos**: `frontend/src/shared/types/index.ts`

### Componentes UI Base

- [x] **5.5** Crear componentes UI base
      **Incluir**: Button, Input, Select, Modal, Badge, Spinner
      **Ref**: `docs/specs/08-SISTEMA-DISENO-ESTILOS.md`
      **Archivos**: `frontend/src/shared/components/ui/`

- [x] **5.6** Crear Layout principal
      **Incluir**: Sidebar, Header, Main content area
      **Ref**: `docs/specs/07-DISENO-UI-UX.md` seccion Navegacion
      **Archivos**: `frontend/src/shared/components/layout/`

### Auth Feature

- [x] **5.7** Crear auth service
      **Archivos**: `frontend/src/features/auth/services/auth-service.ts`

- [x] **5.8** Crear auth hooks
      **Incluir**: useAuth, useLogin, useLogout
      **Archivos**: `frontend/src/features/auth/hooks/`

- [x] **5.9** Crear LoginPage
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` HU-AUTH-01
      **Archivos**: `frontend/src/features/auth/pages/LoginPage.tsx`

- [x] **5.10** Crear ChangePasswordModal
      **Ref**: `docs/specs/03-REQUISITOS-FUNCIONALES.md` HU-AUTH-02
      **Archivos**: `frontend/src/features/auth/components/ChangePasswordModal.tsx`

---

## Fase 6: Frontend - Features

**Objetivo**: Implementar todas las features del frontend.
**Ref principal**: `docs/specs/07-DISENO-UI-UX.md`

### Dashboard

- [x] **6.1** Crear DashboardPage por rol
      **Archivos**: `frontend/src/features/dashboard/pages/DashboardPage.tsx`

### Usuarios Feature (Admin)

- [x] **6.2** Crear usuarios service
      **Archivos**: `frontend/src/features/usuarios/services/usuarios-service.ts`

- [x] **6.3** Crear usuarios hooks
      **Archivos**: `frontend/src/features/usuarios/hooks/`

- [x] **6.4** Crear UsuariosPage
      **Incluir**: Tabla, filtros, acciones
      **Archivos**: `frontend/src/features/usuarios/pages/UsuariosPage.tsx`

- [x] **6.5** Crear UsuarioForm modal
      **Archivos**: `frontend/src/features/usuarios/components/UsuarioForm.tsx`

### Materias Feature

- [x] **6.6** Crear materias service y hooks
      **Archivos**: `frontend/src/features/materias/`

- [x] **6.7** Crear MateriasPage
      **Archivos**: `frontend/src/features/materias/pages/MateriasPage.tsx`

- [x] **6.8** Crear MateriaForm modal
      **Archivos**: `frontend/src/features/materias/components/MateriaForm.tsx`

### Comisiones Feature

- [x] **6.9** Crear comisiones service y hooks
      **Archivos**: `frontend/src/features/comisiones/`

- [x] **6.10** Crear ComisionesPage
      **Archivos**: `frontend/src/features/comisiones/pages/ComisionesPage.tsx`

- [x] **6.11** Crear ComisionForm modal
      **Archivos**: `frontend/src/features/comisiones/components/ComisionForm.tsx`

### Rubricas Feature

- [x] **6.12** Crear rubricas service y hooks
      **Archivos**: `frontend/src/features/rubricas/`

- [x] **6.13** Crear RubricasPage
      **Archivos**: `frontend/src/features/rubricas/pages/RubricasPage.tsx`

- [x] **6.14** Crear RubricaEditor
      **Incluir**: Editor de criterios drag-and-drop
      **Archivos**: `frontend/src/features/rubricas/components/RubricaEditor.tsx`

### Entregas Feature

- [ ] **6.15** Crear entregas service y hooks
      **Archivos**: `frontend/src/features/entregas/`

- [ ] **6.16** Crear EntregasPage
      **Incluir**: Tabla, filtros, seleccion multiple
      **Archivos**: `frontend/src/features/entregas/pages/EntregasPage.tsx`

- [ ] **6.17** Crear CargaEntregaModal
      **Incluir**: Individual y masiva
      **Archivos**: `frontend/src/features/entregas/components/CargaEntregaModal.tsx`

### Correcciones Feature

- [ ] **6.18** Crear correcciones service y hooks
      **Archivos**: `frontend/src/features/correcciones/`

- [ ] **6.19** Crear CorreccionDetailModal
      **Incluir**: Vista y edicion de correccion
      **Archivos**: `frontend/src/features/correcciones/components/CorreccionDetailModal.tsx`

### Perfil Feature

- [ ] **6.20** Crear PerfilPage
      **Incluir**: Datos, API Key, cambio password
      **Archivos**: `frontend/src/features/perfil/pages/PerfilPage.tsx`

---

## Fase 7: Testing + Integracion

**Objetivo**: Tests end-to-end y verificacion de integracion.

### Backend Tests

- [ ] **7.1** Tests de autenticacion
      **Archivos**: `backend/tests/test_auth.py`

- [ ] **7.2** Tests de usuarios
      **Archivos**: `backend/tests/test_usuarios.py`

- [ ] **7.3** Tests de permisos
      **Archivos**: `backend/tests/test_permissions.py`

- [ ] **7.4** Tests de correcciones
      **Archivos**: `backend/tests/test_correcciones.py`

### Frontend Tests

- [ ] **7.5** Tests de componentes UI
      **Archivos**: `frontend/src/shared/components/__tests__/`

- [ ] **7.6** Tests de hooks
      **Archivos**: `frontend/src/features/**/__tests__/`

### Integracion

- [ ] **7.7** Test de flujo completo de correccion
      **Archivos**: `backend/tests/test_integration_correccion.py`

- [ ] **7.8** Verificar todos los endpoints documentados
      **Archivos**: Postman collection o similar

---

## Fase 8: Docker + Deploy

**Objetivo**: Contenedorizacion y preparacion para produccion.
**Ref**: `docs/specs/13-INFRAESTRUCTURA-DEPLOY.md`

### Docker

- [ ] **8.1** Crear Dockerfile backend
      **Archivos**: `backend/Dockerfile`

- [ ] **8.2** Crear Dockerfile frontend
      **Archivos**: `frontend/Dockerfile`

- [ ] **8.3** Crear docker-compose.yml
      **Incluir**: backend, frontend, postgres, nginx
      **Archivos**: `docker-compose.yml`

### Configuracion

- [ ] **8.4** Crear .env.example
      **Archivos**: `.env.example`

- [ ] **8.5** Crear nginx.conf
      **Archivos**: `nginx/nginx.conf`

- [ ] **8.6** Documentar deploy
      **Archivos**: `docs/DEPLOY.md`

---

## Resumen de Fases

| Fase | Descripcion                   | Tareas | Dependencias   |
| ---- | ----------------------------- | ------ | -------------- |
| 0    | Setup Inicial                 | 8      | Ninguna        |
| 1    | Backend - Auth + Modelos      | 12     | Fase 0         |
| 2    | Backend - CRUD Basico         | 15     | Fase 1         |
| 3    | Backend - Rubricas + Entregas | 14     | Fase 2         |
| 4    | Backend - Correccion IA       | 10     | Fase 3         |
| 5    | Frontend - Setup + Auth       | 10     | Fase 2         |
| 6    | Frontend - Features           | 20     | Fase 4, Fase 5 |
| 7    | Testing + Integracion         | 8      | Fase 6         |
| 8    | Docker + Deploy               | 6      | Fase 7         |

**Total: 103 tareas**

---

## Notas

- Cada tarea esta disenada para ser completada en una sesion corta
- Las referencias (Ref:) indican documentacion a consultar
- Marcar `[x]` al completar, actualizar ESTADO.md
- Si una tarea se bloquea, documentar en ESTADO.md seccion "Bloqueantes"

---

_Ultima actualizacion: 2026-01-26_
