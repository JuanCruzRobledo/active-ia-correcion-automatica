# 09 - Patrones de Código y Convenciones

> ⚠️ **Sección/spec parcialmente obsoleta:** la integración de IA ya NO usa N8N. La corrección es nativa en el backend (`backend/app/integrations/`: `ia_provider.py` rutea a `gemini_correction_client.py` / `openrouter_client.py`, llamada HTTP directa a Gemini Studio / OpenRouter). Los ejemplos de código que nombran N8N a continuación son históricos.

---

## 1. Resumen Ejecutivo

Este documento define los patrones de código, convenciones y buenas prácticas obligatorias para el desarrollo del proyecto Active-IA. Aplica tanto al backend (Python/FastAPI) como al frontend (React/TypeScript).

| Aspecto | Decisión |
|---------|----------|
| **Arquitectura Backend** | Clean Architecture (Routers → Services → Repositories) |
| **Arquitectura Frontend** | Feature-based |
| **Límite LOC** | 500 líneas máximo por archivo (ambos) |
| **Principios** | SOLID + Clean Code |
| **Naming** | snake_case archivos, camelCase/PascalCase código |
| **Documentación** | Docstrings completos en todas las funciones |

---

## 2. Clean Architecture - Backend

### 2.1 Principio Fundamental

El backend implementa **Clean Architecture** con separación estricta de responsabilidades. Cada capa tiene una única responsabilidad y no puede saltarse capas.

```
┌─────────────────────────────────────────────────────────────────────┐
│                            HTTP Request                              │
└─────────────────────────────────┬───────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           ROUTERS                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • Reciben request HTTP                                       │    │
│  │ • Validan entrada con Pydantic Schemas (DTOs)               │    │
│  │ • Invocan Services via Depends()                            │    │
│  │ • Retornan response HTTP                                     │    │
│  │ • ❌ PROHIBIDO: Lógica de negocio, acceso a BD              │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ Depends()
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           SERVICES                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • Contienen TODA la lógica de negocio                       │    │
│  │ • Orquestan flujo entre múltiples repositories              │    │
│  │ • Aplican reglas de dominio y validaciones de negocio       │    │
│  │ • Lanzan excepciones de dominio                             │    │
│  │ • ❌ PROHIBIDO: Conocer HTTP, acceso directo a BD           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ Depends()
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         REPOSITORIES                                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • Interactúan exclusivamente con la BD (SQLAlchemy)         │    │
│  │ • Implementan operaciones CRUD                               │    │
│  │ • Manejan queries complejas                                  │    │
│  │ • Gestionan transacciones                                    │    │
│  │ • ❌ PROHIBIDO: Lógica de negocio, validaciones de dominio  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           DATABASE                                   │
│                         (PostgreSQL)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Responsabilidades por Capa

| Capa | SÍ Hace | NO Hace |
|------|---------|---------|
| **Router** | Validar request, llamar service, retornar response | Lógica de negocio, queries a BD, transformaciones complejas |
| **Service** | Lógica de negocio, orquestación, validaciones de dominio | Conocer HTTP status codes, ejecutar queries SQL |
| **Repository** | CRUD, queries, transacciones BD | Decisiones de negocio, validar reglas de dominio |

### 2.3 Ejemplo: Flujo de Corrección

```
POST /api/v1/entregas/{id}/corregir

1. ROUTER (entrega_router.py)
   ├── Valida {id} es UUID válido
   ├── Extrae usuario del token (via Depends)
   ├── Llama: correccion_service.corregir_entrega(id, usuario)
   └── Retorna: 200 OK con CorreccionResponse

2. SERVICE (correccion_service.py)
   ├── Obtiene entrega: entrega_repository.get_by_id(id)
   ├── Valida: usuario tiene acceso a la comisión
   ├── Valida: usuario tiene API Key configurada
   ├── Obtiene rúbrica: rubrica_repository.get_by_id(entrega.rubric_id)
   ├── Llama a ia_provider (gemini_correction_client / openrouter_client) para corrección
   ├── Procesa respuesta de IA
   ├── Guarda: correccion_repository.create(correccion_data)
   └── Retorna: objeto Correccion

