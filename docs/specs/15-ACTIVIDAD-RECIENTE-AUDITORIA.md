# 15. Sistema de Actividad Reciente y Auditoría

**Versión:** 1.0
**Fecha:** 2026-02-12
**Autor:** Claude Code
**Referencias:**
- `docs/specs/07-DISENO-UI-UX.md` Section 4.1 - Dashboard Admin
- `docs/specs/06-MODELO-DATOS.md` - Modelo de datos

---

## 1. Objetivo

Implementar un sistema de auditoría que registre las acciones importantes realizadas en el sistema y permita mostrarlas en el Dashboard de Admin como "Actividad Reciente" con datos reales.

### 1.1. Acciones a Registrar

Se registrarán las siguientes acciones:
- **Creación de Usuarios** (Admin, Coordinador, Tutor - NO Estudiantes)
- **Creación de Materias**
- **Creación de Comisiones**
- **Creación de Rúbricas**

### 1.2. Contexto

Independientemente de si la acción fue realizada por un Admin o un Coordinador (en los casos donde ambos puedan crear entidades), todas las acciones deben quedar registradas.

---

## 2. Modelo de Datos

### 2.1. Nueva Tabla: `actividades`

```python
# backend/app/models/actividad.py

from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum

from app.models.base import Base, TimestampMixin


class TipoActividadEnum(str, enum.Enum):
    """Tipos de actividad que se registran en el sistema."""
    USUARIO_CREADO = "USUARIO_CREADO"
    MATERIA_CREADA = "MATERIA_CREADA"
    COMISION_CREADA = "COMISION_CREADA"
    RUBRICA_CREADA = "RUBRICA_CREADA"


class Actividad(Base, TimestampMixin):
    """
    Registro de actividades/auditoría del sistema.

    Registra acciones importantes como creación de usuarios, materias,
    comisiones y rúbricas para mostrar en el Dashboard Admin.

    Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
    """
    __tablename__ = "actividades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Tipo de actividad
    tipo: Mapped[TipoActividadEnum] = mapped_column(
        SQLEnum(TipoActividadEnum),
        nullable=False,
        index=True
    )

    # Usuario que realizó la acción
    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True  # Puede ser NULL si el usuario se elimina
    )

    # Descripción de la actividad (ej: "Usuario 'Juan Pérez' creado")
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)

    # ID de la entidad afectada (ej: id del usuario creado)
    entidad_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Nombre de la entidad afectada (ej: nombre del usuario, materia, etc.)
    entidad_nombre: Mapped[str] = mapped_column(String(255), nullable=False)

    # Datos adicionales en formato JSON (opcional)
    metadatos: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relaciones
    usuario = relationship("Usuario", back_populates="actividades_realizadas")
```

### 2.2. Actualización en Usuario Model

```python
# backend/app/models/usuario.py
# Agregar relación:

actividades_realizadas = relationship(
    "Actividad",
    back_populates="usuario",
    cascade="all, delete-orphan"
)
```

### 2.3. Migración Alembic

Crear migración con:
```bash
cd backend
alembic revision --autogenerate -m "add actividades table for audit log"
alembic upgrade head
```

---

## 3. Backend Implementation

### 3.1. Schemas

```python
# backend/app/schemas/actividad.py

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from app.models.actividad import TipoActividadEnum


class ActividadBase(BaseModel):
    """Base schema para Actividad."""
    tipo: TipoActividadEnum
    descripcion: str = Field(..., max_length=500)
    entidad_id: int
    entidad_nombre: str = Field(..., max_length=255)


class ActividadCreate(ActividadBase):
    """Schema para crear una actividad."""
    usuario_id: int | None = None
    metadatos: str | None = None


class ActividadResponse(ActividadBase):
    """Schema para respuesta de actividad."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    created_at: datetime

    # Datos del usuario que realizó la acción (opcional)
    usuario_nombre: str | None = None
    usuario_rol: str | None = None


class ActividadListResponse(BaseModel):
    """Schema para lista de actividades."""
    items: list[ActividadResponse]
    total: int
```

### 3.2. Repository

