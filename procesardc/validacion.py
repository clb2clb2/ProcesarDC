"""Reglas que deciden si se puede procesar un Documento Contable."""

from __future__ import annotations

import re

from .modelos import ExcelRowData, ResultadoCruce
from .secciones import EscaneoOrigen, validar_dc_cj_unicos

ERROR_DC_NO_CARGADO = "No se ha cargado un Documento Contable válido"
ERROR_CJ_NO_CARGADA = "No se ha cargado un Cuenta Justificativa válida"
ERROR_SIN_JG = "No se han cargado Justificantes de Gasto válidos, o el archivo no tiene marcadores"
ERROR_NUMERO_DC_CJ = "Debe escribir el número de Documento Contable/Cuenta Justificativa"
ERROR_ANIO = "El año detectado no es válido"
ERROR_SIN_ANALISIS = "Debe ejecutar el análisis antes de procesar"
ERROR_JP_SIN_JG = "Hay Justificantes de Pago a los que no se ha asignado un número de JG"
ERROR_JG_REPETIDO = "Hay varias páginas de JP asignadas al mismo JG"
ERROR_JG_INEXISTENTE = "Hay Justificantes de Pago con JG asignado que no existe en el archivo JG"


def anio_detectado(filas: list[ExcelRowData]) -> str:
    """Año de los JG del Excel ("2026"); si hay varios, "2025/2026"; si no hay, ""."""
    anios = set()
    for fila in filas:
        match = re.match(r"^(20\d{2})/\d+$", str(fila.jg or "").strip())
        if match:
            anios.add(match.group(1))
    return "/".join(sorted(anios))


def es_anio_valido(anio: str) -> bool:
    return bool(re.match(r"^\d{4}$", anio.strip()))


def _es_numero_positivo(valor: str) -> bool:
    valor = valor.strip()
    return valor.isdigit() and int(valor) > 0


def validar_para_procesar(
    escaneo: EscaneoOrigen,
    dc: str,
    cj: str,
    anio: str,
    sin_justificantes_pago: bool,
    resultados: list[ResultadoCruce],
) -> str:
    """Primer motivo por el que no se puede procesar, o "" si se puede.

    `dc`, `cj` y `anio` son los valores de los campos de la ventana ("X" = no detectado).
    """
    error = validar_dc_cj_unicos(escaneo)
    if error:
        return error

    if dc.strip().upper() == "X":
        return ERROR_DC_NO_CARGADO

    if cj.strip().upper() == "X":
        return ERROR_CJ_NO_CARGADA

    if not escaneo.ids_jg:
        return ERROR_SIN_JG

    if not _es_numero_positivo(dc) or not _es_numero_positivo(cj):
        return ERROR_NUMERO_DC_CJ

    if sin_justificantes_pago:
        # El año puede faltar: se pide al procesar.
        if anio.strip() and not es_anio_valido(anio):
            return ERROR_ANIO
        return ""

    if not resultados:
        return ERROR_SIN_ANALISIS

    ids = [r.id_jg for r in resultados]
    if not all(ids):
        return ERROR_JP_SIN_JG

    if len(set(ids)) != len(ids):
        return ERROR_JG_REPETIDO

    if any(i not in escaneo.ids_jg for i in ids):
        return ERROR_JG_INEXISTENTE

    if not es_anio_valido(anio):
        return ERROR_ANIO

    return ""
