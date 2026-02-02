# app/routers/perfil.py
"""
Profile router for user profile operations.

Endpoints:
- GET /perfil: Get current user's profile
- POST /perfil/api-key: Update Gemini API Key

Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-PERF-01, HU-PERF-02
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.security import decrypt_api_key, encrypt_api_key
from app.models import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.perfil import (
    PerfilResponse,
    UpdateApiKeyRequest,
    UpdateApiKeyResponse,
)

router = APIRouter(prefix="/perfil", tags=["perfil"])


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
    # Get last 4 characters of API Key if configured
    gemini_api_key_last_4 = None
    if current_user.gemini_api_key_encrypted:
        try:
            decrypted_key = decrypt_api_key(current_user.gemini_api_key_encrypted)
            gemini_api_key_last_4 = decrypted_key[-4:] if len(decrypted_key) >= 4 else None
        except Exception:
            # If decryption fails, just don't show last 4
            pass

    return PerfilResponse(
        id=current_user.id,
        username=current_user.username,
        nombre=current_user.nombre,
        rol=current_user.rol,
        primer_login=current_user.primer_login,
        gemini_api_key_valid=current_user.gemini_api_key_valid,
        gemini_api_key_last_4=gemini_api_key_last_4,
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
    Update user's Gemini API Key.

    The API Key is validated by making a test call to Gemini API.
    If valid, it is encrypted with AES-256 and stored.

    **Permissions**: All authenticated users
    """
    api_key = data.gemini_api_key.strip()

    # Validate format
    if not api_key.startswith("AIza"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La API Key debe comenzar con 'AIza'",
        )

    # Validate with Gemini API (test call)
    is_valid = await _validate_gemini_api_key(api_key)

    if not is_valid:
        return UpdateApiKeyResponse(
            message="API Key inválida o sin permisos",
            valid=False,
        )

    # Encrypt and save
    try:
        encrypted_key = encrypt_api_key(api_key)

        # Update user
        user_repo = UsuarioRepository(db)
        current_user.gemini_api_key_encrypted = encrypted_key
        current_user.gemini_api_key_valid = True
        await user_repo.update(current_user)

        return UpdateApiKeyResponse(
            message="API Key configurada exitosamente",
            valid=True,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar API Key: {str(e)}",
        )


async def _validate_gemini_api_key(api_key: str) -> bool:
    """
    Validate Gemini API Key by making a test call.

    Args:
        api_key: Gemini API Key to validate.

    Returns:
        True if valid, False otherwise.
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Responde OK"
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{url}?key={api_key}",
                json=payload,
                headers=headers,
            )

            # Valid API Key returns 200
            if response.status_code == 200:
                return True

            # 400 usually means invalid or unauthorized API Key
            return False

    except httpx.TimeoutException:
        # Timeout doesn't necessarily mean invalid key, but we'll be conservative
        return False
    except Exception:
        # Any other error, consider invalid
        return False
