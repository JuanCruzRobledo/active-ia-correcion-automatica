---
name: python-fastapi
description: >
  Patrones y convenciones para desarrollo backend con FastAPI y Clean Architecture.
  Trigger: Cuando trabajes con código Python, endpoints API, modelos SQLAlchemy,
  schemas Pydantic, o cualquier componente del backend.
metadata:
  author: Active-IA Team
  version: "1.0"
  scope: [root, backend]
  auto_invoke:
    - "Creating FastAPI endpoints"
    - "Defining Pydantic schemas"
    - "Writing SQLAlchemy models"
    - "Implementing repositories"
    - "Creating services"
---

# Python FastAPI Skill

## When to Use

- Creando o modificando endpoints API
- Definiendo modelos de base de datos
- Escribiendo schemas de validación
- Implementando lógica de negocio en services
- Creando repositories para acceso a datos

## Clean Architecture - 3 Capas

```
HTTP Request
     ↓
┌─────────────┐
│   ROUTER    │  ← Validación HTTP, autenticación
├─────────────┤
│   SERVICE   │  ← Lógica de negocio, reglas de dominio
├─────────────┤
│ REPOSITORY  │  ← Acceso a datos, queries
└─────────────┘
     ↓
  Database
```

## Critical Patterns

### ALWAYS
- Usar `Depends()` para inyección de dependencias
- Validar entrada con Pydantic schemas
- Retornar schemas Pydantic (no modelos SQLAlchemy directamente)
- Usar `status_code` explícito en decoradores de endpoint
- Soft delete con campo `deleted_at`
- Type hints en todas las funciones
- Docstrings en endpoints públicos

### NEVER
- Lógica de negocio en routers
- Queries SQLAlchemy en routers
- `db.commit()` en routers (solo en repositories)
- `SELECT *` sin filtros ni límites
- Exponer IDs internos sin validar permisos
- Retornar modelos SQLAlchemy directamente al cliente

## Decision Trees

### ¿Dónde va mi código?

| Código | Ubicación |
|--------|-----------|
| Recibir HTTP request | `routers/` |
| Validar permisos de usuario | `routers/` → `core/permissions.py` |
| Validar reglas de negocio | `services/` |
| Orquestar múltiples operaciones | `services/` |
| CRUD básico | `repositories/` |
| Queries complejas | `repositories/` |
| Definir estructura de tabla | `models/` |
| Definir estructura de request/response | `schemas/` |

### ¿Qué HTTP status code usar?

| Situación | Código |
|-----------|--------|
| GET exitoso | `200 OK` |
| POST crear recurso | `201 Created` |
| DELETE exitoso | `204 No Content` |
| Validación fallida | `400 Bad Request` |
| No autenticado | `401 Unauthorized` |
| Sin permisos | `403 Forbidden` |
| Recurso no existe | `404 Not Found` |
| Conflicto (duplicado) | `409 Conflict` |
| Error interno | `500 Internal Server Error` |

## Code Examples

### Router (Presentación)

```python
# routers/usuarios.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.core.permissions import require_admin
from app.schemas.usuario import UsuarioCreate, UsuarioResponse, UsuarioUpdate
from app.services.usuario_service import UsuarioService
from app.models.usuario import Usuario

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/", response_model=list[UsuarioResponse])
def listar_usuarios(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista todos los usuarios activos."""
    require_admin(current_user)
    service = UsuarioService(db)
    return service.listar_todos()


@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    data: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Crea un nuevo usuario."""
    require_admin(current_user)
    service = UsuarioService(db)
    return service.crear(data)


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Obtiene un usuario por ID."""
    require_admin(current_user)
    service = UsuarioService(db)
    usuario = service.obtener_por_id(usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return usuario
```

### Service (Lógica de Negocio)

