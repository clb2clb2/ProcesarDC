"""Escaneo de los PDFs de origen: que documento es cada archivo o cada marcador.

Codigos (en nombres de archivo y en marcadores, sin distinguir mayusculas):
- DC, CJ o RT seguido de numeros (y cualquier cosa detras): Documento Contable, Cuenta
  Justificativa o Relacion de Transferencias, con el numero que sigue a las letras.
- Justificante de gasto (JG): un marcador que es un numero (5270, 05283) o JG + numero
  (JG5270); un archivo cuyo nombre es JG + numero (JG5270.pdf, JG5270 algo.pdf).

Reglas por archivo:
- Nombre que empieza por DC/CJ/RT + numeros: ese documento, entero (sus marcadores se ignoran).
- Nombre que empieza por "DOC " (DOC y un espacio): contiene varios documentos; cada marcador
  abre uno (DC/CJ/RT, JG o, si no es un codigo, un documento con el nombre del marcador).
- Nombre que empieza por "JG": si tiene marcadores de JG, cada uno abre un justificante y no
  puede haber otros marcadores; si no los tiene, el nombre JG + numero lo hace un solo JG.
- Cualquier otro nombre: se archiva entero con su nombre (sus marcadores se ignoran).

En los archivos "DOC" y "JG" partidos por marcadores, todas las paginas deben pertenecer a
algun marcador: si hay paginas antes del primero, la carga se rechaza.
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


# Tipos de archivo segun su nombre.
ARCHIVO_CODIGO = "codigo"  # DC/CJ/RT + numeros
ARCHIVO_DOC = "doc"  # "DOC ": varios documentos con marcadores
ARCHIVO_JG = "jg"  # "JG...": justificantes de gasto
ARCHIVO_OTRO = "otro"


def tipo_de_archivo(stem: str) -> str:
    nombre = str(stem or "").strip()
    if es_nombre_con_prefijo(nombre):
        return ARCHIVO_CODIGO
    if re.match(r"^DOC\s", nombre, flags=re.IGNORECASE):
        return ARCHIVO_DOC
    if nombre.upper().startswith("JG"):
        return ARCHIVO_JG
    return ARCHIVO_OTRO


def numero_jg_de_marcador(titulo: str) -> str:
    """"5270", "05283" o "JG5270" -> numero de JG sin ceros a la izquierda; "" si no lo es."""
    match = re.match(r"^(?:JG)?(\d+)$", normalizar_titulo(titulo), flags=re.IGNORECASE)
    return (match.group(1).lstrip("0") or "0") if match else ""


def numero_jg_de_nombre(stem: str) -> str:
    """"JG5270 algo" -> "5270"; "" si el nombre no es JG + numeros."""
    return numero_con_prefijo(stem, "JG")


def escanear_origen(files: list[Path]) -> EscaneoOrigen:
    escaneo = EscaneoOrigen()

    for pdf_path in files:
        try:
            reader = PdfReader(str(pdf_path))
            total = len(reader.pages)
            marcadores = _entradas_marcadores(reader, reader.outline)
        except Exception as exc:
            escaneo.errores.append(f"No se pudo leer el PDF '{pdf_path.name}': {exc}")
            continue

        tipo = tipo_de_archivo(pdf_path.stem)
        if tipo == ARCHIVO_DOC:
            _escanear_doc(escaneo, pdf_path, marcadores, total)
        elif tipo == ARCHIVO_JG:
            _escanear_jg(escaneo, pdf_path, marcadores, total)
        elif pdf_path.stem.strip():
            escaneo.secciones.append(_archivo_directo(pdf_path))

    return escaneo


def _escanear_doc(escaneo: EscaneoOrigen, pdf_path: Path, marcadores, total: int) -> None:
    tramos = _tramos(marcadores, total)
    if not tramos:
        escaneo.errores.append(
            f"El archivo '{pdf_path.name}' empieza por «DOC», pero no tiene marcadores: cada documento "
            "que contiene debe empezar con un marcador (DC…, CJ…, RT…, el número del justificante u otro nombre)."
        )
        return
    if not _sin_paginas_huerfanas(escaneo, pdf_path, tramos):
        return
    for titulo, inicio, fin in tramos:
        numero_jg = numero_jg_de_marcador(titulo)
        if numero_jg:
            escaneo.secciones.append(_seccion_jg(pdf_path, titulo, numero_jg, inicio, fin, desde_marcador=True))
        else:
            escaneo.secciones.append(
                OriginSection(pdf_path, titulo, inicio, fin, False, "", clasificar_titulo(titulo), True)
            )


def _escanear_jg(escaneo: EscaneoOrigen, pdf_path: Path, marcadores, total: int) -> None:
    if any(numero_jg_de_marcador(titulo) for titulo, _pagina, _orden in marcadores):
        for titulo, pagina, _orden in marcadores:
            if normalizar_titulo(titulo) and not numero_jg_de_marcador(titulo):
                escaneo.errores.append(
                    f"El archivo '{pdf_path.name}' tiene el marcador «{normalizar_titulo(titulo)}» (página "
                    f"{pagina + 1}), que no es un número de justificante de gasto. En un archivo «JG» todos "
                    "los marcadores deben ser números de justificante (por ejemplo, 5270 o JG5270)."
                )
                return
        tramos = _tramos(marcadores, total)
        if not _sin_paginas_huerfanas(escaneo, pdf_path, tramos):
            return
        for titulo, inicio, fin in tramos:
            escaneo.secciones.append(
                _seccion_jg(pdf_path, titulo, numero_jg_de_marcador(titulo), inicio, fin, desde_marcador=True)
            )
        return

    numero_jg = numero_jg_de_nombre(pdf_path.stem)
    if numero_jg:
        # Un solo justificante con todas sus paginas (se extraen para poder anadirle sus pagos).
        escaneo.secciones.append(
            _seccion_jg(pdf_path, pdf_path.stem.strip(), numero_jg, 0, total, desde_marcador=False)
        )
        return
    escaneo.errores.append(
        f"El archivo '{pdf_path.name}' empieza por «JG», pero no tiene marcadores con números de "
        "justificante ni un número detrás de «JG» en el nombre (por ejemplo, JG5270.pdf)."
    )


def _tramos(marcadores, total: int) -> list[tuple[str, int, int]]:
    """(titulo, pagina inicial, pagina final excluida) de cada marcador, ordenados por pagina.

    Se ignoran los marcadores sin titulo, fuera de rango o que comparten pagina con el siguiente.
    """
    ordenados = sorted(marcadores, key=lambda it: (it[1], it[2]))
    tramos = []
    for idx, (titulo_crudo, inicio, _orden) in enumerate(ordenados):
        fin = ordenados[idx + 1][1] if idx + 1 < len(ordenados) else total
        titulo = normalizar_titulo(titulo_crudo)
        if titulo and 0 <= inicio < fin <= total:
            tramos.append((titulo, inicio, fin))
    return tramos


def _sin_paginas_huerfanas(escaneo: EscaneoOrigen, pdf_path: Path, tramos) -> bool:
    """Las paginas anteriores al primer marcador no irian a ningun documento: se rechaza."""
    if tramos and tramos[0][1] > 0:
        primera = tramos[0][1]
        paginas = "la página 1" if primera == 1 else f"las páginas 1 a {primera}"
        escaneo.errores.append(
            f"El archivo '{pdf_path.name}' tiene {paginas} antes del primer marcador, y no irían a ningún "
            "documento. Pon un marcador en la página 1 o quita esas páginas del PDF."
        )
        return False
    return True


def _seccion_jg(pdf_path: Path, titulo: str, numero: str, inicio: int, fin: int, desde_marcador: bool) -> OriginSection:
    return OriginSection(pdf_path, titulo, inicio, fin, True, numero, "JG", desde_marcador)


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
