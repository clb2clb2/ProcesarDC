"""Lectura del PDF de Justificantes de Pago (JP): una transferencia por pagina."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from .modelos import PdfPageData
from .normalizacion import normalizar_texto, parse_decimal


def leer_jp(pdf_path: Path) -> list[PdfPageData]:
    reader = PdfReader(str(pdf_path))
    return [
        parsear_pagina_jp(page.extract_text() or "", idx + 1, pdf_path.name)
        for idx, page in enumerate(reader.pages)
    ]


def parsear_pagina_jp(text: str, page_number: int, source_name: str) -> PdfPageData:
    linea = _texto_en_una_linea(text)

    importe_match = re.search(r"Importe ordenado:\s*([0-9\.,]+)\s*EUR", linea, flags=re.IGNORECASE)
    fecha_match = re.search(r"Fecha operaci[oó]n:\s*([0-9]{2}-[0-9]{2}-[0-9]{4})", linea, flags=re.IGNORECASE)
    beneficiario_match = re.search(r"EUR\s*>>\s*(.*?)\s*POR CUENTA DE:", linea, flags=re.IGNORECASE)
    concepto_block_match = re.search(r"CONCEPTO:\s*(.*)$", linea, flags=re.IGNORECASE)

    if concepto_block_match:
        factura, concepto = separar_factura_concepto(concepto_block_match.group(1).strip())
    else:
        factura, concepto = "", ""

    return PdfPageData(
        source_name=source_name,
        page_number=page_number,
        fecha=fecha_match.group(1) if fecha_match else "",
        importe=parse_decimal(importe_match.group(1)) if importe_match else None,
        factura=factura,
        beneficiario=beneficiario_match.group(1).strip() if beneficiario_match else "",
        concepto=concepto,
    )


def separar_factura_concepto(concepto_block: str) -> tuple[str, str]:
    """Separa "Factura: <factura> - <concepto>".

    Elige el " - " cuyo lado derecho empieza por 4 letras; si no hay ninguno, el primero.
    """
    text = str(concepto_block or "").strip()
    factura_payload_match = re.match(r"Factura:\s*(.*)$", text, flags=re.IGNORECASE)
    if not factura_payload_match:
        return "", text

    payload = factura_payload_match.group(1).strip()

    for sep in re.finditer(r"\s-\s", payload):
        left = payload[: sep.start()].strip()
        right = payload[sep.end() :].strip()
        if left and right and _empieza_por_cuatro_letras(right):
            return left, right

    classic = re.match(r"^(.*?)\s-\s(.*)$", payload)
    if classic:
        return classic.group(1).strip(), classic.group(2).strip()

    return "", text


def _empieza_por_cuatro_letras(text: str) -> bool:
    head = normalizar_texto(str(text or ""))[:4]
    return len(head) == 4 and head.isalpha()


def _texto_en_una_linea(text: str) -> str:
    text = text.replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()
