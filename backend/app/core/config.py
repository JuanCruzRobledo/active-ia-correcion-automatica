# app/core/config.py
"""
Configuración central de la aplicación usando pydantic-settings.
Carga variables desde .env y proporciona valores por defecto seguros.

Ref: docs/specs/05-ARQUITECTURA-STACK.md seccion 11.1
Ref: docs/specs/11-SEGURIDAD.md
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación.

    Variables se cargan desde:
    1. Variables de entorno del sistema
    2. Archivo .env en la raíz del proyecto
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================
    # Aplicación
    # =========================================
    APP_NAME: str = "Active-IA"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # =========================================
    # Base de datos
    # =========================================
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/activeai"

    # Pool de conexiones
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # =========================================
    # Seguridad - JWT
    # =========================================
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    # =========================================
    # Seguridad - Encriptación
    # =========================================
    # Key para encriptar API Keys de Gemini (Fernet/AES-256)
    # Generar con: from cryptography.fernet import Fernet; Fernet.generate_key()
    ENCRYPTION_KEY: str = "change-me-in-production-use-fernet-generate-key"

    # =========================================
    # Seguridad - Bloqueo de cuenta
    # =========================================
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # =========================================
    # Seguridad - Contraseñas
    # =========================================
    PASSWORD_MIN_LENGTH: int = 8

    # =========================================
    # N8N Integration
    # =========================================
    N8N_BASE_URL: str = "http://n8n:5678"
    N8N_WEBHOOK_CORRECCION: str = "http://n8n:5678/webhook/corregir"
    N8N_WEBHOOK_RUBRICA: str = "http://n8n:5678/webhook/generar-rubrica"
    N8N_WEBHOOK_HEALTH: str = "http://n8n:5678/webhook/health"
    N8N_WEBHOOK_SECRET: str = "change-me-webhook-secret"
    N8N_TIMEOUT_SECONDS: int = 90

    # =========================================
    # OpenRouter (proveedor de IA del workflow de corrección)
    # =========================================
    # La API key del usuario es de OpenRouter (sk-or-v1-...) y se usa con auth
    # Bearer. El modelo está hardcodeado en el workflow de n8n; lo replicamos
    # acá solo para validar la key (health check).
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "google/gemini-3.5-flash"

    # =========================================
    # Archivos
    # =========================================
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 104857600  # 100 MB en bytes
    ALLOWED_EXTENSIONS: List[str] = [".zip", ".txt"]

    # =========================================
    # CORS
    # =========================================
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    CORS_ALLOW_HEADERS: List[str] = ["Authorization", "Content-Type"]

    # =========================================
    # Logging
    # =========================================
    LOG_LEVEL: str = "INFO"

    # =========================================
    # Rate Limiting
    # =========================================
    RATE_LIMIT_LOGIN_REQUESTS: int = 10
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = 900  # 15 minutos
    RATE_LIMIT_API_REQUESTS: int = 100
    RATE_LIMIT_API_WINDOW_SECONDS: int = 60  # 1 minuto
    RATE_LIMIT_CORRECCION_REQUESTS: int = 20
    RATE_LIMIT_CORRECCION_WINDOW_SECONDS: int = 60

    # =========================================
    # Eliminación
    # =========================================
    # Si es True, los endpoints de DELETE eliminan el registro físicamente
    # de la base de datos (hard delete) con cascada completa.
    # Si es False (default), se usa baja lógica (soft delete, activo=False).
    ALLOW_HARD_DELETE: bool = False

    # =========================================
    # Email / Resend (notificaciones de avance)
    # =========================================
    # API key de Resend. Vacía => el EmailService no envía (modo no configurado).
    RESEND_API_KEY: str = ""
    # Remitente. En SANDBOX (sin dominio verificado) debe ser onboarding@resend.dev.
    EMAIL_REMITENTE: str = "onboarding@resend.dev"
    # Throttle de envío (emails/segundo) para respetar el rate limit de Resend.
    EMAIL_RATE_POR_SEGUNDO: float = 8.0

    # =========================================
    # Validators
    # =========================================
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Permite CORS_ORIGINS como string separado por comas o lista."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, v):
        """Permite ALLOWED_EXTENSIONS como string separado por comas o lista."""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instancia cacheada de Settings.

    Usar esta función en lugar de instanciar Settings() directamente
    para evitar leer el archivo .env múltiples veces.

    Ejemplo:
        from app.core.config import get_settings

        settings = get_settings()
        print(settings.DATABASE_URL)
    """
    return Settings()


# Instancia global para imports directos
settings = get_settings()
