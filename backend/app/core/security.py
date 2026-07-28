# app/core/security.py
"""
Security utilities for Active-IA.

Provides functions for:
- Password hashing and verification (bcrypt)
- JWT token generation and verification (HS256)
- API key encryption/decryption (Fernet: AES-128-CBC + HMAC-SHA256)

Ref: docs/specs/11-SEGURIDAD.md
"""

from datetime import datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# =========================================
# Password Hashing (bcrypt)
# =========================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Generate bcrypt hash of a password.

    Args:
        password: Plain text password.

    Returns:
        Bcrypt hash string.

    Example:
        >>> hashed = hash_password("mypassword123")
        >>> print(hashed)
        $2b$12$...
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a stored hash.

    Args:
        plain_password: Plain text password to verify.
        hashed_password: Bcrypt hash from database.

    Returns:
        True if password matches, False otherwise.

    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


# =========================================
# JWT Tokens
# =========================================


def create_access_token(
    user_id: int,
    username: str,
    *,
    rol: str | None,
    universidad_activa_id: int | None,
    es_superadmin: bool,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Generate a JWT access token for a user (multi-tenant, Fase 1).

    Args:
        user_id: User's database ID.
        username: User's username.
        rol: Rol del usuario EN LA UNIVERSIDAD ACTIVA (`RolEnum.value`), NO el
            rol global `usuarios.rol`. `None` únicamente en modo superadmin
            sin universidad elegida.
        universidad_activa_id: ID de la universidad en la que el usuario está
            operando. `None` únicamente en modo superadmin sin universidad
            elegida.
        es_superadmin: Flag de admin global (`usuarios.es_superadmin`).
        expires_delta: Optional custom expiration time.
                      Defaults to ACCESS_TOKEN_EXPIRE_DAYS from settings.

    Returns:
        Encoded JWT token string.

    Note:
        `rol`, `universidad_activa_id` y `es_superadmin` son keyword-only a
        propósito: cualquier caller que todavía los pase posicionalmente
        (estilo pre-multi-tenant) falla con TypeError en vez de compilar
        silenciosamente con el argumento equivocado.

    Example:
        >>> token = create_access_token(
        ...     1, "admin", rol="ADMIN", universidad_activa_id=1, es_superadmin=False
        ... )
        >>> print(token)
        eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)

    expire = datetime.utcnow() + expires_delta

    payload: dict[str, Any] = {
        "user_id": user_id,
        "username": username,
        "rol": rol,
        "universidad_activa_id": universidad_activa_id,
        "es_superadmin": es_superadmin,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    encoded_jwt = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload dictionary. Contiene siempre `user_id`, `username`,
        `exp`, `iat`. Desde Fase 1 multi-tenant (multi-tenant-auth-jwt)
        también contiene `universidad_activa_id` (int | None), `rol`
        (string del `RolEnum` de la membresía activa, no `usuarios.rol`;
        None solo en modo superadmin sin universidad) y `es_superadmin`
        (bool) — pero un token emitido ANTES de este change puede no traer
        esos 3 claims (KeyError si se accede con `payload["..."]`; usar
        `payload.get("...")` para leerlos de forma retrocompatible).

    Raises:
        JWTError: If token is invalid or expired.

    Example:
        >>> token = create_access_token(
        ...     1, "admin", rol="ADMIN", universidad_activa_id=1, es_superadmin=False
        ... )
        >>> payload = decode_token(token)
        >>> print(payload["user_id"])
        1
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid or expired token: {str(e)}")


TRANSITIONAL_TOKEN_EXPIRE_MINUTES = 5


def create_transitional_token(user_id: int, username: str) -> str:
    """
    Generate a short-lived transitional JWT for the login-in-two-steps flow.

    Fase 1 multi-tenant (multi-tenant-auth-jwt): emitido por
    `POST /auth/login` cuando el usuario tiene 2+ membresías activas
    (`requiere_seleccion=true`), para identificar al usuario en
    `POST /auth/select-universidad` **sin** emitir todavía un token de
    acceso completo. Se distingue de `create_access_token` por el claim
    `scope="seleccion"` y por NO llevar `universidad_activa_id`/`rol`/
    `es_superadmin` — no sirve como token de acceso.

    Args:
        user_id: User's database ID.
        username: User's username.

    Returns:
        Encoded JWT token string, válido por `TRANSITIONAL_TOKEN_EXPIRE_MINUTES`.
    """
    expire = datetime.utcnow() + timedelta(minutes=TRANSITIONAL_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "user_id": user_id,
        "username": username,
        "scope": "seleccion",
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# =========================================
# API Key Encryption (Fernet: AES-128-CBC + HMAC-SHA256)
# =========================================


def _get_fernet() -> Fernet:
    """
    Get Fernet instance for encryption/decryption.

    Returns:
        Fernet instance configured with ENCRYPTION_KEY from settings.

    Note:
        This is a private function. Use encrypt_api_key/decrypt_api_key instead.
    """
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage.

    Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
    ENCRYPTION_KEY must be a Fernet key: 32 random bytes base64-url-safe
    encoded (44 chars), generated with Fernet.generate_key() — not a raw
    32-char string.

    Args:
        api_key: Plain text API key (e.g., Gemini API key).

    Returns:
        Encrypted API key as base64 string.

    Raises:
        ValueError: If api_key is empty.

    Example:
        >>> encrypted = encrypt_api_key("AIzaSyD...")
        >>> print(encrypted)
        gAAAAABl...
    """
    if not api_key:
        raise ValueError("API key cannot be empty")

    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(api_key.encode())
    return encrypted_bytes.decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt a stored API key.

    Args:
        encrypted_key: Encrypted API key from database.

    Returns:
        Plain text API key.

    Raises:
        ValueError: If encrypted_key is empty.
        cryptography.fernet.InvalidToken: If decryption fails
                                          (wrong key or corrupted data).

    Example:
        >>> encrypted = encrypt_api_key("AIzaSyD...")
        >>> decrypted = decrypt_api_key(encrypted)
        >>> print(decrypted)
        AIzaSyD...
    """
    if not encrypted_key:
        raise ValueError("Encrypted API key cannot be empty")

    fernet = _get_fernet()
    decrypted_bytes = fernet.decrypt(encrypted_key.encode())
    return decrypted_bytes.decode()


# =========================================
# Utility Functions
# =========================================


def generate_temp_password(length: int = 12) -> str:
    """
    Generate a secure temporary password.

    Used when admin creates a new user. The password includes:
    - Random letters (uppercase and lowercase)
    - At least one digit
    - Total length specified by parameter

    Args:
        length: Length of the password (default: 12).

    Returns:
        Temporary password string.

    Example:
        >>> temp_pass = generate_temp_password()
        >>> print(len(temp_pass))
        12
        >>> any(c.isdigit() for c in temp_pass)
        True
    """
    import secrets
    import string

    # Generate random characters (letters + digits)
    alphabet = string.ascii_letters + string.digits

    # Ensure at least one digit
    password = "".join(secrets.choice(alphabet) for _ in range(length - 1))
    password += secrets.choice(string.digits)

    # Shuffle to avoid digit always at the end
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)

    return "".join(password_list)