```python
# services/usuario_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.models.usuario import Usuario
from app.core.security import hash_password


class UsuarioService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UsuarioRepository(db)

    def listar_todos(self) -> list[Usuario]:
        return self.repo.get_all_active()

    def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        return self.repo.get_by_id(usuario_id)

    def crear(self, data: UsuarioCreate) -> Usuario:
        # Validar que el username no existe
        if self.repo.get_by_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El username ya está en uso"
            )

        # Validar que el email no existe
        if self.repo.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya está en uso"
            )

        # Crear usuario con password hasheado
        usuario = Usuario(
            username=data.username,
            email=data.email,
            nombre=data.nombre,
            apellido=data.apellido,
            rol=data.rol,
            password_hash=hash_password(data.password),
            debe_cambiar_password=True,
        )

        return self.repo.create(usuario)

    def actualizar(self, usuario_id: int, data: UsuarioUpdate) -> Usuario:
        usuario = self.repo.get_by_id(usuario_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Actualizar solo campos proporcionados
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(usuario, field, value)

        return self.repo.update(usuario)
```

### Repository (Acceso a Datos)

```python
# repositories/usuario_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional

from app.models.usuario import Usuario
from app.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, db: Session):
        super().__init__(Usuario, db)

    def get_by_username(self, username: str) -> Optional[Usuario]:
        return self.db.query(Usuario).filter(
            and_(
                Usuario.username == username,
                Usuario.deleted_at.is_(None)
            )
        ).first()

    def get_by_email(self, email: str) -> Optional[Usuario]:
        return self.db.query(Usuario).filter(
            and_(
                Usuario.email == email,
                Usuario.deleted_at.is_(None)
            )
        ).first()

    def get_all_active(self) -> list[Usuario]:
        return self.db.query(Usuario).filter(
            Usuario.deleted_at.is_(None)
        ).order_by(Usuario.apellido, Usuario.nombre).all()

    def get_tutores_by_comision(self, comision_id: int) -> list[Usuario]:
        return self.db.query(Usuario).join(
            ComisionTutor
        ).filter(
            and_(
                ComisionTutor.comision_id == comision_id,
                Usuario.deleted_at.is_(None)
            )
        ).all()
```

### Base Repository

```python
# repositories/base.py
from typing import TypeVar, Generic, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, model: type[T], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: int) -> Optional[T]:
        return self.db.query(self.model).filter(
            self.model.id == id,
            self.model.deleted_at.is_(None)
        ).first()

    def get_all(self) -> List[T]:
        return self.db.query(self.model).filter(
            self.model.deleted_at.is_(None)
        ).all()

    def create(self, entity: T) -> T:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: T) -> T:
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def soft_delete(self, entity: T) -> T:
        entity.deleted_at = datetime.utcnow()
        self.db.commit()
        return entity
```

### Model (SQLAlchemy)

```python
# models/usuario.py
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class RolEnum(str, enum.Enum):
    ADMIN = "admin"
    COORDINADOR = "coordinador"
    TUTOR = "tutor"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    rol = Column(Enum(RolEnum), nullable=False)
    debe_cambiar_password = Column(Boolean, default=True)
    api_key_encrypted = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    coordinaciones = relationship("CoordinadorMateria", back_populates="coordinador")
    tutorias = relationship("ComisionTutor", back_populates="tutor")
```

### Schema (Pydantic)

```python
# schemas/usuario.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime

from app.models.usuario import RolEnum


class UsuarioBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    rol: RolEnum


class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=8)


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    apellido: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None


class UsuarioResponse(UsuarioBase):
    id: int
    debe_cambiar_password: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

### Dependencies

```python
# core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import SessionLocal
from app.config import settings
from app.models.usuario import Usuario

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario:
    token = credentials.credentials

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

    user = db.query(Usuario).filter(
        Usuario.id == user_id,
        Usuario.deleted_at.is_(None)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )

    return user
```

## Commands

```bash
# Crear migración
alembic revision --autogenerate -m "descripcion"

# Aplicar migraciones
alembic upgrade head

# Rollback última migración
alembic downgrade -1

# Ejecutar servidor desarrollo
uvicorn app.main:app --reload --port 8000

# Ejecutar tests
pytest

# Linting
ruff check app/

# Type checking
mypy app/
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
