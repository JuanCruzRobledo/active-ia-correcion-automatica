# 11 - Seguridad

---

## 1. Resumen de Seguridad

| Aspecto | Implementación |
|---------|----------------|
| **Autenticación** | JWT con expiración 7 días |
| **Passwords** | bcrypt hash + política (8+ chars, 1 número) |
| **Primer login** | Forzar cambio de password temporal |
| **Bloqueo cuenta** | 5 intentos fallidos → 15 min bloqueado |
| **Encriptación** | AES-256 para API Keys Gemini |
| **Rate Limiting** | Por IP y por usuario |
| **Auditoría** | Log de acciones críticas |
| **Uploads** | Validación extensión + MIME + tamaño |
| **Webhooks N8N** | Header Auth con secret |

---

## 2. Autenticación

### 2.1 JWT (JSON Web Tokens)

| Aspecto | Especificación |
|---------|----------------|
| **Algoritmo** | HS256 |
| **Expiración** | 7 días |
| **Almacenamiento frontend** | localStorage |
| **Header** | `Authorization: Bearer <token>` |

**Payload del Token:**
```json
{
  "user_id": 123,
  "username": "jperez",
  "rol": "tutor",
  "iat": 1706140800,
  "exp": 1706745600
}
```

**Generación (Python):**
```python
# app/core/security.py

from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings

def create_access_token(user_id: int, username: str, rol: str) -> str:
    """
    Genera un token JWT para el usuario.

    Args:
        user_id: ID del usuario.
        username: Nombre de usuario.
        rol: Rol del usuario (admin, coordinador, tutor).

    Returns:
        Token JWT firmado.
    """
    expire = datetime.utcnow() + timedelta(days=settings.JWT_EXPIRE_DAYS)

    payload = {
        "user_id": user_id,
        "username": username,
        "rol": rol,
        "exp": expire,
        "iat": datetime.utcnow()
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> dict | None:
    """
    Verifica y decodifica un token JWT.

    Args:
        token: Token JWT a verificar.

    Returns:
        Payload decodificado o None si es inválido.

    Raises:
        JWTError: Si el token es inválido o expirado.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token expirado")
    except jwt.JWTError:
        raise UnauthorizedError("Token inválido")
```

### 2.2 Middleware de Autenticación

```python
# app/api/deps.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import verify_token
from app.repositories.user_repository import UserRepository

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """
    Obtiene el usuario actual desde el token JWT.

    Args:
        credentials: Credenciales del header Authorization.
        user_repo: Repositorio de usuarios.

    Returns:
        Usuario autenticado.

    Raises:
        UnauthorizedError: Si el token es inválido o usuario no existe.
    """
    token = credentials.credentials
    payload = verify_token(token)

    user = await user_repo.get_by_id(payload["user_id"])

    if not user or user.deleted:
        raise UnauthorizedError("Usuario no encontrado o deshabilitado")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Requiere rol de administrador."""
    if user.rol != "admin":
        raise ForbiddenError("Se requiere rol de administrador")
    return user


async def require_coordinador_or_admin(user: User = Depends(get_current_user)) -> User:
    """Requiere rol de coordinador o administrador."""
    if user.rol not in ("admin", "coordinador"):
        raise ForbiddenError("Se requiere rol de coordinador o administrador")
    return user
```

### 2.3 Almacenamiento en Frontend

```typescript
// shared/services/auth_service.ts

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

/**
 * Guarda el token y usuario en localStorage.
 */
export function saveAuth(token: string, user: User): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/**
 * Obtiene el token almacenado.
 */
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Obtiene el usuario almacenado.
 */
export function getUser(): User | null {
  const data = localStorage.getItem(USER_KEY);
  return data ? JSON.parse(data) : null;
}

/**
 * Limpia la sesión (logout).
 */
export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/**
 * Verifica si hay sesión activa.
 */
export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;

  // Verificar expiración del token (decodificar payload)
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}
```

---

## 3. Gestión de Contraseñas

### 3.1 Política de Contraseñas

