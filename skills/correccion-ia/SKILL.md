---
name: correccion-ia
description: >
  Flujo de corrección automática de trabajos prácticos con IA nativa en el backend
  (Gemini Studio u OpenRouter, llamadas HTTP directas).
  Trigger: Cuando trabajes con corrección de entregas, integración con IA, o el flujo
  de evaluación automática.
metadata:
  author: Active-IA Team
  version: "2.0"
  scope: [root, backend]
  auto_invoke:
    - "Implementing correction flow"
    - "Integrating with Gemini API"
    - "Processing AI evaluations"
    - "Calling the AI provider directly"
---

# Corrección IA Skill

> ⚠️ **Arquitectura actualizada — N8N fue removido.** La corrección/generación con IA es NATIVA en el backend: `backend/app/integrations/ia_provider.py` rutea a `gemini_correction_client.py` (Gemini Studio) o `openrouter_client.py` (OpenRouter) con llamadas HTTP directas. NO existe `n8n_client.py` ni `settings.N8N_WEBHOOK_URL`. Los ejemplos de este skill fueron corregidos a esa realidad; si ves referencias residuales a N8N, la fuente de verdad es el código en `backend/app/integrations/`.

## When to Use

- Implementando el flujo de corrección automática
- Integrando con los clientes de IA (`gemini_correction_client`, `openrouter_client`) vía el dispatcher `ia_provider`
- Procesando respuestas de Gemini / OpenRouter
- Manejando errores de IA
- Optimizando prompts de evaluación

## Architecture Overview

```
┌─────────────┐   ia_provider   ┌──────────────────────────┐     ┌─────────────┐
│   Active-IA │────normaliza────▶│ GeminiCorrectionClient   │────▶│  Gemini API │
│   Backend   │    provider      │   (HTTP directo)         │◀────│  (Studio)   │
│ (Service)   │◀─────────────────│  ó openrouter_client     │     │  ó OpenRouter│
└─────────────┘                  └──────────────────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│  PostgreSQL │
│ (Correccion)│
└─────────────┘
```

No hay servicio N8N intermediario: el backend llama directamente a la API del proveedor
elegido por el tutor (`usuario.correction_provider` → `gemini` por defecto, u `openrouter`).

## Critical Patterns

### ALWAYS
- Validar API Key contra el proveedor activo antes de corregir (`ia_provider.validar_api_key`)
- Incluir timeout en la llamada al cliente de IA (`settings.GEMINI_TIMEOUT_SECONDS`, ~90 s)
- Parsear respuesta JSON del proveedor con validación (Pydantic)
- Guardar estado ERROR si falla la corrección
- Encriptar API Keys con Fernet (AES-128-CBC + HMAC-SHA256) — `app/core/security.py`
- Log de cada corrección (entrada y salida)
- Retry acotado ante timeout / error transitorio (el service reintenta 1 vez con backoff)

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
| API Key inválida (`APIKeyInvalidError`) | Marcar entrega como ERROR, marcar key inválida, notificar usuario |
| Timeout del proveedor (`N8NTimeoutError`) | Retry 1 vez, luego ERROR |
| Respuesta malformada | Validar con Pydantic, si falla → ERROR |
| Rate limit (`QuotaExceededError`) | 429 al usuario; el lote reintenta con backoff |
| Error del proveedor (`N8NError`) | Retry con backoff, luego ERROR |

> Nota histórica: `N8NError` / `N8NTimeoutError` (y los códigos `N8N_TIMEOUT` / `N8N_ERROR`) se conservan como NOMBRES HISTÓRICOS —persistidos en datos y en el catálogo de errores— pero hoy los LANZAN los clientes de Gemini/OpenRouter. No implican que exista un servicio N8N.

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
from app.integrations import openrouter_client
from app.integrations.gemini_correction_client import GeminiCorrectionClient
from app.core.security import decrypt_api_key
from app.core.exceptions import N8NError, N8NTimeoutError, APIKeyInvalidError


class CorreccionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.entrega_repo = EntregaRepository(db)
        self.correccion_repo = CorreccionRepository(db)
        self.rubrica_repo = RubricaRepository(db)
        # Cliente directo a Gemini Studio (sin N8N intermediario).
        self.gemini_client = GeminiCorrectionClient()

    async def corregir_individual(
        self,
        entrega_id: int,
        api_key_encrypted: str,
        corregido_por_id: int,
        provider: str = "gemini",  # "gemini" | "openrouter"
    ) -> CorreccionResponse:
        # 1. Obtener entrega + rúbrica
        entrega = await self.entrega_repo.get_by_id_with_relations(entrega_id)
        if not entrega:
            raise HTTPException(404, "Entrega no encontrada")
        rubrica = await self.rubrica_repo.get_active_by_id(entrega.rubrica_id)
        if not rubrica:
            raise HTTPException(404, "Rúbrica no encontrada o inactiva")

        # 2. Desencriptar API Key (Fernet)
        api_key = decrypt_api_key(api_key_encrypted)

        # 3. Construir payload y marcar entrega PENDIENTE
        payload = self._build_correction_payload(entrega, rubrica, api_key)
        entrega.estado = EstadoEntregaEnum.PENDIENTE
        await self.entrega_repo.update(entrega)

        # 4. Llamar DIRECTAMENTE al proveedor de IA (Gemini o OpenRouter),
        #    con 1 retry ante timeout/error transitorio.
        try:
            result = await self._call_ia_with_retry(payload, provider=provider)
        except N8NTimeoutError:  # nombre histórico: lo lanza el cliente de IA
            _marcar_entrega_error(entrega, ERROR_N8N_TIMEOUT, provider)
            await self.entrega_repo.update(entrega)
            raise HTTPException(502, "Timeout en el servicio de IA")
        except N8NError as e:
            _marcar_entrega_error(entrega, ERROR_N8N, provider)
            await self.entrega_repo.update(entrega)
            raise HTTPException(502, f"Error en el servicio de IA: {e}")

        # 5. Parsear/validar respuesta y persistir la corrección
        gemini_response = self._parse_gemini_response(result)
        correccion = await self._save_correccion(entrega, gemini_response, corregido_por_id)

        # 6. Actualizar estado de entrega
        entrega.estado = EstadoEntregaEnum.CORREGIDA
        await self.entrega_repo.update(entrega)
        return await self._build_correccion_response(correccion)


async def _call_ia_with_retry(self, payload: dict, provider: str = "gemini", max_retries: int = 1):
    """Llama al proveedor elegido; reintenta 1 vez ante timeout/N8NError."""
    for attempt in range(max_retries + 1):
        try:
            if provider == "openrouter":
                return await openrouter_client.corregir(payload)
            return await self.gemini_client.corregir_codigo(payload)
        except (APIKeyInvalidError, QuotaExceededError):
            raise  # nunca reintentar errores de key / rate limit
        except (N8NTimeoutError, N8NError):
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # backoff exponencial
                continue
            raise
```

### 2. Payload de corrección

El payload es el que consumen los clientes de IA (`GeminiCorrectionClient.corregir_codigo`
y `openrouter_client.corregir`). NO lleva `model` — cada cliente usa el modelo de su
configuración (`settings.GEMINI_MODEL` / `settings.OPENROUTER_MODEL`).

```python
def _build_correction_payload(
    self,
    entrega: Entrega,
    rubrica: Rubrica,
    api_key: str,
) -> dict:
    codigo = entrega.contenido_consolidado or entrega.contenido_preview
    return {
        "codigo": codigo,
        "rubrica": {
            "titulo": rubrica.titulo,
            "descripcion": rubrica.descripcion or "",
            "tipo": rubrica.tipo.value,
            "puntaje_maximo": rubrica.puntaje_maximo,
            "metadata": rubrica.metadata_json or {},
            "criterios": rubrica.criterios_json or [],   # JSONB
            "penalizaciones": rubrica.penalizaciones_json or [],
            "condiciones_desaprobacion": rubrica.condiciones_desaprobacion_json or [],
            "schema_version": rubrica.schema_version,
        },
        "api_key": api_key,
        "contexto": {
            "materia": entrega.comision.materia.nombre,
            "alumno": entrega.alumno_nombre,
        },
    }
```

El prompt de sistema/usuario y el `responseSchema` estricto los arma cada cliente
internamente (ver `gemini_correction_client._build_criterios_texto` y el prompt de
`corregir_codigo`), con `temperature=0` y `responseMimeType="application/json"`.

### 3. Cliente de IA directo (Gemini Studio / OpenRouter)

El dispatcher `ia_provider` normaliza el proveedor elegido por el tutor y valida la key
contra ESE proveedor. La corrección se hace con llamadas HTTP directas — NO hay N8N.

```python
# integrations/ia_provider.py
from app.integrations import gemini_studio_client, openrouter_client

