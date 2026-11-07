"""Normalizacion de textos, importes, fechas y numeros de JG (funciones puras)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTIMOS = Decimal("0.01")

# N. reg. justificante de Sorolla/UXXI: "2026/000000005270" (el relleno de ceros puede variar).
JG_EXCEL_RE = re.compile(r"^20\d{2}/\d+$")
# Cualquier celda con forma de JG (aunque no sea valida), para avisar de filas descartadas.
JG_LIKE_RE = re.compile(r"^\s*\d{4}\s*/\s*\d+\s*$")


# --- Textos -----------------------------------------------------------------


def normalizar_texto(value: str) -> str:
    """Mayusculas, sin acentos y con los espacios colapsados."""
    value = value.strip().upper()
    value = "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", value)


def normalizar_cabecera(value) -> str:
    """Cabecera de columna del Excel comparable ("Nº reg. justific." -> "n reg. justific.")."""
    text = str(value or "").strip().upper()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    text = text.replace("N.", "N ")
    text = re.sub(r"N[^A-Z0-9 ]", "N ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


# --- Importes y fechas ------------------------------------------------------


def parse_decimal(value) -> Decimal | None:
    """Importe a Decimal con 2 decimales; acepta celdas numericas y texto en formato espanol."""
    if value is None or isinstance(value, bool):
        return None

    # Celdas numericas de Excel (int/float/Decimal): ya traen el punto decimal correcto.
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value)).quantize(CENTIMOS, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return None

    text = str(value).strip()
    text = text.replace("EUR", "").replace("€", "").replace("\xa0", "").replace(" ", "")
    if not text:
        return None

    if "," in text:
        # Formato espanol: 1.375,77
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", text):
        # Solo separadores de miles: 1.375 o 1.234.567
        text = text.replace(".", "")

    try:
        return Decimal(text).quantize(CENTIMOS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def formatear_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}".replace(".", ",")


def normalizar_fecha_excel(value) -> str:
    """Fecha del Excel a dd-mm-aaaa."""
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")

    text = str(value).strip()
    if not text:
        return ""

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue

    return text.replace("/", "-")


# --- Firmas para comparar JP con Excel -------------------------------------


def normalizar_concepto_pdf(value: str) -> str:
    """Une palabras cortadas por la extraccion de texto del PDF ("C OMPRA" -> "COMPRA")."""
    text = normalizar_texto(value)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\b([A-Z])\s+([A-Z]{2,})\b", r"\1\2", text)
        text = re.sub(r"\b([A-Z]{2,})\s+([A-Z])\b", r"\1\2", text)
    return text


def firma_concepto(value: str) -> str:
    text = normalizar_concepto_pdf(str(value or ""))
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text[:75]


def firma_beneficiario(value: str) -> str:
    text = normalizar_texto(str(value or ""))
    text = text.replace("&", "")
    text = re.sub(r"\s+", "", text)
    return text[:25]


def firma_factura(value: str) -> str:
    text = normalizar_texto(str(value or ""))
    text = text.replace("_", "")
    return re.sub(r"\s+", "", text)


# --- Numeros de JG ----------------------------------------------------------


def formatear_jg(raw_jg: str) -> str:
    """"2026/000000005270" -> "5270-26"; cualquier otra cosa se devuelve igual."""
    text = str(raw_jg or "").strip()
    match = re.match(r"^(\d{4})/(\d+)$", text)
    if not match:
        return text

    year4 = match.group(1)
    numeric = match.group(2).lstrip("0") or "0"
    return f"{numeric}-{year4[-2:]}"


def jg_solo_numero(value: str) -> str:
    """"5270-26" / "005270" / "5270ABC" -> "5270"; sin digitos iniciales se devuelve igual."""
    text = str(value or "").strip().upper()
    if not text:
        return ""

    match = re.match(r"^(\d+)\s*-\s*\d{2}$", text)
    if match:
        return match.group(1).lstrip("0") or "0"

    if text.isdigit():
        return text.lstrip("0") or "0"

    plain_match = re.match(r"^(\d+)", text)
    if plain_match:
        return plain_match.group(1).lstrip("0") or "0"

    return text


def normalizar_jg_manual(value: str) -> str:
    """JG escrito por el usuario en el dialogo de asignacion manual.

    Se deja solo el numero, como el resto de JG de la tabla: "2026/0005270",
    "05270-26" y "5270" quedan como "5270". Lo que no empieza por digitos se deja en mayusculas.
    """
    text = str(value or "").strip().upper()
    if not text:
        return ""

    if re.match(r"^\d{4}/\d+$", text):
        return jg_solo_numero(formatear_jg(text))

    return jg_solo_numero(text)


def id_numerico_jg(value: str) -> str:
    """Identificador numerico de un JG (sin ceros a la izquierda) o "" si no empieza por digitos."""
    text = str(value or "").strip().upper()
    if not text:
        return ""

    match = re.match(r"^(\d+)", text)
    if not match:
        return ""

    return match.group(1).lstrip("0") or "0"