3. REPOSITORY (correccion_repository.py)
   ├── Recibe datos de corrección
   ├── Crea modelo SQLAlchemy
   ├── db.add(correccion)
   ├── db.commit()
   └── Retorna: modelo Correccion con ID generado
```

### 2.4 Dependency Injection

Todas las dependencias se inyectan usando `Depends()` de FastAPI:

```python
# app/api/deps.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_session
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provee sesión de base de datos."""
    async with async_session_maker() as session:
        yield session

def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """Provee instancia de UserRepository."""
    return UserRepository(db)

def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository)
) -> UserService:
    """Provee instancia de UserService."""
    return UserService(user_repo)
```

```python
# app/api/v1/routers/user_router.py
from fastapi import APIRouter, Depends
from app.api.deps import get_user_service
from app.services.user_service import UserService

router = APIRouter()

@router.get("/{user_id}")
async def get_user(
    user_id: int,
    user_service: UserService = Depends(get_user_service)
):
    """Obtiene un usuario por ID."""
    return await user_service.get_by_id(user_id)
```

---

## 3. Quality Gate - Límite de 500 LOC

### 3.1 Regla Innegociable

| Métrica | Límite | Consecuencia |
|---------|--------|--------------|
| **Líneas por archivo** | 500 LOC máximo | Refactorizar inmediatamente |
| **Líneas por clase** | 500 LOC máximo | Dividir en clases especializadas |
| **Líneas por función** | 50 LOC recomendado | Extraer funciones auxiliares |

**Aplica a:** Backend (Python) y Frontend (React/TypeScript)

### 3.2 Cómo Refactorizar

Cuando un archivo se acerca a 500 LOC:

**Opción 1: Dividir por responsabilidad**
```
# ANTES: entrega_service.py (480 LOC)
class EntregaService:
    def create()
    def update()
    def delete()
    def corregir()
    def consolidar()
    def generar_pdf()
    def exportar_excel()

# DESPUÉS: Dividir en servicios especializados
entrega_service.py (150 LOC)      → CRUD básico
correccion_service.py (200 LOC)   → Lógica de corrección
consolidation_service.py (180 LOC) → Consolidación de código
export_service.py (120 LOC)        → PDF y Excel
```

**Opción 2: Extraer clases auxiliares**
```python
# ANTES: Un service gigante
class CorreccionService:
    def _validar_permisos()
    def _obtener_api_key()
    def _llamar_ia_provider()
    def _procesar_respuesta()
    def _calcular_nota()
    ...

# DESPUÉS: Clases especializadas
class PermisoValidator:
    def validar_acceso_comision()
    def validar_api_key()

class IAProviderClient:  # gemini_correction_client / openrouter_client
    def corregir()
    def generar_rubrica()

class CorreccionProcessor:
    def procesar_respuesta()
    def calcular_nota()
```

### 3.3 Señales de Alerta

Refactorizar cuando:
- Archivo supera 400 LOC (preventivo)
- Clase tiene más de 10 métodos públicos
- Función tiene más de 5 parámetros
- Hay código duplicado entre archivos
- Un cambio requiere modificar múltiples lugares

---

## 4. Principios SOLID

### 4.1 Aplicación Práctica

| Principio | Aplicación en Active-IA |
|-----------|------------------------|
| **S** - Single Responsibility | Cada clase tiene UNA razón para cambiar. `UserService` solo maneja usuarios. |
| **O** - Open/Closed | Nuevos tipos de corrección se agregan sin modificar `CorreccionService`. |
| **L** - Liskov Substitution | Todos los repositories heredan de `BaseRepository` y son intercambiables. |
| **I** - Interface Segregation | Interfaces pequeñas y específicas, no una interfaz gigante. |
| **D** - Dependency Inversion | Services dependen de abstracciones (Repository interface), no de implementaciones. |

### 4.2 Ejemplo: Dependency Inversion

```python
# app/repositories/base_repository.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    """Interfaz base para todos los repositories."""

    @abstractmethod
    async def get_by_id(self, id: int) -> T | None:
        """Obtiene entidad por ID."""
        pass

    @abstractmethod
    async def create(self, data: dict) -> T:
        """Crea nueva entidad."""
        pass

    @abstractmethod
    async def update(self, id: int, data: dict) -> T:
        """Actualiza entidad existente."""
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """Elimina entidad (soft delete)."""
        pass

# app/repositories/user_repository.py
class UserRepository(BaseRepository[User]):
    """Implementación concreta para usuarios."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, id: int) -> User | None:
        """Obtiene usuario por ID."""
        result = await self.db.execute(
            select(User).where(User.id == id, User.deleted == False)
        )
        return result.scalar_one_or_none()