| Requisito | Valor |
|-----------|-------|
| **Longitud mínima** | 8 caracteres |
| **Requisitos** | Al menos 1 número |
| **Historial** | No reutilizar últimas 3 contraseñas (opcional) |

**Validación:**
```python
# app/core/validators.py

import re
from app.core.exceptions import ValidationError

def validate_password(password: str) -> None:
    """
    Valida que la contraseña cumpla con la política.

    Args:
        password: Contraseña a validar.

    Raises:
        ValidationError: Si no cumple los requisitos.
    """
    if len(password) < 8:
        raise ValidationError(
            message="La contraseña debe tener al menos 8 caracteres",
            field="password"
        )

    if not re.search(r'\d', password):
        raise ValidationError(
            message="La contraseña debe contener al menos un número",
            field="password"
        )
```

### 3.2 Hash con bcrypt

```python
# app/core/security.py

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Genera hash bcrypt de la contraseña.

    Args:
        password: Contraseña en texto plano.

    Returns:
        Hash bcrypt.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica contraseña contra hash almacenado.

    Args:
        plain_password: Contraseña en texto plano.
        hashed_password: Hash almacenado en BD.

    Returns:
        True si coincide, False si no.
    """
    return pwd_context.verify(plain_password, hashed_password)
```

### 3.3 Primer Login - Cambio Obligatorio

Cuando el admin crea un usuario, se genera una contraseña temporal y se marca `first_login = True`.

```python
# app/services/user_service.py

import secrets
import string

def generate_temp_password(length: int = 12) -> str:
    """
    Genera contraseña temporal aleatoria.

    Args:
        length: Longitud de la contraseña.

    Returns:
        Contraseña temporal (incluye letras y números).
    """
    alphabet = string.ascii_letters + string.digits
    # Asegurar al menos un número
    password = ''.join(secrets.choice(alphabet) for _ in range(length - 1))
    password += secrets.choice(string.digits)
    return password


async def create_user(self, data: UserCreate) -> tuple[User, str]:
    """
    Crea un nuevo usuario con contraseña temporal.

    Args:
        data: Datos del usuario a crear.

    Returns:
        Tupla (usuario creado, contraseña temporal).
    """
    temp_password = generate_temp_password()

    user = User(
        username=data.username,
        nombre=data.nombre,
        password_hash=hash_password(temp_password),
        rol=data.rol,
        first_login=True  # Forzar cambio en primer login
    )

    await self.user_repo.create(user)

    return user, temp_password
```

**Flujo de Primer Login:**

```
1. Admin crea usuario con password temporal
   │
   ▼
2. Admin comunica credenciales al usuario (email, verbal, etc.)
   │
   ▼
3. Usuario hace login con password temporal
   │
   ▼
4. Backend detecta first_login=True
   │
   ▼
5. Frontend redirige a /change-password (obligatorio)
   │
   ▼
6. Usuario cambia contraseña
   │
   ▼
7. Backend marca first_login=False
   │
   ▼
8. Usuario puede acceder al sistema normalmente
```

---

## 4. Bloqueo de Cuenta

### 4.1 Lógica de Bloqueo

| Parámetro | Valor |
|-----------|-------|
| **Intentos máximos** | 5 |
| **Tiempo de bloqueo** | 15 minutos |
| **Desbloqueo** | Automático |

