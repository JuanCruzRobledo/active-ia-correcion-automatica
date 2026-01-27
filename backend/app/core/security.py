# app/core/security.py
"""
Security utilities for Active-IA.

Provides functions for:
- Password hashing and verification (bcrypt)
- JWT token generation and verification (HS256)
- API key encryption/decryption (AES-256 via Fernet)

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
    rol: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Generate a JWT access token for a user.

    Args:
        user_id: User's database ID.
        username: User's username.
        rol: User's role (ADMIN, COORDINADOR, TUTOR).
        expires_delta: Optional custom expiration time.
                      Defaults to ACCESS_TOKEN_EXPIRE_DAYS from settings.

    Returns:
        Encoded JWT token string.

    Example:
        >>> token = create_access_token(1, "admin", "ADMIN")
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
        Decoded payload dictionary containing user_id, username, rol, exp, iat.

    Raises:
        JWTError: If token is invalid or expired.

    Example:
        >>> token = create_access_token(1, "admin", "ADMIN")
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


# =========================================
# API Key Encryption (AES-256 via Fernet)
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

    Uses AES-256 encryption via Fernet (symmetric encryption).

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
