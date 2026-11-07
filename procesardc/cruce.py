"""Cruce de paginas JP con filas del Excel de JG."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .lectura_excel import leer_excel
from .lectura_jp import leer_jp
from .modelos import Discrepancia, Estado, ExcelRowData, PdfPageData, Resaltado, ResultadoCruce
from .normalizacion import (
    CENTIMOS,
    firma_beneficiario,
    firma_concepto,
    firma_factura,
    formatear_decimal,
    formatear_jg,
    jg_solo_numero,
    normalizar_texto,
)

MAX_DISCREPANCIAS_CANDIDATOS = 2


@dataclass
class CandidatoCercano:
    fila: ExcelRowData
    discrepancias: list[Discrepancia]


def _jg_corto(fila: ExcelRowData) -> str:
    """"2026/000000005270" -> "5270"."""
    return jg_solo_numero(formatear_jg(fila.jg))


def analizar_ficheros(
    jp_pdf: Path, excel: Path
) -> tuple[list[PdfPageData], list[ExcelRowData], list[ResultadoCruce]]:
    """Lee el PDF JP y el Excel y los cruza (lo que hace el boton Analizar)."""
    pdf_data = leer_jp(jp_pdf)
    excel_data, _descartadas = leer_excel(excel)
    return pdf_data, excel_data, analizar(pdf_data, excel_data)


def analizar(pdf_data: list[PdfPageData], excel_data: list[ExcelRowData]) -> list[ResultadoCruce]:
    """Un resultado por pagina JP."""
    return [_resultado_pagina(page, excel_data) for page in pdf_data]


def _resultado_pagina(page: PdfPageData, excel_data: list[ExcelRowData]) -> ResultadoCruce:
    coincidencias = buscar_coincidencias(page, excel_data)
    probable_raw, origen_probable = extraer_jg_probable(page)
    probable = jg_solo_numero(probable_raw)
    resultado = ResultadoCruce(
        pagina=page,
        estado=Estado.ENCONTRADO,
        resaltado=Resaltado.NINGUNO,
        jg_probable=probable,
        origen_probable=origen_probable,
    )

    if len(coincidencias) == 1:
        encontrado = _jg_corto(coincidencias[0])
        resultado.jg_automatico = encontrado
        if probable and probable == encontrado:
            resultado.resaltado = Resaltado.VERDE
        elif probable and origen_probable == "concepto":
            # El concepto apunta a otro JG: se propone para revisarlo.
            resultado.candidatos = [probable]
            resultado.resaltado = Resaltado.ROJO
        else:
            resultado.candidatos = [encontrado]

    elif not coincidencias:
        resultado.estado = Estado.NO_ENCONTRADO
        resultado.resaltado = Resaltado.ROJO
        cercanos = buscar_candidatos_cercanos(page, excel_data, MAX_DISCREPANCIAS_CANDIDATOS)
        if cercanos:
            minimo = len(cercanos[0].discrepancias)
            resultado.candidatos = [_jg_corto(c.fila) for c in cercanos if len(c.discrepancias) == minimo]
            resultado.discrepancias = cercanos[0].discrepancias[:2]

    else:
        resultado.estado = Estado.DUDOSO
        resultado.resaltado = Resaltado.ROJO
        candidatos = [_jg_corto(fila) for fila in coincidencias]
        if probable and probable in candidatos:
            resultado.jg_automatico = probable
        elif probable:
            candidatos.append(probable)
        resultado.candidatos = list(dict.fromkeys(candidatos))

    return resultado


def buscar_coincidencias(page: PdfPageData, excel_rows: list[ExcelRowData]) -> list[ExcelRowData]:
    """Filas que coinciden en fecha, importe neto, factura, beneficiario y concepto."""
    page_fecha = normalizar_texto(page.fecha)
    page_factura_sig = firma_factura(page.factura)
    page_beneficiario_sig = firma_beneficiario(page.beneficiario)
    page_concepto_sig = firma_concepto(page.concepto)

    matches: list[ExcelRowData] = []
    for row in excel_rows:
        if page_fecha != normalizar_texto(row.fecha):
            continue
        if page.importe is None or row.importe_neto is None:
            continue
        if page.importe.quantize(CENTIMOS) != row.importe_neto:
            continue
        if page_factura_sig != firma_factura(row.factura):
            continue
        if page_beneficiario_sig != firma_beneficiario(row.beneficiario):
            continue
        if page_concepto_sig != firma_concepto(row.concepto):
            continue
        matches.append(row)

    return matches


def buscar_candidatos_cercanos(
    page: PdfPageData, excel_rows: list[ExcelRowData], max_mismatches: int
) -> list[CandidatoCercano]:
    """Filas con entre 1 y max_mismatches campos distintos, de menos a mas discrepancias."""
    evaluados: list[CandidatoCercano] = []
    page_fecha = normalizar_texto(page.fecha)
    page_factura_sig = firma_factura(page.factura)
    page_beneficiario_sig = firma_beneficiario(page.beneficiario)
    page_concept_sig = firma_concepto(page.concepto)
    page_importe = page.importe.quantize(CENTIMOS) if page.importe is not None else None

    for row in excel_rows:
        discrepancias: list[Discrepancia] = []

        if page_fecha != normalizar_texto(row.fecha):
            discrepancias.append(Discrepancia("Fecha", page.fecha, row.fecha))

        if page_importe is None or row.importe_neto is None or page_importe != row.importe_neto:
            discrepancias.append(
                Discrepancia("Importe", formatear_decimal(page.importe), formatear_decimal(row.importe_neto))
            )

        if page_factura_sig != firma_factura(row.factura):
            discrepancias.append(Discrepancia("Factura", page.factura, row.factura))

        if page_beneficiario_sig != firma_beneficiario(row.beneficiario):
            discrepancias.append(Discrepancia("Beneficiario", page.beneficiario, row.beneficiario))

        if page_concept_sig != firma_concepto(row.concepto):
            discrepancias.append(Discrepancia("Concepto", page.concepto, row.concepto))

        if 0 < len(discrepancias) <= max_mismatches:
            evaluados.append(CandidatoCercano(row, discrepancias))

    evaluados.sort(key=lambda c: (len(c.discrepancias), c.fila.row_number))
    return evaluados


def extraer_jg_probable(page: PdfPageData) -> tuple[str, str]:
    """JG "numero-aa" deducido de la factura o del principio del concepto, y su origen."""
    year_match = re.match(r"^\d{2}-\d{2}-(\d{4})$", str(page.fecha or "").strip())
    if not year_match:
        return "", ""

    year2 = year_match.group(1)[-2:]

    factura_text = re.sub(r"\s+", "", str(page.factura or ""))
    factura_match = re.search(rf"(\d+)-{year2}\b", factura_text)
    if factura_match:
        number = factura_match.group(1).lstrip("0") or "0"
        return f"{number}-{year2}", "factura"

    concept_head = re.sub(r"\s+", "", str(page.concepto or "")[:30])
    concept_match = re.search(rf"\((\d+)-{year2}\)", concept_head)
    if concept_match:
        number = concept_match.group(1).lstrip("0") or "0"
        return f"{number}-{year2}", "concepto"

    return "", ""


# --- Operaciones sobre los resultados ---------------------------------------


def filas_excel_no_asignadas(resultados: list[ResultadoCruce], excel_data: list[ExcelRowData]) -> list[dict]:
    """Filas del Excel cuyo JG no esta asignado a ninguna pagina (para mostrarlas)."""
    asignados = {jg_solo_numero(r.jg_efectivo).upper() for r in resultados if r.jg_efectivo}

    no_asignadas: list[dict] = []
    for row in excel_data:
        row_jg = _jg_corto(row)
        if row_jg.strip().upper() in asignados:
            continue
        no_asignadas.append(
            {
                "jg": row_jg,
                "fecha": row.fecha,
                "importe_neto": formatear_decimal(row.importe_neto),
                "factura": row.factura,
                "beneficiario": row.beneficiario,
                "concepto": row.concepto,
            }
        )
    return no_asignadas


def paginas_jp_por_jg(resultados: list[ResultadoCruce]) -> dict[str, list[int]]:
    """Paginas JP (1-based, en orden) que se anaden al final de cada JG, por id numerico."""
    asignaciones: dict[str, list[int]] = {}
    for r in sorted(resultados, key=lambda r: r.pagina.page_number):
        if r.pagina.page_number > 0 and r.id_jg:
            asignaciones.setdefault(r.id_jg, []).append(r.pagina.page_number)
    return asignaciones


def clave_duplicado(resultado: ResultadoCruce) -> str:
    """Se compara por numero de JG ("5270", "5270-26" y "05270" son el mismo)."""
    return resultado.id_jg or resultado.jg_efectivo.strip().upper()


def jg_duplicados(resultados: list[ResultadoCruce]) -> set[str]:
    """Claves de JG asignadas a mas de una pagina."""
    counts: dict[str, int] = {}
    for r in resultados:
        clave = clave_duplicado(r)
        if clave:
            counts[clave] = counts.get(clave, 0) + 1
    return {clave for clave, count in counts.items() if count > 1}