```python
# backend/app/repositories/actividad_repository.py

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.actividad import Actividad, TipoActividadEnum
from app.schemas.actividad import ActividadCreate


class ActividadRepository:
    """Repository para gestionar actividades/auditoría."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, actividad: ActividadCreate) -> Actividad:
        """Crea un nuevo registro de actividad."""
        db_actividad = Actividad(**actividad.model_dump())
        self.db.add(db_actividad)
        await self.db.commit()
        await self.db.refresh(db_actividad)
        return db_actividad

    async def get_recent(
        self,
        limit: int = 10,
        offset: int = 0,
        tipo: TipoActividadEnum | None = None
    ) -> tuple[list[Actividad], int]:
        """
        Obtiene las actividades más recientes.

        Args:
            limit: Número máximo de resultados
            offset: Offset para paginación
            tipo: Filtrar por tipo de actividad (opcional)

        Returns:
            Tupla con (lista de actividades, total)
        """
        # Query base
        query = select(Actividad).options(joinedload(Actividad.usuario))

        # Filtrar por tipo si se especifica
        if tipo:
            query = query.where(Actividad.tipo == tipo)

        # Ordenar por fecha de creación descendente
        query = query.order_by(Actividad.created_at.desc())

        # Contar total
        count_query = select(func.count()).select_from(Actividad)
        if tipo:
            count_query = count_query.where(Actividad.tipo == tipo)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Aplicar paginación
        query = query.limit(limit).offset(offset)

        # Ejecutar query
        result = await self.db.execute(query)
        actividades = result.scalars().all()

        return list(actividades), total
```

### 3.3. Service

```python
# backend/app/services/actividad_service.py

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.actividad_repository import ActividadRepository
from app.schemas.actividad import (
    ActividadCreate,
    ActividadResponse,
    ActividadListResponse
)
from app.models.actividad import TipoActividadEnum


class ActividadService:
    """Service para gestionar actividades/auditoría."""

    def __init__(self, db: AsyncSession):
        self.repository = ActividadRepository(db)

    async def registrar_actividad(
        self,
        tipo: TipoActividadEnum,
        descripcion: str,
        entidad_id: int,
        entidad_nombre: str,
        usuario_id: int | None = None,
        metadatos: str | None = None
    ) -> None:
        """
        Registra una nueva actividad en el sistema.

        Este método se llamará desde otros servicios al crear entidades.
        """
        actividad = ActividadCreate(
            tipo=tipo,
            descripcion=descripcion,
            entidad_id=entidad_id,
            entidad_nombre=entidad_nombre,
            usuario_id=usuario_id,
            metadatos=metadatos
        )
        await self.repository.create(actividad)

    async def get_actividades_recientes(
        self,
        limit: int = 10,
        offset: int = 0,
        tipo: TipoActividadEnum | None = None
    ) -> ActividadListResponse:
        """Obtiene las actividades más recientes."""
        actividades, total = await self.repository.get_recent(
            limit=limit,
            offset=offset,
            tipo=tipo
        )

        # Mapear a response schema
        items = []
        for act in actividades:
            item = ActividadResponse(
                id=act.id,
                tipo=act.tipo,
                descripcion=act.descripcion,
                entidad_id=act.entidad_id,
                entidad_nombre=act.entidad_nombre,
                usuario_id=act.usuario_id,
                created_at=act.created_at,
                usuario_nombre=(
                    f"{act.usuario.nombre} {act.usuario.apellido}"
                    if act.usuario else None
                ),
                usuario_rol=act.usuario.rol.value if act.usuario else None
            )
            items.append(item)

        return ActividadListResponse(items=items, total=total)
```

### 3.4. Router

```python
# backend/app/routers/actividades.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_async_session
from app.models.usuario import Usuario
from app.models.enums import RolEnum
from app.services.actividad_service import ActividadService
from app.schemas.actividad import ActividadListResponse
from app.models.actividad import TipoActividadEnum
from app.dependencies.auth import get_current_user, require_roles


router = APIRouter(prefix="/actividades", tags=["actividades"])


@router.get(
    "/recientes",
    response_model=ActividadListResponse,
    summary="Obtener actividades recientes"
)
async def get_actividades_recientes(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    tipo: TipoActividadEnum | None = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: Usuario = Depends(
        require_roles([RolEnum.ADMIN])  # Solo admin puede ver actividades
    )
):
    """
    Obtiene las actividades más recientes del sistema.

    Solo accesible para usuarios con rol ADMIN.
    """
    service = ActividadService(db)
    return await service.get_actividades_recientes(
        limit=limit,
        offset=offset,
        tipo=tipo
    )
```