```

---

## 5. Arquitectura Frontend - Feature-Based

### 5.1 Estructura de Carpetas

```
frontend/src/
├── features/                    # Módulos de negocio
│   ├── auth/                    # Autenticación
│   │   ├── components/
│   │   │   ├── LoginForm.tsx
│   │   │   └── ChangePasswordForm.tsx
│   │   ├── hooks/
│   │   │   └── useAuth.ts
│   │   ├── services/
│   │   │   └── auth_service.ts
│   │   ├── types/
│   │   │   └── auth.types.ts
│   │   └── index.ts             # Exportaciones públicas
│   │
│   ├── entregas/                # Gestión de entregas
│   │   ├── components/
│   │   │   ├── EntregasList.tsx
│   │   │   ├── EntregaUpload.tsx
│   │   │   ├── EntregaCard.tsx
│   │   │   └── CorreccionModal.tsx
│   │   ├── hooks/
│   │   │   ├── useEntregas.ts
│   │   │   └── useCorreccion.ts
│   │   ├── services/
│   │   │   └── entrega_service.ts
│   │   ├── types/
│   │   │   └── entrega.types.ts
│   │   └── index.ts
│   │
│   ├── rubricas/                # Gestión de rúbricas
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   │
│   ├── comisiones/              # Gestión de comisiones
│   ├── materias/                # Gestión de materias
│   ├── usuarios/                # Gestión de usuarios
│   └── reportes/                # Reportes y exportación
│
├── shared/                      # Código compartido
│   ├── components/              # Componentes UI reutilizables
│   │   ├── ui/                  # Componentes base (Button, Input, Modal)
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Table.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Alert.tsx
│   │   │   ├── Tooltip.tsx
│   │   │   └── TooltipIcon.tsx
│   │   └── layout/              # Layout components
│   │       ├── AppLayout.tsx
│   │       ├── Sidebar.tsx
│   │       └── Header.tsx
│   │
│   ├── hooks/                   # Hooks compartidos
│   │   ├── useApi.ts
│   │   ├── useDebounce.ts
│   │   └── useLocalStorage.ts
│   │
│   ├── services/                # Servicios compartidos
│   │   └── api_client.ts        # Cliente Axios configurado
│   │
│   ├── types/                   # Tipos compartidos
│   │   ├── api.types.ts
│   │   └── common.types.ts
│   │
│   └── utils/                   # Utilidades
│       ├── formatters.ts
│       └── validators.ts
│
├── pages/                       # Páginas/Rutas
│   ├── auth/
│   │   ├── LoginPage.tsx
│   │   └── ChangePasswordPage.tsx
│   ├── admin/
│   │   ├── DashboardPage.tsx
│   │   ├── UsuariosPage.tsx
│   │   └── MateriasPage.tsx
│   ├── coordinador/
│   │   ├── DashboardPage.tsx
│   │   └── RubricasPage.tsx
│   └── tutor/
│       ├── DashboardPage.tsx
│       ├── EntregasPage.tsx
│       └── CorreccionesPage.tsx
│
├── styles/                      # Estilos globales
│   ├── globals.css
│   └── variables.css
│
├── App.tsx
├── main.tsx
└── router.tsx
```

### 5.2 Reglas de Importación Frontend

```typescript
// ✅ CORRECTO: Importar desde el index del feature
import { LoginForm, useAuth } from '@/features/auth';
import { EntregasList, useEntregas } from '@/features/entregas';