```python
# app/services/auth_service.py

from datetime import datetime, timedelta

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

async def login(self, username: str, password: str) -> LoginResponse:
    """
    Autentica un usuario verificando bloqueo.

    Args:
        username: Nombre de usuario.
        password: Contraseña.

    Returns:
        LoginResponse con token y datos del usuario.

    Raises:
        UnauthorizedError: Credenciales inválidas.
        ForbiddenError: Cuenta bloqueada.
    """
    user = await self.user_repo.get_by_username(username)

    if not user:
        raise UnauthorizedError("Credenciales inválidas")

    # Verificar si está bloqueado
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = (user.locked_until - datetime.utcnow()).seconds // 60
        raise ForbiddenError(
            f"Cuenta bloqueada. Intenta en {remaining} minutos."
        )

    # Verificar contraseña
    if not verify_password(password, user.password_hash):
        # Incrementar intentos fallidos
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
            await self.user_repo.update(user)
            raise ForbiddenError(
                f"Cuenta bloqueada por {LOCKOUT_DURATION.seconds // 60} minutos debido a múltiples intentos fallidos."
            )

        await self.user_repo.update(user)
        remaining = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        raise UnauthorizedError(
            f"Credenciales inválidas. {remaining} intentos restantes."
        )

    # Login exitoso: resetear contadores
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    await self.user_repo.update(user)

    # Generar token
    token = create_access_token(user.id, user.username, user.rol)

    return LoginResponse(
        token=token,
        user=user.to_public(),
        first_login=user.first_login
    )
```

### 4.2 Campos en Modelo Usuario

```python
# app/models/user.py

class User(Base):
    """Modelo de usuario."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))  # admin, coordinador, tutor

    # Seguridad
    first_login: Mapped[bool] = mapped_column(default=True)
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(nullable=True)

    # API Key Gemini (encriptada)
    gemini_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Soft delete
    deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

---

## 5. Encriptación de Datos Sensibles

### 5.1 Qué se Encripta

| Dato | Método | Ubicación |
|------|--------|-----------|
| **Contraseñas** | bcrypt hash | `password_hash` |
| **API Keys Gemini** | AES-256-CBC | `gemini_api_key_encrypted` |

### 5.2 Encriptación AES-256

```python
# app/core/encryption.py

from cryptography.fernet import Fernet
from app.core.config import settings

def get_fernet() -> Fernet:
    """Obtiene instancia de Fernet para encriptación."""
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_api_key(api_key: str) -> str:
    """
    Encripta una API Key para almacenamiento seguro.

    Args:
        api_key: API Key en texto plano.

    Returns:
        API Key encriptada (base64).
    """
    if not api_key:
        raise ValueError("API Key no puede estar vacía")

    fernet = get_fernet()
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Desencripta una API Key almacenada.

    Args:
        encrypted_key: API Key encriptada.

    Returns:
        API Key en texto plano.
    """
    if not encrypted_key:
        raise ValueError("API Key encriptada no puede estar vacía")

    fernet = get_fernet()
    return fernet.decrypt(encrypted_key.encode()).decode()
```

### 5.3 Generación de ENCRYPTION_KEY

```python
# Script de utilidad para generar key
from cryptography.fernet import Fernet

key = Fernet.generate_key()
print(f"ENCRYPTION_KEY={key.decode()}")

# Ejemplo de salida:
# ENCRYPTION_KEY=ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=
```

**Importante:** La `ENCRYPTION_KEY` debe:
- Almacenarse en variables de entorno (nunca en código)
- Ser única por ambiente (dev, staging, prod)
- Tener backup seguro (si se pierde, las API Keys no se pueden recuperar)

---

## 6. Rate Limiting

### 6.1 Configuración

| Endpoint | Límite | Ventana |
|----------|--------|---------|
| **Login** | 10 intentos | 15 minutos |
| **API general** | 100 requests | 1 minuto |
| **Corrección IA** | 20 requests | 1 minuto |
| **Cambio API Key** | 5 intentos | 1 hora |

### 6.2 Implementación

```python
# app/core/rate_limit.py

from fastapi import Request, HTTPException
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

class RateLimiter:
    """Rate limiter en memoria (usar Redis en producción para múltiples instancias)."""

    def __init__(self):
        self.requests: dict[str, list[datetime]] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Verifica si una request está permitida.

        Args:
            key: Identificador único (IP, user_id, etc.).
            max_requests: Máximo de requests permitidos.
            window_seconds: Ventana de tiempo en segundos.

        Returns:
            Tupla (permitido, requests restantes).
        """
        async with self.lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=window_seconds)

            # Limpiar requests antiguos
            self.requests[key] = [
                ts for ts in self.requests[key]
                if ts > window_start
            ]

            # Verificar límite
            current_count = len(self.requests[key])

            if current_count >= max_requests:
                return False, 0

            # Registrar nueva request
            self.requests[key].append(now)

            return True, max_requests - current_count - 1