### 3.5. Integración en Servicios Existentes

Actualizar los servicios de Usuario, Materia, Comision y Rubrica para registrar actividades al crear entidades:

#### a) UsuarioService

```python
# backend/app/services/usuario_service.py

async def create_usuario(self, usuario_create: UsuarioCreate) -> UsuarioResponse:
    """Crea un nuevo usuario."""
    # ... código existente de creación ...

    # Registrar actividad solo si NO es estudiante
    if new_usuario.rol != RolEnum.ESTUDIANTE:
        actividad_service = ActividadService(self.repository.db)
        await actividad_service.registrar_actividad(
            tipo=TipoActividadEnum.USUARIO_CREADO,
            descripcion=f"Usuario '{new_usuario.nombre} {new_usuario.apellido}' ({new_usuario.rol.value}) creado",
            entidad_id=new_usuario.id,
            entidad_nombre=f"{new_usuario.nombre} {new_usuario.apellido}",
            usuario_id=current_user_id  # Pasar el ID del usuario que lo creó
        )

    return UsuarioResponse.model_validate(new_usuario)
```

#### b) MateriaService

```python
# backend/app/services/materia_service.py

async def create_materia(self, materia_create: MateriaCreate, current_user_id: int) -> MateriaResponse:
    """Crea una nueva materia."""
    # ... código existente de creación ...

    # Registrar actividad
    actividad_service = ActividadService(self.repository.db)
    await actividad_service.registrar_actividad(
        tipo=TipoActividadEnum.MATERIA_CREADA,
        descripcion=f"Materia '{new_materia.nombre}' creada",
        entidad_id=new_materia.id,
        entidad_nombre=new_materia.nombre,
        usuario_id=current_user_id
    )

    return MateriaResponse.model_validate(new_materia)
```

#### c) ComisionService

```python
# backend/app/services/comision_service.py

async def create_comision(self, comision_create: ComisionCreate, current_user_id: int) -> ComisionResponse:
    """Crea una nueva comisión."""
    # ... código existente de creación ...

    # Registrar actividad
    actividad_service = ActividadService(self.repository.db)
    await actividad_service.registrar_actividad(
        tipo=TipoActividadEnum.COMISION_CREADA,
        descripcion=f"Comisión '{new_comision.nombre}' creada",
        entidad_id=new_comision.id,
        entidad_nombre=new_comision.nombre,
        usuario_id=current_user_id
    )

    return ComisionResponse.model_validate(new_comision)
```

#### d) RubricaService

```python
# backend/app/services/rubrica_service.py

async def create_rubrica(self, rubrica_create: RubricaCreate, current_user_id: int) -> RubricaResponse:
    """Crea una nueva rúbrica."""
    # ... código existente de creación ...

    # Registrar actividad
    actividad_service = ActividadService(self.repository.db)
    await actividad_service.registrar_actividad(
        tipo=TipoActividadEnum.RUBRICA_CREADA,
        descripcion=f"Rúbrica '{new_rubrica.nombre}' (tipo: {new_rubrica.tipo.value}) creada",
        entidad_id=new_rubrica.id,
        entidad_nombre=new_rubrica.nombre,
        usuario_id=current_user_id
    )

    return RubricaResponse.model_validate(new_rubrica)
```

### 3.6. Registrar Router en Main

```python
# backend/app/main.py

from app.routers import actividades

app.include_router(actividades.router, prefix="/api")
```

---

## 4. Frontend Implementation

### 4.1. Types