// ✅ CORRECTO: Importar componentes compartidos
import { Button, Modal, Card } from '@/shared/components/ui';
import { useApi } from '@/shared/hooks';

// ❌ INCORRECTO: Importar directamente de archivos internos
import { LoginForm } from '@/features/auth/components/LoginForm';
```

### 5.3 Cada Feature Expone su API Pública

```typescript
// features/entregas/index.ts
// Componentes públicos
export { EntregasList } from './components/EntregasList';
export { EntregaUpload } from './components/EntregaUpload';
export { CorreccionModal } from './components/CorreccionModal';

// Hooks públicos
export { useEntregas } from './hooks/useEntregas';
export { useCorreccion } from './hooks/useCorreccion';

// Tipos públicos
export type { Entrega, Correccion } from './types/entrega.types';

// NO exportar: componentes internos, servicios (se usan via hooks)
```

---

## 6. Convenciones de Nombres

### 6.1 Backend (Python)

| Elemento | Convención | Ejemplo |
|----------|------------|---------|
| **Archivos** | snake_case | `user_service.py`, `entrega_repository.py` |
| **Clases** | PascalCase | `UserService`, `EntregaRepository` |
| **Funciones** | snake_case | `get_by_id()`, `create_entrega()` |
| **Variables** | snake_case | `user_id`, `entrega_data` |
| **Constantes** | UPPER_SNAKE | `MAX_FILE_SIZE`, `DEFAULT_PAGE_SIZE` |
| **Modelos SQLAlchemy** | PascalCase singular | `User`, `Entrega`, `Correccion` |
| **Schemas Pydantic** | PascalCase + sufijo | `UserCreate`, `UserResponse`, `UserUpdate` |

```python
# Ejemplo completo
# app/services/entrega_service.py

from app.repositories.entrega_repository import EntregaRepository
from app.schemas.entrega_schema import EntregaCreate, EntregaResponse

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

class EntregaService:
    """Servicio para gestión de entregas."""

    def __init__(self, entrega_repo: EntregaRepository):
        """
        Inicializa el servicio de entregas.

        Args:
            entrega_repo: Repositorio de entregas inyectado.
        """
        self.entrega_repo = entrega_repo

    async def create_entrega(self, data: EntregaCreate) -> EntregaResponse:
        """
        Crea una nueva entrega.

        Args:
            data: Datos de la entrega a crear.

        Returns:
            EntregaResponse con la entrega creada.

        Raises:
            ValidationError: Si los datos son inválidos.
        """
        pass
```

### 6.2 Frontend (TypeScript/React)

| Elemento | Convención | Ejemplo |
|----------|------------|---------|
| **Archivos componentes** | PascalCase.tsx | `UserCard.tsx`, `EntregasList.tsx` |
| **Archivos servicios/hooks** | snake_case.ts | `user_service.ts`, `useAuth.ts` |
| **Archivos tipos** | snake_case.types.ts | `user.types.ts` |
| **Componentes** | PascalCase | `UserCard`, `EntregasList` |
| **Hooks** | camelCase con use | `useAuth`, `useEntregas` |
| **Funciones** | camelCase | `formatDate()`, `validateEmail()` |
| **Variables** | camelCase | `userId`, `entregaData` |
| **Constantes** | UPPER_SNAKE | `API_BASE_URL`, `MAX_ITEMS` |
| **Interfaces/Types** | PascalCase | `User`, `Entrega`, `ApiResponse` |

```typescript
// Ejemplo completo
// features/entregas/hooks/useEntregas.ts

import { useState, useCallback } from 'react';
import { Entrega, EntregaFilters } from '../types/entrega.types';

const DEFAULT_PAGE_SIZE = 20;

/**
 * Hook para gestionar entregas.
 *
 * @returns Objeto con entregas, loading state y funciones de gestión.
 */
