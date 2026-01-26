---
name: correccion-ia
description: >
  Flujo de corrección automática de trabajos prácticos con Google Gemini vía N8N.
  Trigger: Cuando trabajes con corrección de entregas, integración con IA, o el flujo
  de evaluación automática.
metadata:
  author: Active-IA Team
  version: "1.0"
  scope: [root, backend]
  auto_invoke:
    - "Implementing correction flow"
    - "Integrating with Gemini API"
    - "Processing AI evaluations"
    - "Handling N8N webhooks"
---

# Corrección IA Skill

## When to Use

- Implementando el flujo de corrección automática
- Integrando con N8N webhooks
- Procesando respuestas de Gemini
- Manejando errores de IA
- Optimizando prompts de evaluación

## Architecture Overview

```
┌─────────────┐     ┌─────────┐     ┌─────────────┐
│   Active-IA │────▶│   N8N   │────▶│   Gemini    │
│   Backend   │◀────│ Workflow│◀────│   API       │
└─────────────┘     └─────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│  PostgreSQL │
│  (Correccion)│
└─────────────┘
```

## Critical Patterns

### ALWAYS
- Validar API Key antes de enviar a N8N
- Incluir timeout en llamadas a N8N (90 segundos)
- Parsear respuesta JSON de Gemini con validación
- Guardar estado ERROR si falla la corrección
- Encriptar API Keys con AES-256
- Log de cada corrección (entrada y salida)
- Retry con backoff exponencial (max 3 intentos)

### NEVER
- Exponer API Key del usuario en logs
- Bloquear el servidor esperando corrección (usar background task)
- Asumir que la respuesta de Gemini es válida sin validar
- Guardar el código del alumno en logs (solo metadata)
- Enviar más de 1 corrección simultánea por usuario (rate limit)

## Decision Trees

### ¿Qué hacer si la corrección falla?

| Error | Acción |
|-------|--------|
| API Key inválida | Marcar entrega como ERROR, notificar usuario |
| Timeout N8N | Retry 1 vez, luego ERROR |
| Respuesta malformada | Intentar parseo parcial, si falla → ERROR |
| Rate limit Gemini | Queue con delay, retry en 60s |
| Error 500 N8N | Retry con backoff, max 3 intentos |

### ¿Cuándo re-corregir?

| Situación | Permitir re-corrección |
|-----------|------------------------|
| Corrección exitosa | Sí, descarta anterior |
| Corrección con ERROR | Sí |
| Corrección editada manualmente | Sí, con warning |
| Entrega sin código | No (validar antes) |

## Correction Flow

### 1. Preparación

```python
# services/correccion_service.py

class CorreccionService:
    def __init__(self, db: Session):
        self.db = db
        self.entrega_repo = EntregaRepository(db)
        self.correccion_repo = CorreccionRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        self.n8n_client = N8NClient()

    async def corregir(
        self,
        entrega_id: int,
        user_api_key_encrypted: str
    ) -> Correccion:
        # 1. Obtener entrega
        entrega = self.entrega_repo.get_by_id(entrega_id)
        if not entrega:
            raise HTTPException(404, "Entrega no encontrada")

        if not entrega.codigo_consolidado:
            raise HTTPException(400, "La entrega no tiene código")

        # 2. Obtener rúbrica
        rubrica = self._get_rubrica_for_entrega(entrega)
        if not rubrica:
            raise HTTPException(400, "No hay rúbrica configurada")

        # 3. Desencriptar API Key
        api_key = decrypt_api_key(user_api_key_encrypted)

        # 4. Preparar payload para N8N
        payload = self._build_correction_payload(entrega, rubrica, api_key)

        # 5. Enviar a N8N
        try:
            result = await self.n8n_client.trigger_correction(payload)
        except N8NTimeoutError:
            self._mark_as_error(entrega, "Timeout en corrección")
            raise HTTPException(502, "Timeout en servicio de IA")
        except N8NError as e:
            self._mark_as_error(entrega, str(e))
            raise HTTPException(502, f"Error en servicio de IA: {e}")

        # 6. Parsear y validar respuesta
        correccion_data = self._parse_gemini_response(result)

        # 7. Guardar corrección
        correccion = self._save_correccion(entrega, correccion_data)

        # 8. Actualizar estado de entrega
        entrega.estado = EstadoEntrega.CORREGIDA
        self.entrega_repo.update(entrega)

        return correccion
```

### 2. Payload para N8N

