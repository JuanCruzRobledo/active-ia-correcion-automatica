# app/models/correccion.py
"""
Correccion model for Active-IA.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3.8
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import ARRAY, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.entrega import Entrega
    from app.models.usuario import Usuario


class Correccion(Base, TimestampMixin):
    """
    Corrección de una entrega.

    Almacena el resultado de la evaluación de una entrega, ya sea
    generada automáticamente por IA (Gemini) o editada manualmente
    por un tutor.

    Relación 1:1 con Entrega (una entrega tiene máximo una corrección).

    Estructura de criterios_json:
    {
        "criterios": [
            {
                "id": "c1",
                "nombre": "Funcionalidad correcta",
                "puntaje_obtenido": 35,
                "puntaje_maximo": 40,
                "estado": "WARNING",
                "feedback": "Error en el manejo de lista vacía..."
            },
            ...
        ]
    }
    """

    __tablename__ = "correcciones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entrega_id: Mapped[int] = mapped_column(
        ForeignKey("entregas.id"),
        unique=True,
        nullable=False,
    )
    nota: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )  # 0.00 - 100.00
    criterios_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    fortalezas: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        default=list,
        server_default="{}",
    )
    recomendaciones: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        default=list,
        server_default="{}",
    )
    comentario_general: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    editado_manualmente: Mapped[bool] = mapped_column(
        default=False,
    )
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    corregido_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"),
        nullable=True,
    )

    # Relationships
    entrega: Mapped["Entrega"] = relationship(
        "Entrega",
        back_populates="correccion",
    )
    corregido_por: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="correcciones_realizadas",
    )

    def __repr__(self) -> str:
        return f"<Correccion(id={self.id}, entrega_id={self.entrega_id}, nota={self.nota})>"