export function useEntregas() {
  const [entregas, setEntregas] = useState<Entrega[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  /**
   * Obtiene entregas con filtros.
   *
   * @param filters - Filtros a aplicar (comision, rubrica, estado).
   */
  const fetchEntregas = useCallback(async (filters: EntregaFilters) => {
    setIsLoading(true);
    // ...
  }, []);

  return { entregas, isLoading, fetchEntregas };
}
```

### 6.3 Nombres de Archivos Especiales

| Tipo | Patrón | Ejemplo |
|------|--------|---------|
| **Router** | `{entity}_router.py` | `user_router.py` |
| **Service** | `{entity}_service.py` | `user_service.py` |
| **Repository** | `{entity}_repository.py` | `user_repository.py` |
| **Schema** | `{entity}_schema.py` | `user_schema.py` |
| **Model** | `{entity}.py` | `user.py` |
| **Test** | `test_{entity}_{layer}.py` | `test_user_service.py` |

---

## 7. Manejo de Errores

### 7.1 Excepciones Personalizadas

```python
# app/core/exceptions.py

class AppException(Exception):
    """Excepción base de la aplicación."""

    def __init__(self, message: str, code: str = "APP_ERROR"):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje descriptivo del error.
            code: Código único del error.
        """
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppException):
    """Recurso no encontrado."""

    def __init__(self, resource: str, id: int | str):
        """
        Inicializa error de recurso no encontrado.

        Args:
            resource: Nombre del recurso (ej: "Usuario").
            id: Identificador del recurso.
        """
        super().__init__(
            message=f"{resource} con ID {id} no encontrado",
            code="NOT_FOUND"
        )


class ValidationError(AppException):
    """Error de validación de datos."""

    def __init__(self, message: str, field: str | None = None):
        """
        Inicializa error de validación.

        Args:
            message: Mensaje descriptivo.
            field: Campo que falló la validación.
        """
        self.field = field
        super().__init__(message=message, code="VALIDATION_ERROR")


class UnauthorizedError(AppException):
    """Usuario no autenticado."""

    def __init__(self, message: str = "No autenticado"):
        """Inicializa error de autenticación."""
        super().__init__(message=message, code="UNAUTHORIZED")


class ForbiddenError(AppException):
    """Usuario sin permisos."""

    def __init__(self, message: str = "Sin permisos para esta acción"):
        """Inicializa error de autorización."""
        super().__init__(message=message, code="FORBIDDEN")


class ConflictError(AppException):
    """Conflicto con estado actual (duplicados, etc)."""

    def __init__(self, message: str):
        """Inicializa error de conflicto."""
        super().__init__(message=message, code="CONFLICT")


class ExternalServiceError(AppException):
    """Error en servicio externo (proveedor de IA: Gemini Studio / OpenRouter)."""

    def __init__(self, service: str, message: str):
        """
        Inicializa error de servicio externo.

        Args:
            service: Nombre del servicio (ej: "Gemini", "OpenRouter").
            message: Mensaje de error.
        """
        super().__init__(
            message=f"Error en {service}: {message}",
            code="EXTERNAL_SERVICE_ERROR"
        )
```

### 7.2 Handler Global de Excepciones

```python
# app/core/exception_handlers.py

from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import (
    AppException,
    NotFoundError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
)

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handler global para excepciones de la aplicación.

    Args:
        request: Request de FastAPI.
        exc: Excepción capturada.

    Returns:
        JSONResponse con error formateado.
    """
    status_codes = {
        "NOT_FOUND": 404,
        "VALIDATION_ERROR": 422,
        "UNAUTHORIZED": 401,
        "FORBIDDEN": 403,
        "CONFLICT": 409,
        "EXTERNAL_SERVICE_ERROR": 502,
    }

    status_code = status_codes.get(exc.code, 500)

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        }
    )

# app/main.py
from fastapi import FastAPI
from app.core.exceptions import AppException
from app.core.exception_handlers import app_exception_handler

app = FastAPI()

app.add_exception_handler(AppException, app_exception_handler)
```

### 7.3 Uso en Services

```python
# app/services/entrega_service.py

from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError

