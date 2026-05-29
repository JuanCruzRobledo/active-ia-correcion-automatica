# app/services/devolucion_link_service.py
"""
DevolucionLinkService — genera y valida tokens firmados para el PDF de devolución.

El endpoint público /api/v1/public/devoluciones/{token} permite que un alumno abra
su PDF desde Moodle SIN sesión de Active-IA. El token es un JWT firmado con SECRET_KEY
que codifica {tipo: 'devolucion', correccion_id, exp}, con expiración acotada.

Seguridad (PLAN_FEAT.md §7.3): cada token apunta a UNA sola corrección → no expone
datos de otros alumnos. Firma HMAC + expiración. Sin JWT de usuario.

Ref: PLAN_FEAT.md §5.7, §7.3
"""

from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings

TIPO_DEVOLUCION = "devolucion"
DEFAULT_TTL_DIAS = 90


class TokenDevolucionInvalido(Exception):
    """El token de devolución es inválido, expiró o no corresponde a una devolución."""


class DevolucionLinkService:
    """Genera/valida tokens firmados para acceso público al PDF de devolución."""

    @staticmethod
    def generar_token(correccion_id: int, ttl_dias: int = DEFAULT_TTL_DIAS) -> str:
        expire = datetime.utcnow() + timedelta(days=ttl_dias)
        payload = {
            "tipo": TIPO_DEVOLUCION,
            "correccion_id": correccion_id,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def validar_token(token: str) -> int:
        """Valida el token y devuelve el correccion_id. Lanza TokenDevolucionInvalido si falla."""
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
        except JWTError as e:
            raise TokenDevolucionInvalido(f"Token inválido o expirado: {e}") from e

        if payload.get("tipo") != TIPO_DEVOLUCION:
            raise TokenDevolucionInvalido("El token no es de tipo devolución")

        correccion_id = payload.get("correccion_id")
        if not isinstance(correccion_id, int):
            raise TokenDevolucionInvalido("El token no contiene un correccion_id válido")
        return correccion_id

    @staticmethod
    def generar_path(correccion_id: int, ttl_dias: int = DEFAULT_TTL_DIAS) -> str:
        """Path relativo del endpoint público. El host absoluto lo antepone el caller."""
        token = DevolucionLinkService.generar_token(correccion_id, ttl_dias)
        return f"/api/v1/public/devoluciones/{token}"
