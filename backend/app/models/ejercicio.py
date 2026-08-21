# app/models/ejercicio.py
"""
Ejercicio model for Active-IA.

Change: `trabajos-practicos-y-external-ref`.

Un ejercicio es la **unidad de corrección**: se corrige contra su propia rúbrica
y devuelve su propia nota. Es lo que permite corregir un TP de a un ejercicio, y
con eso desaparece por construcción el modo de fallo del motor donde una pieza
del ejercicio 3 cuenta como cumplimiento de un criterio del 1.

Notas de diseño:

- **`materia_id` va denormalizado** además de `trabajo_practico_id`. El contrato
  pide que `external_ref` sea único *por materia*, y sin la denormalización esa
  unicidad necesitaría un join en cada validación. Es el mismo criterio con el
  que el proyecto denormaliza `universidad_id`.
- **La FK del vínculo con la rúbrica vive en `rubricas.ejercicio_id`**, no acá
  (design D2). Poniéndola de ese lado, la condición del índice parcial que exime
  a las rúbricas de ejercicio de `uq_rubrica_materia_tipo_numero_anio` se evalúa
  sobre la propia tabla `rubricas`, sin joins.
- **`peso` NO se valida contra ningún total** (design D7). El cliente dijo
  explícitamente que Active-IA no calcula la nota final del TP: el promedio
  ponderado lo hace él. Acá el peso es metadata de contexto, no input de cálculo.
- **`test_cases` NO son para ejecutar.** Active-IA no ejecuta código, nunca.
  Viajan porque son parte del enunciado: que un caso espere que pidiendo cupo 1
  entren 2 personas le dice al motor cuál es la regla de negocio. Los casos con
  `es_publico: false` se almacenan SIN `salida_esperada` ni `asercion` — lo que
  el motor nunca recibe no lo puede citar en un PDF que el alumno lee.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.materia import Materia
    from app.models.rubrica import Rubrica
    from app.models.trabajo_practico import TrabajoPractico


class Ejercicio(Base, TimestampMixin, SoftDeleteMixin):
    """Ejercicio de un trabajo práctico. Unidad de corrección."""

    __tablename__ = "ejercicios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    trabajo_practico_id: Mapped[int] = mapped_column(
        ForeignKey("trabajos_practicos.id"),
        nullable=False,
        index=True,
    )
    # Denormalizada: la unicidad de `external_ref` es POR MATERIA.
    materia_id: Mapped[int] = mapped_column(
        ForeignKey("materias.id"),
        nullable=False,
        index=True,
    )
    universidad_id: Mapped[int] = mapped_column(
        ForeignKey("universidades.id"),
        nullable=False,
        index=True,
    )
    external_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    enunciado_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    peso: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("1.00"),
        server_default=text("1.00"),
        comment="Peso relativo dentro del TP. Metadata: Active-IA no calcula la nota del TP.",
    )
    test_cases: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment=(
            "Casos de prueba como parte del enunciado. NO se ejecutan. "
            "Los casos no públicos no conservan salida_esperada ni asercion."
        ),
    )

    __table_args__ = (
        Index(
            "uq_ejercicio_materia_external_ref",
            "materia_id",
            "external_ref",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    # Relationships
    trabajo_practico: Mapped["TrabajoPractico"] = relationship(
        "TrabajoPractico",
        back_populates="ejercicios",
    )
    materia: Mapped["Materia"] = relationship("Materia")
    # 1:1 — la unicidad la fuerza el índice único sobre `rubricas.ejercicio_id`.
    rubrica: Mapped["Rubrica | None"] = relationship(
        "Rubrica",
        back_populates="ejercicio",
        uselist=False,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Ejercicio(id={self.id}, orden={self.orden}, "
            f"titulo='{self.titulo}', external_ref='{self.external_ref}')>"
        )
