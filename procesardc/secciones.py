"""Escaneo de los PDFs origen: secciones por marcador o PDFs copiados tal cual.

Reglas:
- Un PDF cuyo nombre empieza por DC/CJ/RT + digitos se trata como archivo directo
  (se ignoran sus marcadores internos).
- Un PDF sin marcadores tambien es archivo directo, con su nombre como titulo.
- Si tiene marcadores, cada marcador abre una seccion hasta el siguiente marcador.
  Los titulos numericos son JG; los demas se clasifican como DC/CJ/RT/OTHER.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from .modelos import OriginSection
from .normalizacion import normalizar_texto

ERROR_VARIOS_DC = "¡Atención! Debes cargar un solo archivo de Documento Contable (DC)."
ERROR_VARIOS_CJ = "¡Atención! Debes cargar un solo archivo de Cuenta Justificativa (CJ)."
ERROR_CONFLICTO = (
    "¡Atención! Hay marcadores o archivos en conflicto "
    "(duplicados entre secciones extraídas y/o archivos directos)."
)
ERROR_DC_NO_UNICO = "Debe haber exactamente un archivo o sección de Documento Contable (DC)"
ERROR_CJ_NO_UNICO = "Debe haber exactamente un archivo o sección de Cuenta Justificativa (CJ)"


@dataclass
class EscaneoOrigen:
    """Resultado de escanear una seleccion de PDFs origen."""

    secciones: list[OriginSection] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    def de_categoria(self, categoria: str) -> list[OriginSection]:
        return [s for s in self.secciones if not s.is_numeric and s.category == categoria]

    @property
    def ids_jg(self) -> set[str]:
        return {s.numeric_id for s in self.secciones if s.is_numeric and s.numeric_id}

    @property
    def otros(self) -> list[str]:
        return [s.title for s in self.de_categoria("OTHER")]

    def numero_con_prefijo(self, prefijo: str) -> str:
        """Numero de la primera seccion no numerica cuyo titulo empieza por prefijo+digitos."""
        for section in self.secciones:
            if section.is_numeric:
                continue
            numero = numero_con_prefijo(section.title, prefijo)
            if numero:
                return numero
        return ""


def escanear_origen(files: list[Path]) -> EscaneoOrigen:
    escaneo = EscaneoOrigen()

    for pdf_path in files:
        if es_nombre_con_prefijo(pdf_path.stem):
            escaneo.secciones.append(_archivo_directo(pdf_path))
            continue

        try:
            reader = PdfReader(str(pdf_path))
            entries = _entradas_marcadores(reader, reader.outline)
        except Exception as exc:
            escaneo.errores.append(f"No se pudo leer el PDF de origen '{pdf_path.name}': {exc}")
            continue

        if not entries:
            if pdf_path.stem.strip():
                escaneo.secciones.append(_archivo_directo(pdf_path))
            continue

        total_pages = len(reader.pages)
        entries_sorted = sorted(entries, key=lambda it: (it[1], it[2]))
        for idx, (title_raw, start_page, _order) in enumerate(entries_sorted):
            end_page = entries_sorted[idx + 1][1] if idx + 1 < len(entries_sorted) else total_pages
            # Marcadores fuera de rango o que comparten pagina con el siguiente: se ignoran.
            if start_page < 0 or end_page > total_pages or start_page >= end_page:
                continue

            title = normalizar_titulo(title_raw)
            if not title:
                continue

            is_numeric = title.isdigit()
            escaneo.secciones.append(
                OriginSection(
                    source_path=pdf_path,
                    title=title,
                    start_page=start_page,
                    end_page=end_page,
                    is_numeric=is_numeric,
                    numeric_id=(title.lstrip("0") or "0") if is_numeric else "",
                    category="JG" if is_numeric else clasificar_titulo(title),
                    from_marker=True,
                )
            )

    return escaneo


def validar_carga(escaneo: EscaneoOrigen) -> str:
    """Comprobaciones al cargar los PDFs origen: "" si todo es correcto."""
    if escaneo.errores:
        return escaneo.errores[0]

    if len(escaneo.de_categoria("DC")) > 1:
        return ERROR_VARIOS_DC

    if len(escaneo.de_categoria("CJ")) > 1:
        return ERROR_VARIOS_CJ

    claves: set[str] = set()
    for section in escaneo.secciones:
        if section.is_numeric:
            clave = f"JG::{section.numeric_id}"
        else:
            clave = f"TXT::{normalizar_texto(section.title)}"
        if clave in claves:
            return ERROR_CONFLICTO
        claves.add(clave)

    return ""


def validar_dc_cj_unicos(escaneo: EscaneoOrigen) -> str:
    """Comprobaciones previas a procesar sobre las secciones: "" si todo es correcto."""
    if escaneo.errores:
        return escaneo.errores[0]

    if len(escaneo.de_categoria("DC")) != 1:
        return ERROR_DC_NO_UNICO

    if len(escaneo.de_categoria("CJ")) != 1:
        return ERROR_CJ_NO_UNICO

    return ""


# --- Titulos -----------------------------------------------------------------


def normalizar_titulo(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def numero_con_prefijo(title: str, prefix: str) -> str:
    """"DC0123 algo" con prefijo "DC" -> "123"; "" si no empieza por prefijo+digitos."""
    text = str(title or "").strip().upper()
    match = re.match(rf"^{prefix.upper()}(\d+)", text)
    if not match:
        return ""
    return match.group(1).lstrip("0") or "0"


def clasificar_titulo(title: str) -> str:
    text = str(title or "").strip().upper()
    for categoria in ("DC", "CJ", "RT"):
        if re.match(rf"^{categoria}\d+", text):
            return categoria
    return "OTHER"


def es_nombre_con_prefijo(stem: str) -> bool:
    return bool(re.match(r"^(DC|CJ|RT)\d+", str(stem or "").strip().upper()))


# --- Lectura de marcadores ---------------------------------------------------


def _archivo_directo(pdf_path: Path) -> OriginSection:
    return OriginSection(
        source_path=pdf_path,
        title=pdf_path.stem.strip(),
        start_page=None,
        end_page=None,
        is_numeric=False,
        numeric_id="",
        category=clasificar_titulo(pdf_path.stem),
        from_marker=False,
    )


def _entradas_marcadores(reader: PdfReader, outline) -> list[tuple[str, int, int]]:
    """(titulo, pagina 0-based, orden) de todos los marcadores, incluidos los anidados."""
    entries: list[tuple[str, int, int]] = []

    def _walk(node) -> None:
        if node is None:
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return

        title = _titulo_marcador(node)
        if title is not None:
            try:
                page_number = int(reader.get_destination_page_number(node))
            except Exception:
                return
            entries.append((title, page_number, len(entries)))

    _walk(outline)
    return entries


def _titulo_marcador(node) -> str | None:
    if hasattr(node, "title"):
        value = getattr(node, "title", None)
        return str(value) if value is not None else None

    if isinstance(node, dict) and "/Title" in node:
        value = node.get("/Title")
        return str(value) if value is not None else None

    return None