PROVIDER_GEMINI = "gemini"
PROVIDER_OPENROUTER = "openrouter"
PROVIDERS_VALIDOS = frozenset({PROVIDER_GEMINI, PROVIDER_OPENROUTER})


def normalizar_provider(provider: str | None) -> str:
    """Normaliza el provider; cae a Gemini Studio si es vacío/desconocido."""
    if not provider:
        return PROVIDER_GEMINI
    limpio = provider.strip().lower()
    return limpio if limpio in PROVIDERS_VALIDOS else PROVIDER_GEMINI


async def validar_api_key(provider: str, api_key: str) -> bool:
    if normalizar_provider(provider) == PROVIDER_OPENROUTER:
        return await openrouter_client.validar_api_key(api_key)
    return await gemini_studio_client.validar_api_key(api_key)
```

```python
# integrations/gemini_correction_client.py  (cliente directo — reemplaza a N8N)
import httpx
from app.core.config import settings
from app.core.exceptions import N8NError, N8NTimeoutError  # nombres históricos

_GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={api_key}"
)


class GeminiCorrectionClient:
    """Cliente directo a Gemini — hace POST a generativelanguage, sin intermediario."""

    def __init__(self):
        self.model = settings.GEMINI_MODEL  # "gemini-3.5-flash"
        self.correction_timeout = float(settings.GEMINI_TIMEOUT_SECONDS)

    def _generate_url(self, api_key: str) -> str:
        return _GEMINI_GENERATE_URL.format(model=self.model, api_key=api_key)

    async def corregir_codigo(self, payload: dict) -> dict:
        """Corrige código con Gemini directo. payload: {codigo, rubrica, api_key, contexto}."""
        body = {
            "generationConfig": {
                "temperature": 0,
                "topK": 1,
                "topP": 1,
                "candidateCount": 1,
                "responseMimeType": "application/json",
                "responseSchema": _SCHEMA_CORRECCION_CODIGO,  # JSON estricto
            },
            "contents": [{"role": "user", "parts": [{"text": self._build_prompt(payload)}]}],
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._generate_url(payload["api_key"]),
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=self.correction_timeout,  # ~90 s
                )
                if response.status_code != 200:
                    _handle_non_200(response)  # → APIKeyInvalidError / QuotaExceededError / N8NError
                return {"success": True, "correccion": _parse_candidate_json(response.json())}
            except httpx.TimeoutException:
                raise N8NTimeoutError("Timeout esperando respuesta de Gemini")
            except httpx.RequestError as e:
                raise N8NError(f"Error de conexión con Gemini: {e}")
```

Para PDF, el mismo cliente usa la Files API + Vision (`corregir_pdf`); OpenRouter usa
`POST {settings.OPENROUTER_BASE_URL}/chat/completions` con `Authorization: Bearer` y
`response_format` JSON (ver `openrouter_client.corregir`).

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
    """Parsea y valida la respuesta del proveedor de IA."""
    try:
        # El cliente devuelve {"success": True, "correccion": {...}, "metadata": {...}}
        if not response.get("success"):
            raise ValidationError("El proveedor de IA retornó error")
        gemini_output = response.get("correccion", {})

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

Las excepciones viven centralizadas en `app/core/exceptions.py` y sus mensajes/códigos
en `app/core/error_catalog.py`. `N8NError` / `N8NTimeoutError` son **nombres históricos**
(persistidos en datos y en el catálogo con los códigos `N8N_ERROR` / `N8N_TIMEOUT`), pero
hoy los LANZAN los clientes de Gemini/OpenRouter ante fallos HTTP o timeout — no implican
que exista un servicio N8N. NO redefinas estas clases en el flujo de corrección;
importalas del módulo central.

```python
# core/exceptions.py (fuente de verdad — no redefinir)
from app.core.exceptions import (
    APIKeyInvalidError,      # key inválida/expirada del proveedor activo
    InsufficientCreditsError, # sin créditos (OpenRouter)
    ModelOverloadedError,     # modelo sobrecargado (503)
    N8NError,                 # error genérico del proveedor de IA (nombre histórico)
    N8NTimeoutError,          # timeout del proveedor de IA (nombre histórico)
    QuotaExceededError,       # rate limit (429)
)
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
- [OpenRouter API](https://openrouter.ai/docs)
- [httpx Async Client](https://www.python-httpx.org/async/)
- Clientes reales: `backend/app/integrations/gemini_correction_client.py`, `openrouter_client.py`, `ia_provider.py`
