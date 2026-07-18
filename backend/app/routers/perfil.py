# app/routers/perfil.py
"""
Profile router for user profile operations.

Endpoints:
- GET /perfil: Get current user's profile
- POST /perfil/api-key: Update Gemini API Key

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-PERF-01, HU-PERF-02
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.security import decrypt_api_key, encrypt_api_key
from app.integrations import ia_provider
from app.models import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.perfil import (
    PerfilResponse,
    UpdateApiKeyRequest,
    UpdateApiKeyResponse,
    UpdateCorrectionProviderRequest,
    UpdateCorrectionProviderResponse,
    UpdateEmailRequest,
    UpdateEmailResponse,
    UpdateKeyPagaRequest,
    UpdateKeyPagaResponse,
)

logger = logging.getLogger(__name__)


def _last_4(encrypted: str | None) -> str | None:
    """Últimos 4 caracteres de una key encriptada (para mostrar enmascarada)."""
    if not encrypted:
        return None
    try:
        decrypted = decrypt_api_key(encrypted)
        return decrypted[-4:] if len(decrypted) >= 4 else None
    except Exception:
        return None

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.patch("/key-paga", response_model=UpdateKeyPagaResponse)
async def update_key_paga(
    data: UpdateKeyPagaRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateKeyPagaResponse:
    """
    Toggle manual: marca si la API key Gemini del usuario es paga (billing habilitado).

    Habilita la corrección masiva global ('Corregir todo'). No se infiere por API
    (la Fase 0 demostró que el tier no es detectable de forma fiable).
    """
    user_repo = UsuarioRepository(db)
    current_user.gemini_api_key_paga = data.paga
    await user_repo.update(current_user)
    return UpdateKeyPagaResponse(
        message="Preferencia actualizada", gemini_api_key_paga=data.paga
    )


@router.patch("/email", response_model=UpdateEmailResponse)
async def update_email(
    data: UpdateEmailRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateEmailResponse:
    """Setea (o limpia) el email de notificaciones del usuario actual.

    Es el email al que se envían las notificaciones (PDF del tutor académico). El login
    sigue siendo por username, así que esto NO afecta el acceso. **Permisos**: cualquiera.
    """
    user_repo = UsuarioRepository(db)
    current_user.email = data.email
    await user_repo.update(current_user)
    return UpdateEmailResponse(message="Email actualizado", email=data.email)


@router.get("", response_model=PerfilResponse)
async def get_profile(
    current_user: Usuario = Depends(get_current_user),
) -> PerfilResponse:
    """
    Get current user's profile.

    Returns complete user information including API Key status
    (but not the key itself).

    **Permissions**: All authenticated users
    """
    return PerfilResponse(
        id=current_user.id,
        username=current_user.username,
        nombre=current_user.nombre,
        email=current_user.email,
        rol=current_user.rol,
        primer_login=current_user.primer_login,
        gemini_api_key_valid=current_user.gemini_api_key_valid,
        gemini_api_key_last_4=_last_4(current_user.gemini_api_key_encrypted),
        gemini_api_key_paga=getattr(current_user, "gemini_api_key_paga", False),
        correction_provider=ia_provider.normalizar_provider(
            getattr(current_user, "correction_provider", None)
        ),
        openrouter_api_key_valid=getattr(current_user, "openrouter_api_key_valid", False),
        openrouter_api_key_last_4=_last_4(
            getattr(current_user, "openrouter_api_key_encrypted", None)
        ),
        moodle_username=current_user.moodle_username,
        moodle_host=current_user.moodle_host,
        moodle_configured=bool(current_user.moodle_username and current_user.moodle_password_encrypted),
        activo=current_user.activo,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login=current_user.last_login,
    )


@router.post("/api-key", response_model=UpdateApiKeyResponse)
async def update_api_key(
    data: UpdateApiKeyRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateApiKeyResponse:
    """
    Configura la API Key del proveedor de corrección indicado (`provider`).

    Valida contra el proveedor correspondiente (Gemini Studio → Google;
    OpenRouter → consulta real a google/gemini-3.5-flash) ANTES de guardar.
    Si es válida, se encripta con AES-256 en la columna propia de ese proveedor.
    Las keys de cada proveedor se guardan por separado.

    **Permissions**: All authenticated users
    """
    api_key = data.gemini_api_key.strip()
    provider = ia_provider.normalizar_provider(data.provider)

    # Health check contra el proveedor correspondiente antes de guardar.
    is_valid = await ia_provider.validar_api_key(provider, api_key)

    if not is_valid:
        return UpdateApiKeyResponse(
            message="API Key inválida o sin permisos",
            valid=False,
        )

    try:
        encrypted_key = encrypt_api_key(api_key)
        user_repo = UsuarioRepository(db)

        # Guardar en la columna del proveedor correspondiente (keys separadas).
        if provider == ia_provider.PROVIDER_OPENROUTER:
            current_user.openrouter_api_key_encrypted = encrypted_key
            current_user.openrouter_api_key_valid = True
        else:
            current_user.gemini_api_key_encrypted = encrypted_key
            current_user.gemini_api_key_valid = True

        await user_repo.update(current_user)

        return UpdateApiKeyResponse(
            message="API Key configurada exitosamente",
            valid=True,
        )

    except Exception:
        logger.exception(
            "Error al guardar API Key para usuario %s", current_user.id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar la API Key. Intentá nuevamente.",
        )


@router.patch("/correction-provider", response_model=UpdateCorrectionProviderResponse)
async def update_correction_provider(
    data: UpdateCorrectionProviderRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateCorrectionProviderResponse:
    """Cambia el modo de corrección activo del usuario (slider del perfil).

    No valida ni borra ninguna key: solo cambia cuál proveedor se usa para
    corregir. Cada proveedor conserva su propia API key guardada.

    **Permissions**: All authenticated users
    """
    provider = ia_provider.normalizar_provider(data.provider)
    user_repo = UsuarioRepository(db)
    current_user.correction_provider = provider
    await user_repo.update(current_user)
    return UpdateCorrectionProviderResponse(
        message="Modo de corrección actualizado",
        correction_provider=provider,
    )