rate_limiter = RateLimiter()


def rate_limit(max_requests: int, window_seconds: int):
    """
    Decorator para rate limiting en endpoints.

    Args:
        max_requests: Máximo de requests permitidos.
        window_seconds: Ventana de tiempo en segundos.
    """
    async def dependency(request: Request):
        # Usar IP como key (o user_id si está autenticado)
        key = f"{request.client.host}:{request.url.path}"

        allowed, remaining = await rate_limiter.is_allowed(
            key, max_requests, window_seconds
        )

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Demasiadas solicitudes. Intenta más tarde.",
                    "retry_after": window_seconds
                }
            )

        return remaining

    return dependency
```

### 6.3 Uso en Endpoints

```python
# app/api/v1/routers/auth_router.py

from app.core.rate_limit import rate_limit

@router.post("/login")
async def login(
    data: LoginRequest,
    _: int = Depends(rate_limit(max_requests=10, window_seconds=900))  # 10 en 15 min
):
    """Endpoint de login con rate limiting."""
    pass


@router.post("/entregas/{id}/corregir")
async def corregir(
    id: int,
    _: int = Depends(rate_limit(max_requests=20, window_seconds=60))  # 20 por minuto
):
    """Corrección con rate limiting."""
    pass
```

---

## 7. Validación de Uploads

### 7.1 Validaciones Aplicadas

| Validación | Descripción |
|------------|-------------|
| **Extensión** | Solo `.zip`, `.txt` permitidos |
| **MIME Type** | Verificar que coincida con extensión |
| **Tamaño** | Máximo 100 MB |
| **Nombre** | Sanitizar caracteres especiales |

### 7.2 Implementación

```python
# app/core/file_validators.py

import magic
from pathlib import Path
from app.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {".zip", ".txt"}
ALLOWED_MIME_TYPES = {
    ".zip": ["application/zip", "application/x-zip-compressed"],
    ".txt": ["text/plain"]
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def validate_upload(file_path: str, original_filename: str, file_size: int) -> None:
    """
    Valida un archivo subido.

    Args:
        file_path: Ruta temporal del archivo.
        original_filename: Nombre original del archivo.
        file_size: Tamaño en bytes.

    Raises:
        ValidationError: Si el archivo no pasa las validaciones.
    """
    # Validar extensión
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            message=f"Extensión no permitida. Solo se aceptan: {', '.join(ALLOWED_EXTENSIONS)}",
            field="file"
        )

    # Validar tamaño
    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        raise ValidationError(
            message=f"El archivo excede el tamaño máximo de {max_mb} MB",
            field="file"
        )

    # Validar MIME type real (no confiar en el header)
    mime = magic.from_file(file_path, mime=True)
    allowed_mimes = ALLOWED_MIME_TYPES.get(extension, [])

    if mime not in allowed_mimes:
        raise ValidationError(
            message=f"El contenido del archivo no coincide con la extensión {extension}",
            field="file"
        )


def sanitize_filename(filename: str) -> str:
    """
    Sanitiza nombre de archivo para almacenamiento seguro.

    Args:
        filename: Nombre original.

    Returns:
        Nombre sanitizado.
    """
    # Remover caracteres peligrosos
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    sanitized = "".join(c if c in safe_chars else "_" for c in filename)

    # Evitar nombres que empiecen con punto (archivos ocultos)
    if sanitized.startswith("."):
        sanitized = "_" + sanitized[1:]

    return sanitized[:255]  # Limitar longitud
```

---

## 8. Seguridad de Webhooks N8N

### 8.1 Header Authentication

El backend incluye un header secreto en cada request a N8N, y N8N lo valida.

**Backend (envía el secret):**
```python
# app/services/n8n_service.py

import httpx
from app.core.config import settings

