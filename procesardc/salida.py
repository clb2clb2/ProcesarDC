"""Generacion de la carpeta de salida de un Documento Contable.

Se trabaja en dos fases:
1. `planificar`: decide que fichero se genera a partir de cada seccion (sin tocar el disco).
2. `generar`: escribe todo en una carpeta temporal junto al destino y, solo si no ha
   fallado nada, mueve los ficheros a la carpeta destino. Un error a mitad no deja
   ficheros sueltos en el destino.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from .modelos import OriginSection

PREFIJO_TEMPORAL = ".procesardc_"


@dataclass
class PlanSalida:
    carpeta: Path
    copias: list[tuple[Path, Path]] = field(default_factory=list)
    extracciones: list[tuple[OriginSection, Path]] = field(default_factory=list)

    @property
    def destinos(self) -> list[Path]:
        return [dst for _, dst in self.copias] + [dst for _, dst in self.extracciones]

    def duplicados(self) -> list[Path]:
        """Destinos repetidos (sin distinguir mayusculas, como en Windows)."""
        vistos: dict[str, int] = {}
        duplicados: list[Path] = []
        for path in self.destinos:
            clave = str(path.resolve()).lower()
            vistos[clave] = vistos.get(clave, 0) + 1
            if vistos[clave] == 2:
                duplicados.append(path)
        return duplicados

    def existentes(self) -> list[Path]:
        return [p for p in self.destinos if p.exists()]

    def ids_jg(self) -> set[str]:
        return {s.numeric_id for s, _ in self.extracciones if s.is_numeric and s.numeric_id}


def nombre_carpeta(anio: str, dc: int, tipo_documento: str) -> str:
    """"2026", 1234, "Remesa INV" -> "2026000001234 (REMESA INV)"."""
    return f"{anio}{dc:09d} ({tipo_documento.strip().upper()})"


def nombre_seguro(value: str) -> str:
    """Titulo de marcador convertido en nombre de fichero valido en Windows."""
    stem = re.sub(r"[\\/:*?\"<>|]", "_", str(value or "").strip())
    stem = stem.rstrip(". ")
    return stem or "SECCION"


def planificar(carpeta: Path, secciones: list[OriginSection], dc: int, cj: int) -> PlanSalida:
    plan = PlanSalida(carpeta=carpeta)
    for section in secciones:
        if section.is_numeric:
            nombre = f"JG{section.numeric_id}.pdf"
        elif section.category == "DC":
            nombre = f"DC{dc}.pdf"
        elif section.category == "CJ":
            nombre = f"CJ{cj}.pdf"
        elif section.from_marker:
            nombre = f"{nombre_seguro(section.title)}.pdf"
        else:
            nombre = section.source_path.name

        destino = carpeta / nombre
        if section.from_marker:
            plan.extracciones.append((section, destino))
        else:
            plan.copias.append((section.source_path, destino))
    return plan


def generar(
    plan: PlanSalida,
    jp_pdf: Path | None = None,
    paginas_jp_por_jg: dict[str, list[int]] | None = None,
) -> None:
    """Escribe la salida del plan, anadiendo al final de cada JG sus paginas JP (1-based)."""
    paginas_jp_por_jg = paginas_jp_por_jg or {}
    _comprobar_paginas_jp(plan, jp_pdf, paginas_jp_por_jg)

    plan.carpeta.parent.mkdir(parents=True, exist_ok=True)
    temporal = Path(tempfile.mkdtemp(prefix=PREFIJO_TEMPORAL, dir=plan.carpeta.parent))
    try:
        _escribir(plan, temporal, jp_pdf, paginas_jp_por_jg)
        _instalar(temporal, plan.carpeta)
    finally:
        shutil.rmtree(temporal, ignore_errors=True)


def _comprobar_paginas_jp(plan: PlanSalida, jp_pdf: Path | None, paginas_jp_por_jg: dict[str, list[int]]) -> None:
    if not paginas_jp_por_jg:
        return
    if jp_pdf is None:
        raise ValueError("Falta el PDF de justificantes de pago")

    ids_jg = plan.ids_jg()
    total = len(PdfReader(str(jp_pdf)).pages)
    for numeric_id, paginas in paginas_jp_por_jg.items():
        if numeric_id not in ids_jg:
            raise ValueError(f"No existe archivo JG para el identificador {numeric_id}")
        for pagina in paginas:
            if pagina < 1 or pagina > total:
                raise ValueError(f"Pagina JP fuera de rango: {pagina}")


def _escribir(
    plan: PlanSalida, temporal: Path, jp_pdf: Path | None, paginas_jp_por_jg: dict[str, list[int]]
) -> None:
    for origen, destino in plan.copias:
        shutil.copy2(origen, temporal / destino.name)

    readers: dict[Path, PdfReader] = {}

    def reader(path: Path) -> PdfReader:
        clave = path.resolve()
        if clave not in readers:
            readers[clave] = PdfReader(str(path))
        return readers[clave]

    for section, destino in plan.extracciones:
        if section.start_page is None or section.end_page is None:
            continue

        writer = PdfWriter()
        origen = reader(section.source_path)
        for page_idx in range(section.start_page, section.end_page):
            writer.add_page(origen.pages[page_idx])

        if section.is_numeric and jp_pdf is not None:
            jp = reader(jp_pdf)
            for pagina in paginas_jp_por_jg.get(section.numeric_id, []):
                writer.add_page(jp.pages[pagina - 1])

        with open(temporal / destino.name, "wb") as fh:
            writer.write(fh)


def _instalar(temporal: Path, carpeta: Path) -> None:
    """Mueve los ficheros generados a la carpeta destino, sustituyendo los que ya existan."""
    if not carpeta.exists():
        os.replace(temporal, carpeta)
        return

    for fichero in temporal.iterdir():
        os.replace(fichero, carpeta / fichero.name)
