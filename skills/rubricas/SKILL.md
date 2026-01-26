---
name: rubricas
description: >
  Gestión de rúbricas y criterios de evaluación para corrección de trabajos prácticos.
  Trigger: Cuando trabajes con rúbricas, criterios de evaluación, tipos de evaluación,
  o generación de rúbricas desde PDF.
metadata:
  author: Active-IA Team
  version: "1.0"
  scope: [root, backend]
  auto_invoke:
    - "Managing rubrics/criteria"
    - "Creating evaluation criteria"
    - "Generating rubrics from PDF"
    - "Duplicating rubrics"
---

# Rúbricas Skill

## When to Use

- Creando o editando rúbricas de evaluación
- Definiendo criterios y puntajes
- Generando rúbricas desde PDF de consigna
- Duplicando rúbricas de años anteriores
- Validando estructura de criterios

## Domain Concepts

### Jerarquía

```
MATERIA
└── RÚBRICAS (por tipo y año académico)
    └── CRITERIOS (nombre, descripción, puntaje máximo)
```

### Tipos de Rúbrica

| Tipo | Descripción |
|------|-------------|
| `TP` | Trabajo Práctico |
| `PARCIAL_1` | Primer Parcial |
| `PARCIAL_2` | Segundo Parcial |
| `RECUP_1` | Recuperatorio del Primer Parcial |
| `RECUP_2` | Recuperatorio del Segundo Parcial |
| `FINAL` | Examen Final |
| `GLOBAL` | Rúbrica general de la materia |

### Scope de Rúbricas

- Las rúbricas pertenecen a una **materia**
- Todas las comisiones de la materia (del mismo año) comparten las rúbricas
- El año académico permite tener rúbricas diferentes por año

## Critical Patterns

### ALWAYS
- Validar que la suma de puntajes máximos = 100
- Generar UUID único para cada criterio
- Almacenar criterios como JSONB (flexible)
- Validar que la materia existe antes de crear rúbrica
- Permitir solo un tipo de rúbrica por materia/año (excepto TP)
- Soft delete al eliminar rúbricas

### NEVER
- Permitir criterios sin descripción
- Crear rúbricas duplicadas (mismo tipo, materia, año)
- Eliminar rúbricas que tengan correcciones asociadas
- Modificar rúbricas que ya tienen correcciones (crear nueva versión)
- Puntajes negativos o mayores a 100

## Data Model

### Rubrica Model

```python
# models/rubrica.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class TipoRubrica(str, enum.Enum):
    TP = "TP"
    PARCIAL_1 = "PARCIAL_1"
    PARCIAL_2 = "PARCIAL_2"
    RECUP_1 = "RECUP_1"
    RECUP_2 = "RECUP_2"
    FINAL = "FINAL"
    GLOBAL = "GLOBAL"


class Rubrica(Base):
    __tablename__ = "rubricas"

    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    tipo = Column(String(20), nullable=False)  # TipoRubrica
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    criterios = Column(JSONB, nullable=False, default=list)
    anio_academico = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    materia = relationship("Materia", back_populates="rubricas")


# Estructura de criterios (JSONB):
# [
#   {
#     "id": "550e8400-e29b-41d4-a716-446655440000",
#     "nombre": "Funcionalidad",
#     "descripcion": "El código cumple con todos los requisitos funcionales",
#     "puntaje_maximo": 30
#   },
#   {
#     "id": "550e8400-e29b-41d4-a716-446655440001",
#     "nombre": "Buenas prácticas",
#     "descripcion": "Uso de nombres descriptivos, modularización, etc.",
#     "puntaje_maximo": 25
#   },
#   ...
# ]
```

### Schemas