async def call_n8n_webhook(
    webhook_path: str,
    payload: dict
) -> dict:
    """
    Llama a un webhook de N8N con autenticación.

    Args:
        webhook_path: Path del webhook (ej: "/corregir").
        payload: Datos a enviar.

    Returns:
        Respuesta del webhook.
    """
    url = f"{settings.N8N_BASE_URL}/webhook{webhook_path}"

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
```

**N8N (valida el secret):**

En el workflow de N8N, agregar un nodo "IF" después del Webhook:

```javascript
// Nodo IF - Condition
// Validar que el header X-Webhook-Secret coincida

const expectedSecret = $env.WEBHOOK_SECRET;  // Variable de entorno en N8N
const receivedSecret = $input.first().headers['x-webhook-secret'];

return receivedSecret === expectedSecret;
```

**Variables de Entorno:**
```bash
# Backend .env
N8N_WEBHOOK_SECRET=mi-secreto-super-seguro-de-32-chars

# N8N environment
WEBHOOK_SECRET=mi-secreto-super-seguro-de-32-chars
```

### 8.2 Red Interna Docker (Defensa en Profundidad)

Además del header auth, los webhooks solo son accesibles desde la red interna de Docker:

```yaml
# docker-compose.yml

services:
  backend:
    networks:
      - internal
      - external

  n8n:
    networks:
      - internal  # Solo red interna, no expuesto a internet
    # ports:
    #   - "5678:5678"  # NO exponer en producción

networks:
  internal:
    internal: true  # Red aislada
  external:
```

---

## 9. Logging de Auditoría

### 9.1 Eventos Auditados

| Evento | Datos Registrados |
|--------|-------------------|
| **Login exitoso** | user_id, username, IP, timestamp |
| **Login fallido** | username intentado, IP, timestamp, razón |
| **Logout** | user_id, timestamp |
| **Cambio de password** | user_id, timestamp |
| **Creación de usuario** | admin_id, nuevo_user_id, rol asignado |
| **Eliminación de usuario** | admin_id, user_id eliminado |
| **Corrección editada** | user_id, entrega_id, campos modificados |
| **API Key configurada** | user_id, timestamp (NO loggear la key) |

### 9.2 Modelo de Audit Log

```python
# app/models/audit_log.py

from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.db.base import Base
from datetime import datetime