class EntregaService:
    """Servicio de entregas."""

    async def get_by_id(self, id: int, user_id: int) -> Entrega:
        """
        Obtiene entrega por ID validando permisos.

        Args:
            id: ID de la entrega.
            user_id: ID del usuario solicitante.

        Returns:
            Entrega encontrada.

        Raises:
            NotFoundError: Si la entrega no existe.
            ForbiddenError: Si el usuario no tiene acceso.
        """
        entrega = await self.entrega_repo.get_by_id(id)

        if not entrega:
            raise NotFoundError("Entrega", id)

        if not await self._user_has_access(user_id, entrega.comision_id):
            raise ForbiddenError("No tiene acceso a esta entrega")

        return entrega
```

---

## 8. Documentación en Código

### 8.1 Docstrings (Python)

Usar formato **Google Style** para todos los docstrings:

```python
def create_correccion(
    self,
    entrega_id: int,
    user_id: int,
    resultado: CorreccionResultado
) -> Correccion:
    """
    Crea una nueva corrección para una entrega.

    Valida que el usuario tenga permisos y que la entrega no esté
    ya corregida. Guarda el resultado de la IA y calcula la nota final.

    Args:
        entrega_id: ID de la entrega a corregir.
        user_id: ID del usuario que realiza la corrección.
        resultado: Resultado de la corrección de IA.

    Returns:
        Correccion creada con nota y feedback.

    Raises:
        NotFoundError: Si la entrega no existe.
        ForbiddenError: Si el usuario no tiene permisos.
        ConflictError: Si la entrega ya fue corregida.

    Example:
        >>> resultado = await ia_service.corregir(codigo, rubrica)
        >>> correccion = await correccion_service.create_correccion(
        ...     entrega_id=1,
        ...     user_id=5,
        ...     resultado=resultado
        ... )
        >>> print(correccion.nota)
        85
    """
    pass
```

### 8.2 Documentación TypeScript (TSDoc)

```typescript
/**
 * Hook para gestionar el proceso de corrección de entregas.
 *
 * @remarks
 * Este hook maneja el estado de corrección, comunicación con la API
 * y actualización optimista de la UI.
 *
 * @example
 * ```tsx
 * const { corregir, isLoading, error } = useCorreccion();
 *
 * const handleCorregir = async () => {
 *   await corregir(entregaIds);
 * };
 * ```
 *
 * @returns Objeto con funciones y estados de corrección.
 */
export function useCorreccion() {
  /**
   * Corrige una o más entregas.
   *
   * @param entregaIds - Array de IDs de entregas a corregir.
   * @returns Promesa que resuelve cuando todas las correcciones terminan.
   * @throws Error si alguna corrección falla.
   */
  const corregir = async (entregaIds: number[]): Promise<void> => {
    // ...
  };

  return { corregir, isLoading, error };
}
```

### 8.3 Qué Documentar

| Elemento | Obligatorio | Contenido |
|----------|-------------|-----------|
| **Clases** | Sí | Descripción, responsabilidad |
| **Funciones públicas** | Sí | Descripción, args, returns, raises |
| **Funciones privadas** | Si son complejas | Descripción breve |
| **Constantes** | Si no es obvio | Qué representa |
| **Tipos/Interfaces** | Sí | Descripción, propiedades clave |

---

## 9. Imports

### 9.1 Python - Absolute Imports

```python
# ✅ CORRECTO: Imports absolutos siempre
from app.services.user_service import UserService
from app.repositories.entrega_repository import EntregaRepository
from app.core.exceptions import NotFoundError
from app.schemas.user_schema import UserCreate, UserResponse

# ❌ INCORRECTO: Imports relativos
from .user_service import UserService
from ..repositories import EntregaRepository
```

### 9.2 Orden de Imports (Python)

```python
# 1. Standard library
import os
import json
from datetime import datetime
from typing import Optional, List

# 2. Third-party packages
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

# 3. Local application imports
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.services.user_service import UserService
from app.schemas.user_schema import UserCreate
```

### 9.3 TypeScript - Path Aliases

```typescript
// tsconfig.json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@/features/*": ["./src/features/*"],
      "@/shared/*": ["./src/shared/*"]
    }
  }
}