```typescript
// frontend/src/shared/types/actividad.ts

export enum TipoActividad {
  USUARIO_CREADO = 'USUARIO_CREADO',
  MATERIA_CREADA = 'MATERIA_CREADA',
  COMISION_CREADA = 'COMISION_CREADA',
  RUBRICA_CREADA = 'RUBRICA_CREADA',
}

export interface Actividad {
  id: number;
  tipo: TipoActividad;
  descripcion: string;
  entidad_id: number;
  entidad_nombre: string;
  usuario_id: number | null;
  created_at: string;
  usuario_nombre: string | null;
  usuario_rol: string | null;
}

export interface ActividadListResponse {
  items: Actividad[];
  total: number;
}
```

### 4.2. API Service

```typescript
// frontend/src/shared/api/actividadesApi.ts

import { apiClient } from './client';
import type { ActividadListResponse, TipoActividad } from '@/shared/types/actividad';

export const actividadesApi = {
  /**
   * Obtiene las actividades recientes del sistema
   */
  getRecientes: async (params?: {
    limit?: number;
    offset?: number;
    tipo?: TipoActividad;
  }): Promise<ActividadListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());
    if (params?.tipo) searchParams.append('tipo', params.tipo);

    const response = await apiClient.get<ActividadListResponse>(
      `/actividades/recientes?${searchParams}`
    );
    return response.data;
  },
};
```

### 4.3. React Query Hook

```typescript
// frontend/src/features/dashboard/hooks/useActividades.ts

import { useQuery } from '@tanstack/react-query';
import { actividadesApi } from '@/shared/api/actividadesApi';
import type { TipoActividad } from '@/shared/types/actividad';

export function useActividadesRecientes(params?: {
  limit?: number;
  offset?: number;
  tipo?: TipoActividad;
}) {
  return useQuery({
    queryKey: ['actividades', 'recientes', params],
    queryFn: () => actividadesApi.getRecientes(params),
    staleTime: 30000, // 30 segundos
  });
}
```

### 4.4. Actualizar DashboardAdmin Component

```typescript
// frontend/src/features/dashboard/components/DashboardAdmin.tsx

import { useActividadesRecientes } from '../hooks/useActividades';

export function DashboardAdmin() {
  const navigate = useNavigate();
  const { data: stats, isLoading: statsLoading, error: statsError } = useDashboardAdminStats();
  const { data: actividadesData, isLoading: actividadesLoading } = useActividadesRecientes({
    limit: 10
  });

  // Loading state
  if (statsLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  // Error state
  if (statsError) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Error al cargar estadísticas del dashboard</p>
        <p className="text-sm text-muted-foreground mt-2">
          {statsError instanceof Error ? statsError.message : 'Error desconocido'}
        </p>
      </div>
    );
  }

  // No data state
  if (!stats) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No hay datos disponibles</p>
      </div>
    );
  }

  const quickActions = [
    {
      label: 'Crear Materia',
      icon: Plus,
      onClick: () => navigate('/materias'),
    },
    {
      label: 'Crear Usuario',
      icon: Plus,
      onClick: () => navigate('/usuarios'),
    },
    {
      label: 'Crear Comisión',
      icon: Plus,
      onClick: () => navigate('/comisiones'),
    },
    {
      label: 'Crear Rúbrica',
      icon: Plus,
      onClick: () => navigate('/rubricas'),
    },
  ];

  // Mapear actividades a formato esperado por RecentActivity
  const recentActivities = actividadesData?.items.map(act => ({
    id: act.id,
    text: act.descripcion,
    timestamp: act.created_at,
  })) ?? [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard Administrativo</h1>
        <p className="text-sm text-muted-foreground">
          Vista general del sistema Active-IA
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Materias"
          value={stats.materias}
          subtitle="activas"
          icon={BookOpen}
          variant="default"
        />
        <StatCard
          title="Comisiones"
          value={stats.comisiones}
          subtitle="activas"
          icon={GraduationCap}
          variant="default"
        />
        <StatCard
          title="Usuarios"
          value={stats.usuarios}
          subtitle="activos"
          icon={Users}
          variant="default"
        />
        <StatCard
          title="Rúbricas"
          value={stats.rubricas}
          subtitle="activas"
          icon={FileText}
          variant="default"
        />
      </div>

      {/* Quick Actions & Recent Activity */}
      <div className="grid gap-6 lg:grid-cols-2">
        <QuickActions actions={quickActions} />
        <RecentActivity
          activities={recentActivities}
          isLoading={actividadesLoading}
        />
      </div>
    </div>
  );
}
```