class AuditLog(Base):
    """Registro de auditoría de acciones sensibles."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Quién
    user_id = Column(Integer, nullable=True)  # Null para acciones anónimas (login fallido)
    username = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible

    # Qué
    action = Column(String(50), nullable=False)  # LOGIN, LOGOUT, PASSWORD_CHANGE, etc.
    resource_type = Column(String(50), nullable=True)  # USER, ENTREGA, CORRECCION
    resource_id = Column(Integer, nullable=True)

    # Detalles
    details = Column(JSON, nullable=True)  # Datos adicionales específicos del evento
    status = Column(String(20), nullable=False)  # SUCCESS, FAILURE
```

### 9.3 Servicio de Auditoría

```python
# app/services/audit_service.py

from app.models.audit_log import AuditLog
from app.repositories.audit_repository import AuditRepository

class AuditService:
    """Servicio para registrar eventos de auditoría."""

    def __init__(self, audit_repo: AuditRepository):
        self.audit_repo = audit_repo

    async def log_login_success(
        self,
        user_id: int,
        username: str,
        ip_address: str
    ) -> None:
        """Registra login exitoso."""
        await self.audit_repo.create(AuditLog(
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            action="LOGIN",
            status="SUCCESS"
        ))

    async def log_login_failure(
        self,
        username: str,
        ip_address: str,
        reason: str
    ) -> None:
        """Registra intento de login fallido."""
        await self.audit_repo.create(AuditLog(
            username=username,
            ip_address=ip_address,
            action="LOGIN",
            status="FAILURE",
            details={"reason": reason}
        ))

    async def log_password_change(
        self,
        user_id: int,
        username: str,
        ip_address: str
    ) -> None:
        """Registra cambio de contraseña."""
        await self.audit_repo.create(AuditLog(
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            action="PASSWORD_CHANGE",
            resource_type="USER",
            resource_id=user_id,
            status="SUCCESS"
        ))

    async def log_correction_edited(
        self,
        user_id: int,
        username: str,
        entrega_id: int,
        campos_modificados: list[str]
    ) -> None:
        """Registra edición de corrección."""
        await self.audit_repo.create(AuditLog(
            user_id=user_id,
            username=username,
            action="CORRECTION_EDIT",
            resource_type="CORRECCION",
            resource_id=entrega_id,
            status="SUCCESS",
            details={"campos_modificados": campos_modificados}
        ))
```

---

## 10. CORS (Cross-Origin Resource Sharing)

### 10.1 Configuración

```python
# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["http://localhost:3000", "https://midominio.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### 10.2 Variables de Entorno

```bash
# Desarrollo
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# Producción
CORS_ORIGINS=["https://active-ia.midominio.com"]
```

---

## 11. Headers de Seguridad

### 11.1 Configuración Nginx

```nginx
# nginx.conf

server {
    listen 80;
    server_name _;

    # Headers de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;

    # HTTPS redirect (en producción)
    # return 301 https://$host$request_uri;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 12. Variables de Entorno Sensibles

### 12.1 Lista de Secrets

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SECRET_KEY` | Key para firmar JWT | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | Key para encriptar API Keys | `Fernet.generate_key()` |
| `DATABASE_URL` | Connection string BD | `postgresql://...` |
| `N8N_WEBHOOK_SECRET` | Secret para webhooks | `openssl rand -hex 16` |

### 12.2 Nunca Commitear

Archivos que NUNCA deben estar en el repositorio:

```gitignore
# .gitignore

# Variables de entorno
.env
.env.local
.env.production

# Keys
*.key
*.pem

# Datos de N8N
n8n/data/

# Uploads
uploads/
```

### 12.3 Ejemplo de .env

```bash
# .env.example (este SÍ se commitea, sin valores reales)

# Base de datos
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/activeai

# Seguridad
SECRET_KEY=change-me-in-production
ENCRYPTION_KEY=change-me-in-production

# JWT
JWT_EXPIRE_DAYS=7

# N8N
N8N_BASE_URL=http://n8n:5678
N8N_WEBHOOK_SECRET=change-me-in-production

# CORS
CORS_ORIGINS=["http://localhost:3000"]
```

---

## 13. Resumen de Decisiones

| Aspecto | Decisión |
|---------|----------|
| **Autenticación** | JWT con HS256, 7 días expiración |
| **Token storage** | localStorage |
| **Passwords** | bcrypt + mínimo 8 chars + 1 número |
| **Primer login** | Forzar cambio de password temporal |
| **Bloqueo** | 5 intentos → 15 min bloqueo automático |
| **Encriptación** | AES-256 (Fernet) solo para API Keys |
| **Auditoría** | Log de acciones críticas |
| **Uploads** | Validar extensión + MIME + tamaño (100MB) |
| **Webhooks** | Header X-Webhook-Secret + red interna |
| **Rate limiting** | Por IP, configurable por endpoint |

---

## 14. Checklist de Seguridad Pre-Deploy

Antes de desplegar a producción:

- [ ] `SECRET_KEY` generado con `openssl rand -hex 32`
- [ ] `ENCRYPTION_KEY` generado con `Fernet.generate_key()`
- [ ] `N8N_WEBHOOK_SECRET` configurado en backend y N8N
- [ ] CORS configurado solo con dominios permitidos
- [ ] HTTPS habilitado (certificado SSL)
- [ ] N8N no expuesto a internet (solo red interna)
- [ ] `.env` no commiteado en repositorio
- [ ] Rate limiting configurado para endpoints sensibles
- [ ] Logs de auditoría funcionando
- [ ] Backup de `ENCRYPTION_KEY` en lugar seguro

---

*Documento parte de la especificación de Active-IA*
*Versión: 1.0*
*Fecha: Enero 2026*