// ✅ CORRECTO: Usar aliases
import { Button } from '@/shared/components/ui';
import { useAuth } from '@/features/auth';

// ❌ INCORRECTO: Paths relativos largos
import { Button } from '../../../shared/components/ui/Button';
```

---

## 10. Testing

### 10.1 Estrategia

| Tipo | Cobertura | Ubicación |
|------|-----------|-----------|
| **Unit Tests** | Services, Repositories, Utils | `tests/unit/` |
| **Integration Tests** | Endpoints API completos | `tests/integration/` |

### 10.2 Estructura de Tests

```
tests/
├── unit/
│   ├── services/
│   │   ├── test_user_service.py
│   │   ├── test_entrega_service.py
│   │   └── test_correccion_service.py
│   ├── repositories/
│   │   ├── test_user_repository.py
│   │   └── test_entrega_repository.py
│   └── utils/
│       └── test_validators.py
│
└── integration/
    └── api/
        ├── test_auth_endpoints.py
        ├── test_user_endpoints.py
        ├── test_entrega_endpoints.py
        └── conftest.py  # Fixtures compartidos
```

### 10.3 Naming de Tests

```python
# Patrón: test_{método}_{escenario}_{resultado_esperado}

def test_get_by_id_existing_user_returns_user():
    """Debe retornar usuario cuando existe."""
    pass

def test_get_by_id_nonexistent_user_raises_not_found():
    """Debe lanzar NotFoundError cuando usuario no existe."""
    pass

def test_create_user_duplicate_email_raises_conflict():
    """Debe lanzar ConflictError cuando email ya existe."""
    pass
```

---

## 11. Linting y Formateo

### 11.1 Backend (Python)

**Herramientas:**
- **Ruff**: Linter ultra-rápido (reemplaza flake8, isort, etc.)
- **Black**: Formateador de código

```toml
# pyproject.toml

[tool.ruff]
line-length = 100
target-version = "py311"

select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]

ignore = [
    "E501",   # line too long (Black handles this)
    "B008",   # function call in default argument (needed for Depends)
]

[tool.ruff.isort]
known-first-party = ["app"]

[tool.black]
line-length = 100
target-version = ["py311"]
```

### 11.2 Frontend (TypeScript)

**Herramientas:**
- **ESLint**: Linter
- **Prettier**: Formateador

```json
// .eslintrc.json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "prettier"
  ],
  "rules": {
    "react/react-in-jsx-scope": "off",
    "@typescript-eslint/explicit-function-return-type": "off",
    "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }]
  }
}
```

```json
// .prettierrc
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100
}
```

---

## 12. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Arquitectura Backend** | Clean Architecture: Routers → Services → Repositories |
| **Arquitectura Frontend** | Feature-based con shared/ para código común |
| **Quality Gate** | 500 LOC máximo por archivo/clase |
| **Principios** | SOLID + Clean Code obligatorios |
| **Naming archivos** | snake_case |
| **Naming código** | camelCase funciones, PascalCase clases |
| **Errores** | Excepciones personalizadas + Handler global |
| **Testing** | Unit (services/repos) + Integration (endpoints) |
| **Linting Backend** | Ruff + Black |
| **Linting Frontend** | ESLint + Prettier |
| **Imports Python** | Absolute siempre |
| **Docstrings** | Completos en todas las funciones públicas |

---

## 13. Checklist de Code Review

Antes de aprobar un PR, verificar:

### Backend
- [ ] Routers NO contienen lógica de negocio
- [ ] Services NO acceden directamente a la BD
- [ ] Repositories NO contienen validaciones de dominio
- [ ] Archivo no supera 500 LOC
- [ ] Imports son absolutos
- [ ] Docstrings completos en funciones públicas
- [ ] Excepciones personalizadas, no HTTPException directo
- [ ] Tests unitarios para lógica nueva

### Frontend
- [ ] Componente no supera 500 LOC
- [ ] Hooks extraídos para lógica reutilizable
- [ ] Imports usan path aliases (@/)
- [ ] TSDoc en funciones públicas
- [ ] No hay lógica de negocio en componentes UI

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
