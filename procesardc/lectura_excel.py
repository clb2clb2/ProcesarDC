"""Lectura del Excel de UXXI "Seleccion parametrica de justificantes del gasto"."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from .modelos import ExcelRowData
from .normalizacion import (
    JG_EXCEL_RE,
    JG_LIKE_RE,
    normalizar_cabecera,
    normalizar_fecha_excel,
    normalizar_texto,
    parse_decimal,
)

COLUMNAS_OBLIGATORIAS = {
    "jg": "n reg. justific.",
    "fecha": "fecha pago",
    "importe_total": "importe total",
    "importe_retencion": "importe retencion",
    "factura": "factura proveedor",
    "beneficiario": "nombre proveedor",
    "concepto": "descripcion",
}


def leer_excel(excel_path: Path) -> tuple[list[ExcelRowData], list[int]]:
    """Devuelve las filas validas y los numeros de fila con JG que se han descartado."""
    wb = load_workbook(filename=str(excel_path), data_only=True)
    ws = wb.active

    header_row_idx = localizar_cabecera(ws)
    col_index = mapear_columnas(ws, header_row_idx)

    rows: list[ExcelRowData] = []
    discarded_rows: list[int] = []
    for row_idx in range(header_row_idx + 1, ws.max_row + 1):
        valor = {key: ws.cell(row=row_idx, column=col).value for key, col in col_index.items()}

        jg_raw = valor["jg"]
        fecha = normalizar_fecha_excel(valor["fecha"])
        total = parse_decimal(valor["importe_total"])
        ret = parse_decimal(valor["importe_retencion"])
        factura = normalizar_texto(str(valor["factura"] or ""))
        beneficiario = normalizar_texto(str(valor["beneficiario"] or ""))
        concepto = normalizar_texto(str(valor["concepto"] or ""))

        if not es_fila_valida(jg_raw, fecha, total, ret, beneficiario, concepto):
            if JG_LIKE_RE.match(str(jg_raw or "")):
                discarded_rows.append(row_idx)
            continue

        rows.append(
            ExcelRowData(
                row_number=row_idx,
                jg=str(jg_raw).strip(),
                fecha=fecha,
                importe_total=total,
                importe_retencion=ret,
                factura=factura,
                beneficiario=beneficiario,
                concepto=concepto,
            )
        )

    return rows, discarded_rows


def localizar_cabecera(ws) -> int:
    for row_idx in range(1, ws.max_row + 1):
        normalized = [normalizar_cabecera(ws.cell(row=row_idx, column=c).value) for c in range(1, ws.max_column + 1)]
        if "n reg. justific." in normalized and "fecha pago" in normalized:
            return row_idx

    raise ValueError("No se encontro la fila de cabeceras en el Excel.")


def mapear_columnas(ws, header_row_idx: int) -> dict[str, int]:
    headers = {
        normalizar_cabecera(ws.cell(row=header_row_idx, column=col_idx).value): col_idx
        for col_idx in range(1, ws.max_column + 1)
    }

    mapped: dict[str, int] = {}
    for key, header in COLUMNAS_OBLIGATORIAS.items():
        if header not in headers:
            raise ValueError(f"Falta la columna requerida en Excel: {header}")
        mapped[key] = headers[header]

    return mapped


def es_fila_valida(
    jg_raw,
    fecha: str,
    importe_total: Decimal | None,
    importe_retencion: Decimal | None,
    beneficiario: str,
    concepto: str,
) -> bool:
    return bool(
        JG_EXCEL_RE.match(str(jg_raw or "").strip())
        and re.match(r"^\d{2}-\d{2}-\d{4}$", fecha)
        and importe_total is not None
        and importe_retencion is not None
        and beneficiario
        and concepto
    )
