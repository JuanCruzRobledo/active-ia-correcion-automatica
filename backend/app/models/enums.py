# app/models/enums.py
"""
Enumerations for Active-IA models.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3
"""

from enum import Enum


class RolEnum(str, Enum):
    """Roles de usuario en el sistema."""

    ADMIN = "ADMIN"
    COORDINADOR = "COORDINADOR"
    TUTOR = "TUTOR"


class TipoRubricaEnum(str, Enum):
    """Tipos de rúbrica de evaluación."""

    TP = "TP"
    PARCIAL_1 = "PARCIAL_1"
    PARCIAL_2 = "PARCIAL_2"
    RECUPERATORIO_1 = "RECUPERATORIO_1"
    RECUPERATORIO_2 = "RECUPERATORIO_2"
    FINAL = "FINAL"
    GLOBAL = "GLOBAL"


class EstadoEntregaEnum(str, Enum):
    """Estados posibles de una entrega."""

    SUBIDA = "SUBIDA"  # Archivo cargado, sin corregir
    PENDIENTE = "PENDIENTE"  # En proceso de corrección
    CORREGIDA = "CORREGIDA"  # Corrección completada
    ERROR = "ERROR"  # Falló el proceso


class FuenteRubricaEnum(str, Enum):
    """Fuente de creación de la rúbrica."""

    MANUAL = "manual"
    PDF = "pdf"


class EstadoCriterioEnum(str, Enum):
    """Estados de evaluación de un criterio."""

    OK = "OK"  # Criterio cumplido satisfactoriamente
    WARNING = "WARNING"  # Criterio con observaciones menores
    ERROR = "ERROR"  # Criterio con problemas significativos
