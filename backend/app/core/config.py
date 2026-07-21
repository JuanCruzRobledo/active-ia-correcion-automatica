# app/core/config.py
"""
Configuración central de la aplicación usando pydantic-settings.
Carga variables desde .env y proporciona valores por defecto seguros.

Ref: docs/specs/05-ARQUITECTURA-STACK.md seccion 11.1
Ref: docs/specs/11-SEGURIDAD.md
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Valores default públicos de los secretos. Viven en el repositorio, así que un
# despliegue de producción que los conserve es explotable (SEC-003): permiten
# forjar JWT de ADMIN y descifrar las API keys y contraseñas almacenadas.
# Son una única fuente de verdad: el default del campo y el validador de
# arranque leen de acá.
_DEFAULT_SECRET_KEY = "change-me-in-production-use-openssl-rand-hex-32"
_DEFAULT_ENCRYPTION_KEY = "change-me-in-production-use-fernet-generate-key"

# Todo secreto que empiece así es un placeholder público del repositorio: el
# default de arriba, o el de .env.example ("change-me-in-production"). Se
# rechazan por prefijo porque el operador que copia .env.example sin tocarlo es
# el vector real de SEC-003, y ese valor NO coincide con el default de acá.
_PREFIJO_SECRETO_INSEGURO = "change-me-in-production"


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
    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    # =========================================
    # Seguridad - Encriptación
    # =========================================
    # Key para encriptar API Keys de Gemini (Fernet/AES-256)
    # Generar con: from cryptography.fernet import Fernet; Fernet.generate_key()
    ENCRYPTION_KEY: str = _DEFAULT_ENCRYPTION_KEY

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
    # Gemini API (corrección e IA directa)
    # =========================================
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_TIMEOUT_SECONDS: float = 90.0

    # =========================================
    # OpenRouter (proveedor alternativo de corrección)
    # =========================================
    # La API key del usuario es de OpenRouter (sk-or-v1-...) y se usa con auth
    # Bearer.
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "google/gemini-3.5-flash"

    # =========================================
    # Archivos
    # =========================================
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 104857600  # 100 MB en bytes
    ALLOWED_EXTENSIONS: List[str] = [".zip", ".txt"]

    # Anti ZIP-bomb (SEC-005 / PERF-008): topes al descomprimir/consolidar ZIPs.
    # - MAX_ZIP_EXPANDED_SIZE: tamaño DESCOMPRIMIDO acumulado permitido
    #   (suma de ZipInfo.file_size). Se alinea con MAX_UPLOAD_SIZE (100 MB): una
    #   entrega legítima descomprimida no debería superar el propio tope de subida.
    # - MAX_ZIP_ENTRIES: cantidad máxima de entradas del ZIP; corta las bombas de
    #   "muchos archivos diminutos" que el tope de tamaño no atrapa.
    MAX_ZIP_EXPANDED_SIZE: int = MAX_UPLOAD_SIZE  # 100 MB descomprimido acumulado

    # IA-015: tope de caracteres del código consolidado que se manda al LLM. Una
    # entrega enorme podía inflar el payload sin control (costo de tokens / rechazo
    # del modelo). ~200k chars ≈ ~50k tokens, holgado para una entrega de código.
    MAX_CODIGO_CORRECCION_CHARS: int = 200_000
    MAX_ZIP_ENTRIES: int = 5000

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
    # CRUD-002: se eliminó el flag ALLOW_HARD_DELETE. Los DELETE son SIEMPRE soft
    # (baja lógica), nunca físico — regla dura del proyecto (auditoría). Antes el
    # flag sobrecargaba el mismo verbo DELETE con dos semánticas opuestas según
    # config: un solo cambio de env degradaba todo el sistema a borrado destructivo
    # (incluido el audit log). Si alguna vez se necesita purga física real, debe ser
    # una feature deliberada y auditada (endpoint /purge explícito), no un toggle.

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

    @model_validator(mode="after")
    def rechazar_secretos_default_en_produccion(self) -> "Settings":
        """Aborta el arranque si en producción (DEBUG=False) los secretos siguen
        siendo los defaults públicos del repositorio (SEC-003)."""
        if self.DEBUG:
            return self

        candidatos = (
            (
                "SECRET_KEY",
                self.SECRET_KEY,
                "openssl rand -hex 32",
            ),
            (
                "ENCRYPTION_KEY",
                self.ENCRYPTION_KEY,
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"',
            ),
        )
        # Mensaje sin acentos a proposito: se lee en logs de deploy y consolas
        # sin UTF-8 (Windows/cp1252), donde los acentos salen corruptos.
        inseguras = [
            f"  - {nombre}: conserva un valor placeholder. Genera uno real con: {comando}"
            for nombre, valor, comando in candidatos
            if valor.startswith(_PREFIJO_SECRETO_INSEGURO)
        ]
        if inseguras:
            raise ValueError(
                "Arranque abortado: hay secretos con valor placeholder en produccion "
                "(DEBUG=False). Configura estas variables en el .env antes de "
                "desplegar:\n" + "\n".join(inseguras)
            )
        return self


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