```python
def _build_correction_payload(
    self,
    entrega: Entrega,
    rubrica: Rubrica,
    api_key: str
) -> dict:
    return {
        "api_key": api_key,
        "model": "gemini-2.0-flash",
        "entrega": {
            "id": entrega.id,
            "alumno": entrega.alumno,
            "codigo": entrega.codigo_consolidado,
        },
        "rubrica": {
            "nombre": rubrica.nombre,
            "tipo": rubrica.tipo,
            "criterios": rubrica.criterios,  # JSONB
        },
        "instrucciones": self._get_system_prompt(),
    }

def _get_system_prompt(self) -> str:
    return """
Eres un evaluador de código para estudiantes universitarios de programación.
Tu tarea es evaluar el código según la rúbrica proporcionada.

INSTRUCCIONES:
1. Evalúa cada criterio de la rúbrica
2. Asigna un puntaje de 0 al máximo permitido por criterio
3. Proporciona feedback específico y constructivo
4. Identifica fortalezas del código
5. Sugiere mejoras concretas

FORMATO DE RESPUESTA (JSON estricto):
{
  "nota": <número 0-100>,
  "criterios": [
    {
      "id": "<id del criterio>",
      "puntaje_obtenido": <número>,
      "estado": "OK" | "WARNING" | "ERROR",
      "feedback": "<feedback específico>"
    }
  ],
  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>"],
  "recomendaciones": ["<recomendación 1>", "<recomendación 2>"],
  "comentario_general": "<comentario de cierre>"
}

REGLAS:
- La nota debe ser la suma de los puntajes de criterios
- El estado es OK si puntaje >= 70% del máximo, WARNING si >= 40%, ERROR si < 40%
- El feedback debe ser específico al código del alumno
- Las fortalezas deben destacar lo positivo
- Las recomendaciones deben ser accionables
"""
```

### 3. N8N Client

```python
# integrations/n8n_client.py
import httpx
from typing import Any

from app.config import settings
from app.core.exceptions import N8NError, N8NTimeoutError


class N8NClient:
    def __init__(self):
        self.base_url = settings.N8N_WEBHOOK_URL
        self.timeout = 90.0  # 90 segundos

    async def trigger_correction(self, payload: dict) -> dict[str, Any]:
        """Dispara el workflow de corrección en N8N."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/webhook/correccion",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout esperando respuesta de N8N")

            except httpx.HTTPStatusError as e:
                raise N8NError(f"Error HTTP {e.response.status_code}")

            except httpx.RequestError as e:
                raise N8NError(f"Error de conexión: {e}")

    async def trigger_rubric_generation(self, payload: dict) -> dict[str, Any]:
        """Dispara el workflow de generación de rúbrica desde PDF."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/webhook/generar-rubrica",
                    json=payload,
                    timeout=120.0,  # 2 minutos para PDFs
                )
                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout generando rúbrica")

            except httpx.HTTPStatusError as e:
                raise N8NError(f"Error HTTP {e.response.status_code}")
```

### 4. Parsear Respuesta

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Literal


class CriterioEvaluadoSchema(BaseModel):
    id: str
    puntaje_obtenido: int = Field(ge=0)
    estado: Literal["OK", "WARNING", "ERROR"]
    feedback: str = Field(min_length=1)


class CorreccionGeminiSchema(BaseModel):
    nota: int = Field(ge=0, le=100)
    criterios: list[CriterioEvaluadoSchema]
    fortalezas: list[str]
    recomendaciones: list[str]
    comentario_general: str


def _parse_gemini_response(self, response: dict) -> CorreccionGeminiSchema:
    """Parsea y valida la respuesta de Gemini."""
    try:
        # Extraer el JSON de la respuesta de N8N
        gemini_output = response.get("output", {})

        # Validar con Pydantic
        correccion = CorreccionGeminiSchema.model_validate(gemini_output)

        # Validar que la nota coincide con la suma de criterios
        suma_criterios = sum(c.puntaje_obtenido for c in correccion.criterios)
        if abs(correccion.nota - suma_criterios) > 1:  # Tolerancia de 1 punto
            correccion.nota = suma_criterios

        return correccion

    except ValidationError as e:
        # Intentar parseo parcial o fallback
        raise HTTPException(
            status_code=502,
            detail=f"Respuesta de IA malformada: {e}"
        )
```

### 5. Corrección en Lote

```python
async def corregir_lote(
    self,
    entrega_ids: list[int],
    user_api_key_encrypted: str
) -> list[Correccion]:
    """Corrige múltiples entregas secuencialmente."""
    resultados = []

    for entrega_id in entrega_ids:
        try:
            correccion = await self.corregir(entrega_id, user_api_key_encrypted)
            resultados.append(correccion)

            # Rate limiting: 1 corrección cada 2 segundos mínimo
            await asyncio.sleep(2)

        except HTTPException as e:
            # Continuar con las siguientes, log del error
            logger.error(f"Error corrigiendo entrega {entrega_id}: {e.detail}")
            continue

    return resultados