```python
# schemas/rubrica.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import uuid


class CriterioBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str = Field(..., min_length=10, max_length=500)
    puntaje_maximo: int = Field(..., ge=1, le=100)


class CriterioCreate(CriterioBase):
    pass


class CriterioResponse(CriterioBase):
    id: str


class RubricaCreate(BaseModel):
    materia_id: int
    tipo: str = Field(..., pattern="^(TP|PARCIAL_1|PARCIAL_2|RECUP_1|RECUP_2|FINAL|GLOBAL)$")
    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = Field(None, max_length=1000)
    criterios: list[CriterioCreate] = Field(..., min_length=1, max_length=20)
    anio_academico: int = Field(..., ge=2020, le=2100)

    @field_validator('criterios')
    @classmethod
    def validate_total_puntaje(cls, criterios: list[CriterioCreate]):
        total = sum(c.puntaje_maximo for c in criterios)
        if total != 100:
            raise ValueError(f"La suma de puntajes debe ser 100, es {total}")
        return criterios


class RubricaUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = Field(None, max_length=1000)
    criterios: Optional[list[CriterioCreate]] = None

    @field_validator('criterios')
    @classmethod
    def validate_total_puntaje(cls, criterios: list[CriterioCreate] | None):
        if criterios is None:
            return criterios
        total = sum(c.puntaje_maximo for c in criterios)
        if total != 100:
            raise ValueError(f"La suma de puntajes debe ser 100, es {total}")
        return criterios


class RubricaResponse(BaseModel):
    id: int
    materia_id: int
    tipo: str
    nombre: str
    descripcion: Optional[str]
    criterios: list[CriterioResponse]
    anio_academico: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DuplicarRubricaRequest(BaseModel):
    rubrica_origen_id: int
    anio_destino: int = Field(..., ge=2020, le=2100)
    nuevo_nombre: Optional[str] = None
```

## Service Implementation

```python
# services/rubrica_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import uuid

from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.correccion_repository import CorreccionRepository
from app.schemas.rubrica import RubricaCreate, RubricaUpdate, DuplicarRubricaRequest
from app.models.rubrica import Rubrica


class RubricaService:
    def __init__(self, db: Session):
        self.db = db
        self.rubrica_repo = RubricaRepository(db)
        self.materia_repo = MateriaRepository(db)
        self.correccion_repo = CorreccionRepository(db)

    def crear(self, data: RubricaCreate) -> Rubrica:
        # Validar que la materia existe
        materia = self.materia_repo.get_by_id(data.materia_id)
        if not materia:
            raise HTTPException(404, "Materia no encontrada")

        # Validar duplicados (excepto TP que puede haber varios)
        if data.tipo != "TP":
            existente = self.rubrica_repo.get_by_materia_tipo_anio(
                data.materia_id, data.tipo, data.anio_academico
            )
            if existente:
                raise HTTPException(
                    409,
                    f"Ya existe una rúbrica de tipo {data.tipo} para esta materia y año"
                )

        # Generar UUIDs para criterios
        criterios_con_id = [
            {
                "id": str(uuid.uuid4()),
                "nombre": c.nombre,
                "descripcion": c.descripcion,
                "puntaje_maximo": c.puntaje_maximo,
            }
            for c in data.criterios
        ]

        rubrica = Rubrica(
            materia_id=data.materia_id,
            tipo=data.tipo,
            nombre=data.nombre,
            descripcion=data.descripcion,
            criterios=criterios_con_id,
            anio_academico=data.anio_academico,
        )

        return self.rubrica_repo.create(rubrica)

    def actualizar(self, rubrica_id: int, data: RubricaUpdate) -> Rubrica:
        rubrica = self.rubrica_repo.get_by_id(rubrica_id)
        if not rubrica:
            raise HTTPException(404, "Rúbrica no encontrada")

        # Verificar si tiene correcciones asociadas
        if data.criterios and self._tiene_correcciones(rubrica_id):
            raise HTTPException(
                400,
                "No se pueden modificar los criterios de una rúbrica con correcciones. "
                "Crea una nueva versión."
            )

        # Actualizar campos
        if data.nombre is not None:
            rubrica.nombre = data.nombre
        if data.descripcion is not None:
            rubrica.descripcion = data.descripcion
        if data.criterios is not None:
            # Generar nuevos UUIDs para criterios modificados
            rubrica.criterios = [
                {
                    "id": str(uuid.uuid4()),
                    "nombre": c.nombre,
                    "descripcion": c.descripcion,
                    "puntaje_maximo": c.puntaje_maximo,
                }
                for c in data.criterios
            ]

        return self.rubrica_repo.update(rubrica)

    def duplicar(self, data: DuplicarRubricaRequest) -> Rubrica:
        """Duplica una rúbrica para un nuevo año académico."""
        origen = self.rubrica_repo.get_by_id(data.rubrica_origen_id)
        if not origen:
            raise HTTPException(404, "Rúbrica origen no encontrada")

        # Verificar que no existe para el año destino
        if origen.tipo != "TP":
            existente = self.rubrica_repo.get_by_materia_tipo_anio(
                origen.materia_id, origen.tipo, data.anio_destino
            )
            if existente:
                raise HTTPException(
                    409,
                    f"Ya existe una rúbrica de tipo {origen.tipo} para el año {data.anio_destino}"
                )

        # Crear copia con nuevos IDs de criterios
        nuevos_criterios = [
            {
                "id": str(uuid.uuid4()),
                "nombre": c["nombre"],
                "descripcion": c["descripcion"],
                "puntaje_maximo": c["puntaje_maximo"],
            }
            for c in origen.criterios
        ]

        nueva_rubrica = Rubrica(
            materia_id=origen.materia_id,
            tipo=origen.tipo,
            nombre=data.nuevo_nombre or f"{origen.nombre} ({data.anio_destino})",
            descripcion=origen.descripcion,
            criterios=nuevos_criterios,
            anio_academico=data.anio_destino,
        )

        return self.rubrica_repo.create(nueva_rubrica)

    def _tiene_correcciones(self, rubrica_id: int) -> bool:
        """Verifica si la rúbrica tiene correcciones asociadas."""
        # Las correcciones referencian a entregas, y las entregas a comisiones
        # que usan las rúbricas de la materia
        return self.correccion_repo.count_by_rubrica(rubrica_id) > 0
```

