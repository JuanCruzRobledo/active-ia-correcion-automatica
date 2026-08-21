# app/models/trabajo_practico.py
"""
TrabajoPractico model for Active-IA.

Change: `trabajos-practicos-y-external-ref`.

Agrupa N ejercicios bajo una materia. Es lo que AI-Native llama "TP" y lo que en
el flujo de Moodle sería una unidad. La unidad de CORRECCIÓN, en cambio, es el
`Ejercicio`: se corrige de a uno contra su propia rúbrica, que es lo que
desactiva el modo de fallo "distingue presencia, no vínculo" del motor.

`external_ref` es el identificador que provee el sistema cliente. Es una cadena
OPACA: Active-IA la guarda y la compara, nunca la interpreta. Se declara
`String(64)` y no `UUID` nativo a propósito — atarse al tipo de Postgres cerraría
la puerta a un cliente que use otro formato de identificador.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ejercicio import Ejercicio
    from app.models.materia import Materia


class TrabajoPractico(Base, TimestampMixin, SoftDeleteMixin):
    """Trabajo práctico compuesto por uno o más ejercicios."""

    __tablename__ = "trabajos_practicos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
        index=True,
    )
    # Denormalizada desde materia.universidad_id, como en el resto de las
    # entidades scopeadas del proyecto (rubricas, entregas, correcciones).
    universidad_id: Mapped[int] = mapped_column(
        ForeignKey("universidades.id"),
        nullable=False,
        index=True,
    )
    # NOT NULL: un TP nace de la integración; sin identificador externo no tiene
    # para qué existir. (En `Materia` sí es opcional: las de Moodle no tienen.)
    external_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Parcial sobre no borrados: un TP dado de baja no debe bloquear la
        # republicación de otro con el mismo identificador externo. Mismo patrón
        # que `uq_entrega_rubrica_alumno`.
        Index(
            "uq_trabajo_practico_materia_external_ref",
            "materia_id",
            "external_ref",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    # Relationships
    materia: Mapped["Materia"] = relationship(
        "Materia",
        back_populates="trabajos_practicos",
    )
    ejercicios: Mapped[list["Ejercicio"]] = relationship(
        "Ejercicio",
        back_populates="trabajo_practico",
        lazy="selectin",
        order_by="Ejercicio.orden",
    )

    def __repr__(self) -> str:
        return (
            f"<TrabajoPractico(id={self.id}, titulo='{self.titulo}', "
            f"external_ref='{self.external_ref}')>"
        )