### 4.5. Actualizar RecentActivity Component

```typescript
// frontend/src/features/dashboard/components/RecentActivity.tsx

import { Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';
import { Spinner } from '@/shared/components/ui';

interface Activity {
  id: number;
  text: string;
  timestamp: string;
}

interface RecentActivityProps {
  activities: Activity[];
  isLoading?: boolean;
}

export function RecentActivity({ activities, isLoading = false }: RecentActivityProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h2 className="text-lg font-semibold text-foreground mb-4">
        Actividad Reciente
      </h2>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spinner size="md" />
        </div>
      ) : activities.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No hay actividades registradas
        </div>
      ) : (
        <div className="space-y-4">
          {activities.map((activity) => (
            <div
              key={activity.id}
              className="flex items-start gap-3 pb-4 border-b border-border last:border-0 last:pb-0"
            >
              <div className="rounded-full bg-primary/10 p-2 mt-0.5">
                <Clock className="h-4 w-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-foreground">{activity.text}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatDistanceToNow(new Date(activity.timestamp), {
                    addSuffix: true,
                    locale: es,
                  })}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 5. Plan de Implementación

### Fase 1: Backend - Modelo y Migración
1. Crear `backend/app/models/actividad.py` con el modelo y enum
2. Actualizar `backend/app/models/__init__.py` para exportar Actividad
3. Actualizar `backend/app/models/usuario.py` con relación `actividades_realizadas`
4. Crear migración Alembic
5. Ejecutar migración

### Fase 2: Backend - Schemas, Repository y Service
1. Crear `backend/app/schemas/actividad.py`
2. Crear `backend/app/repositories/actividad_repository.py`
3. Crear `backend/app/services/actividad_service.py`
4. Crear `backend/app/routers/actividades.py`
5. Registrar router en `main.py`

### Fase 3: Backend - Integración con Servicios Existentes
1. Actualizar `usuario_service.py` - método `create_usuario`
2. Actualizar `materia_service.py` - método `create_materia`
3. Actualizar `comision_service.py` - método `create_comision`
4. Actualizar `rubrica_service.py` - método `create_rubrica`

### Fase 4: Frontend - Types y API
1. Crear `frontend/src/shared/types/actividad.ts`
2. Actualizar `frontend/src/shared/types/index.ts` para exportar types
3. Crear `frontend/src/shared/api/actividadesApi.ts`

### Fase 5: Frontend - Hooks y Components
1. Crear `frontend/src/features/dashboard/hooks/useActividades.ts`
2. Actualizar `frontend/src/features/dashboard/components/RecentActivity.tsx`
3. Actualizar `frontend/src/features/dashboard/components/DashboardAdmin.tsx`

### Fase 6: Testing
1. Crear usuarios, materias, comisiones y rúbricas
2. Verificar que se registren en la tabla `actividades`
3. Verificar que aparezcan en el Dashboard Admin
4. Verificar formato de fechas y descripción

---

## 6. Consideraciones

### 6.1. Performance
- Índice en `tipo` para filtrado rápido
- Índice en `created_at` para ordenamiento
- Límite de 10 actividades por defecto en el dashboard
- Paginación disponible para más actividades

### 6.2. Seguridad
- Solo usuarios ADMIN pueden ver actividades
- No se exponen datos sensibles en las descripciones
- El `usuario_id` usa `SET NULL` en caso de eliminación

### 6.3. Extensibilidad
- El modelo permite agregar más tipos de actividad fácilmente
- Campo `metadatos` para información adicional en formato JSON
- Sistema de paginación permite consultar histórico completo

### 6.4. Mantenimiento
- No se implementa auto-limpieza de actividades antiguas en esta versión
- Se puede agregar más adelante un job que archive/elimine actividades antiguas (> 90 días)

---

## 7. Referencias

- FastAPI Docs: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0 Docs: https://docs.sqlalchemy.org/en/20/
- React Query: https://tanstack.com/query/latest/docs/react/overview
- date-fns: https://date-fns.org/