## Generación de Rúbrica desde PDF

```python
# services/rubrica_service.py (continuación)

async def generar_desde_pdf(
    self,
    materia_id: int,
    tipo: str,
    anio_academico: int,
    pdf_content: bytes,
    api_key_encrypted: str,
) -> Rubrica:
    """Genera una rúbrica a partir de un PDF de consigna usando IA."""

    # Validar materia
    materia = self.materia_repo.get_by_id(materia_id)
    if not materia:
        raise HTTPException(404, "Materia no encontrada")

    # Preparar payload para N8N
    api_key = decrypt_api_key(api_key_encrypted)
    payload = {
        "api_key": api_key,
        "model": "gemini-2.0-flash",
        "pdf_base64": base64.b64encode(pdf_content).decode(),
        "instrucciones": self._get_rubric_generation_prompt(),
    }

    # Llamar a N8N
    n8n_client = N8NClient()
    try:
        result = await n8n_client.trigger_rubric_generation(payload)
    except N8NError as e:
        raise HTTPException(502, f"Error generando rúbrica: {e}")

    # Parsear respuesta
    criterios_data = self._parse_rubric_response(result)

    # Crear rúbrica
    rubrica = Rubrica(
        materia_id=materia_id,
        tipo=tipo,
        nombre=f"{materia.nombre} - {tipo} ({anio_academico})",
        descripcion="Generada automáticamente desde PDF",
        criterios=criterios_data,
        anio_academico=anio_academico,
    )

    return self.rubrica_repo.create(rubrica)


def _get_rubric_generation_prompt(self) -> str:
    return """
Analiza el PDF de consigna y genera una rúbrica de evaluación.

INSTRUCCIONES:
1. Identifica los requisitos y criterios evaluables
2. Agrupa en 4-8 criterios principales
3. Asigna puntajes proporcionales a la importancia
4. La suma de puntajes debe ser exactamente 100

FORMATO DE RESPUESTA (JSON estricto):
{
  "criterios": [
    {
      "nombre": "<nombre corto del criterio>",
      "descripcion": "<qué se evalúa en detalle>",
      "puntaje_maximo": <número>
    }
  ]
}

CRITERIOS TÍPICOS A CONSIDERAR:
- Funcionalidad (cumple requisitos)
- Buenas prácticas de código
- Manejo de errores
- Documentación/comentarios
- Eficiencia/optimización
- Testing (si aplica)
- Interfaz de usuario (si aplica)
"""
```

