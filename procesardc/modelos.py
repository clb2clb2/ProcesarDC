"""Estructuras de datos compartidas."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path

from .normalizacion import CENTIMOS, id_numerico_jg


@dataclass
class PdfPageData:
    """Datos extraidos de una pagina del PDF de Justificantes de Pago (JP)."""

    source_name: str
    page_number: int
    fecha: str
    importe: Decimal | None
    factura: str
    beneficiario: str
    concepto: str


@dataclass
class ExcelRowData:
    """Fila valida del Excel de UXXI de Justificantes de Gasto (JG)."""

    row_number: int
    jg: str
    fecha: str
    importe_total: Decimal | None
    importe_retencion: Decimal | None
    factura: str
    beneficiario: str
    concepto: str

    @property
    def importe_neto(self) -> Decimal | None:
        if self.importe_total is None or self.importe_retencion is None:
            return None
        return (self.importe_total - self.importe_retencion).quantize(CENTIMOS)


class Estado(str, Enum):
    """Resultado del cruce exacto de una pagina JP con el Excel."""

    ENCONTRADO = "found"  # una sola fila coincide
    NO_ENCONTRADO = "not_found"  # ninguna fila coincide
    DUDOSO = "dubious"  # varias filas coinciden


class Resaltado(str, Enum):
    VERDE = "green"  # coincidencia exacta confirmada por el JG probable
    ROJO = "red"  # requiere revision
    NINGUNO = ""


@dataclass
class Discrepancia:
    campo: str
    pdf: str
    excel: str


@dataclass
class ResultadoCruce:
    """Resultado del cruce de una pagina JP, con la asignacion manual del usuario."""

    pagina: PdfPageData
    estado: Estado
    resaltado: Resaltado
    jg_automatico: str = ""
    candidatos: list[str] = field(default_factory=list)
    jg_probable: str = ""
    origen_probable: str = ""  # "factura" | "concepto" | ""
    discrepancias: list[Discrepancia] = field(default_factory=list)
    jg_manual: str = ""

    @property
    def clave(self) -> str:
        return f"{self.pagina.source_name}::{self.pagina.page_number}"

    @property
    def jg_efectivo(self) -> str:
        """El JG que se usa: el manual si lo hay; si no, el automatico."""
        return self.jg_manual or self.jg_automatico

    @property
    def id_jg(self) -> str:
        """Identificador numerico del JG efectivo ("" si no hay o no es numerico)."""
        return id_numerico_jg(self.jg_efectivo)

    @property
    def requiere_revision(self) -> bool:
        return self.resaltado is Resaltado.ROJO or self.estado is not Estado.ENCONTRADO


@dataclass
class OriginSection:
    """Seccion de un PDF origen (por marcador) o PDF origen copiado tal cual."""

    source_path: Path
    title: str
    start_page: int | None
    end_page: int | None
    is_numeric: bool
    numeric_id: str
    category: str
    from_marker: bool
