# app/services/moodle_credentials_resolver.py
"""
Resolver de credenciales Moodle compartido por los services (Fase 3 multi-tenant).

Único punto donde un service traduce el resultado del repo
(`UsuarioRepository.get_credenciales_moodle`) en la terna
`(host, username, password_encrypted)` lista para `MoodleService.get_token`, o
en el fail-fast HTTPException correspondiente. Evita repetir la lógica de
"de dónde salen los bytes" + los códigos de error en cada uno de los ~10
services que hablan con Moodle (D2).

Fail-fast (D1, D2, OQ5) — SIN fallback al viejo `usuarios.moodle_host`:
- `universidad_id is None` (superadmin sin universidad activa elegida, OQ5)
  -> 409, pedí elegir universidad.
- Sin membresía activa, o membresía sin `moodle_username`/`password_encrypted`
  -> 424, "Configurá tus credenciales Moodle en tu perfil".
- `moodle_host` de la universidad activa NULL/vacío (OP-1) -> 424, "El campus
  Moodle de tu universidad no está configurado; contactá al administrador".

Ref: openspec/changes/multi-tenant-moodle-services/design.md (D1, D2, OQ5)
Ref: openspec/changes/multi-tenant-moodle-services/specs/moodle-credenciales-por-universidad/spec.md
"""

from fastapi import HTTPException, status

from app.repositories.usuario_repository import UsuarioRepository

MSG_SIN_UNIVERSIDAD_ACTIVA = "Elegí una universidad activa para operar con Moodle"
MSG_SIN_CREDENCIALES = "Configurá tus credenciales Moodle en tu perfil"
MSG_CAMPUS_NO_CONFIGURADO = (
    "El campus Moodle de tu universidad no está configurado; contactá al administrador"
)


async def resolver_credenciales_moodle(
    usuario_repo: UsuarioRepository,
    usuario_id: int,
    universidad_id: int | None,
) -> tuple[str, str, str]:
    """
    Resuelve `(moodle_host, moodle_username, moodle_password_encrypted)` de la
    universidad activa, o falla-rápido con el `HTTPException` accionable.

    Args:
        usuario_repo: Repositorio de usuarios (ARCH-001: el acceso a datos
            vive en el repo; este helper es capa service, no ejecuta SQL).
        usuario_id: ID del usuario autenticado.
        universidad_id: `ctx.universidad_id` de la universidad activa del
            request (puede ser `None` para un superadmin sin universidad
            elegida, OQ5).

    Returns:
        Tupla `(host, username, password_encrypted)`, ya lista para
        `MoodleService.get_token`.

    Raises:
        HTTPException 409: sin universidad activa elegida (OQ5).
        HTTPException 424: sin membresía/credenciales, o host NULL/vacío
            (OP-1) — nunca cae al `usuarios.moodle_host` viejo (D1).
    """
    if universidad_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=MSG_SIN_UNIVERSIDAD_ACTIVA,
        )

    creds = await usuario_repo.get_credenciales_moodle(usuario_id, universidad_id)
    if creds is None or not creds.username or not creds.password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=MSG_SIN_CREDENCIALES,
        )
    if not creds.host:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=MSG_CAMPUS_NO_CONFIGURADO,
        )

    return creds.host, creds.username, creds.password_encrypted