```

## Data Models

### Correccion Model

```python
# models/correccion.py
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Correccion(Base):
    __tablename__ = "correcciones"

    id = Column(Integer, primary_key=True, index=True)
    entrega_id = Column(Integer, ForeignKey("entregas.id"), nullable=False)

    nota = Column(Integer, nullable=False)  # 0-100
    criterios = Column(JSONB, nullable=False)  # Lista de criterios evaluados
    fortalezas = Column(JSONB, nullable=False, default=list)  # Lista de strings
    recomendaciones = Column(JSONB, nullable=False, default=list)  # Lista de strings
    comentario_general = Column(Text, nullable=False)

    editado_manualmente = Column(Boolean, default=False)
    fecha_correccion = Column(DateTime, default=datetime.utcnow)
    fecha_edicion = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    entrega = relationship("Entrega", back_populates="correccion")


# Estructura de criterios (JSONB):
# [
#   {
#     "id": "uuid-del-criterio",
#     "nombre": "Funcionalidad",
#     "puntaje_obtenido": 25,
#     "puntaje_maximo": 30,
#     "estado": "OK",
#     "feedback": "El código cumple con los requisitos..."
#   }
# ]
```

### Correccion Schemas

```python
# schemas/correccion.py
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class CriterioEvaluado(BaseModel):
    id: str
    nombre: str
    puntaje_obtenido: int = Field(ge=0)
    puntaje_maximo: int = Field(ge=1)
    estado: Literal["OK", "WARNING", "ERROR"]
    feedback: str


class CorreccionResponse(BaseModel):
    id: int
    entrega_id: int
    nota: int
    criterios: list[CriterioEvaluado]
    fortalezas: list[str]
    recomendaciones: list[str]
    comentario_general: str
    editado_manualmente: bool
    fecha_correccion: datetime

    class Config:
        from_attributes = True


class CorreccionUpdate(BaseModel):
    """Para edición manual de correcciones."""
    nota: Optional[int] = Field(None, ge=0, le=100)
    criterios: Optional[list[CriterioEvaluado]] = None
    fortalezas: Optional[list[str]] = None
    recomendaciones: Optional[list[str]] = None
    comentario_general: Optional[str] = None
```

## Error Handling

```python
# core/exceptions.py

class N8NError(Exception):
    """Error genérico de N8N."""
    pass


class N8NTimeoutError(N8NError):
    """Timeout esperando respuesta de N8N."""
    pass


class GeminiError(Exception):
    """Error de la API de Gemini."""
    pass


class APIKeyInvalidError(Exception):
    """API Key de Gemini inválida."""
    pass
```

## API Endpoints

```python
# routers/correcciones.py

@router.post("/{entrega_id}/corregir", response_model=CorreccionResponse)
async def corregir_entrega(
    entrega_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Corrige una entrega con IA."""
    require_tutor(current_user)

    if not current_user.api_key_encrypted:
        raise HTTPException(400, "Debes configurar tu API Key de Gemini")

    service = CorreccionService(db)
    return await service.corregir(entrega_id, current_user.api_key_encrypted)


@router.post("/corregir-lote", response_model=list[CorreccionResponse])
async def corregir_lote(
    data: CorregirLoteRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Corrige múltiples entregas en lote."""
    require_tutor(current_user)

    if not current_user.api_key_encrypted:
        raise HTTPException(400, "Debes configurar tu API Key de Gemini")

    if len(data.entrega_ids) > 50:
        raise HTTPException(400, "Máximo 50 entregas por lote")

    service = CorreccionService(db)
    return await service.corregir_lote(data.entrega_ids, current_user.api_key_encrypted)


@router.put("/{correccion_id}", response_model=CorreccionResponse)
def editar_correccion(
    correccion_id: int,
    data: CorreccionUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Edita manualmente una corrección."""
    require_tutor(current_user)

    service = CorreccionService(db)
    return service.editar(correccion_id, data, current_user.id)
```

## Performance Targets

| Métrica | Target |
|---------|--------|
| Corrección individual | < 60 segundos |
| Corrección en lote (30 entregas) | < 3 minutos |
| Tasa de éxito | > 95% |
| Retries necesarios | < 5% |

## Resources

- [Google Gemini API](https://ai.google.dev/docs)
- [N8N Documentation](https://docs.n8n.io/)
- [httpx Async Client](https://www.python-httpx.org/async/)