## Repository Implementation

```python
# repositories/rubrica_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional

from app.models.rubrica import Rubrica
from app.repositories.base import BaseRepository


class RubricaRepository(BaseRepository[Rubrica]):
    def __init__(self, db: Session):
        super().__init__(Rubrica, db)

    def get_by_materia(self, materia_id: int) -> list[Rubrica]:
        return self.db.query(Rubrica).filter(
            and_(
                Rubrica.materia_id == materia_id,
                Rubrica.deleted_at.is_(None)
            )
        ).order_by(Rubrica.tipo, Rubrica.anio_academico.desc()).all()

    def get_by_materia_tipo_anio(
        self,
        materia_id: int,
        tipo: str,
        anio: int
    ) -> Optional[Rubrica]:
        return self.db.query(Rubrica).filter(
            and_(
                Rubrica.materia_id == materia_id,
                Rubrica.tipo == tipo,
                Rubrica.anio_academico == anio,
                Rubrica.deleted_at.is_(None)
            )
        ).first()

    def get_by_materia_anio(self, materia_id: int, anio: int) -> list[Rubrica]:
        return self.db.query(Rubrica).filter(
            and_(
                Rubrica.materia_id == materia_id,
                Rubrica.anio_academico == anio,
                Rubrica.deleted_at.is_(None)
            )
        ).order_by(Rubrica.tipo).all()
```

## API Endpoints

```python
# routers/rubricas.py

@router.post("/", response_model=RubricaResponse, status_code=status.HTTP_201_CREATED)
def crear_rubrica(
    data: RubricaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Crea una nueva rúbrica."""
    require_coordinador(current_user)
    service = RubricaService(db)
    return service.crear(data)


@router.post("/generar-desde-pdf", response_model=RubricaResponse)
async def generar_rubrica_desde_pdf(
    materia_id: int = Form(...),
    tipo: str = Form(...),
    anio_academico: int = Form(...),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Genera una rúbrica a partir de un PDF de consigna."""
    require_coordinador(current_user)

    if not current_user.api_key_encrypted:
        raise HTTPException(400, "Debes configurar tu API Key de Gemini")

    if not archivo.filename.endswith('.pdf'):
        raise HTTPException(400, "El archivo debe ser PDF")

    pdf_content = await archivo.read()
    service = RubricaService(db)

    return await service.generar_desde_pdf(
        materia_id=materia_id,
        tipo=tipo,
        anio_academico=anio_academico,
        pdf_content=pdf_content,
        api_key_encrypted=current_user.api_key_encrypted,
    )


@router.post("/duplicar", response_model=RubricaResponse)
def duplicar_rubrica(
    data: DuplicarRubricaRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Duplica una rúbrica para un nuevo año académico."""
    require_coordinador(current_user)
    service = RubricaService(db)
    return service.duplicar(data)
```

## Validation Examples

### Criterios Válidos

```json
{
  "criterios": [
    {
      "nombre": "Funcionalidad",
      "descripcion": "El código cumple con todos los requisitos funcionales especificados en la consigna",
      "puntaje_maximo": 35
    },
    {
      "nombre": "Buenas prácticas",
      "descripcion": "Uso de nombres descriptivos, modularización, principios SOLID básicos",
      "puntaje_maximo": 25
    },
    {
      "nombre": "Manejo de errores",
      "descripcion": "Validación de inputs, manejo de excepciones, mensajes de error claros",
      "puntaje_maximo": 20
    },
    {
      "nombre": "Documentación",
      "descripcion": "Comentarios útiles, README si aplica, código auto-documentado",
      "puntaje_maximo": 10
    },
    {
      "nombre": "Testing",
      "descripcion": "Tests unitarios básicos, cobertura de casos principales",
      "puntaje_maximo": 10
    }
  ]
}
```

Total: 35 + 25 + 20 + 10 + 10 = **100**

## Resources

- [Bloom's Taxonomy for Assessment](https://cft.vanderbilt.edu/guides-sub-pages/blooms-taxonomy/)
- [Rubric Best Practices](https://teaching.cornell.edu/teaching-resources/assessment-evaluation/using-rubrics)
