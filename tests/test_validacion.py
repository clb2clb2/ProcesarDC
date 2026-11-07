"""procesardc.validacion: condiciones para poder procesar y año detectado."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from procesardc import secciones
from procesardc import validacion as v
from procesardc.modelos import Estado, ExcelRowData, OriginSection, PdfPageData, Resaltado, ResultadoCruce
from procesardc.secciones import EscaneoOrigen


def _seccion(titulo: str) -> OriginSection:
    numerico = titulo.isdigit()
    categoria = "JG" if numerico else secciones.clasificar_titulo(titulo)
    return OriginSection(Path("x.pdf"), titulo, 0, 1, numerico, titulo if numerico else "", categoria, True)


def _escaneo(*titulos: str) -> EscaneoOrigen:
    return EscaneoOrigen([_seccion(t) for t in titulos])


def _resultado(pagina: int, jg: str) -> ResultadoCruce:
    page = PdfPageData("JP.pdf", pagina, "", Decimal("1"), "", "", "")
    return ResultadoCruce(page, Estado.ENCONTRADO, Resaltado.NINGUNO, jg_automatico=jg)


COMPLETO = _escaneo("DC1234", "CJ5678", "5270", "5283")
OK = dict(dc="1234", cj="5678", anio="2026", sin_justificantes_pago=False)


def _validar(escaneo=COMPLETO, resultados=(), **cambios):
    return v.validar_para_procesar(escaneo, resultados=list(resultados), **{**OK, **cambios})


def test_todo_correcto():
    assert _validar(resultados=[_resultado(1, "5270"), _resultado(2, "5283")]) == ""
    # Puede haber JG sin pago asignado.
    assert _validar(resultados=[_resultado(1, "5283")]) == ""


@pytest.mark.parametrize(
    ("escaneo", "cambios", "resultados", "error"),
    [
        (_escaneo("CJ5678", "5270"), {}, [], secciones.ERROR_DC_NO_UNICO),
        (_escaneo("DC1", "DC2", "CJ5678"), {}, [], secciones.ERROR_DC_NO_UNICO),
        (_escaneo("DC1234", "5270"), {}, [], secciones.ERROR_CJ_NO_UNICO),
        (COMPLETO, {"dc": "X"}, [], v.ERROR_DC_NO_CARGADO),
        (COMPLETO, {"cj": "x"}, [], v.ERROR_CJ_NO_CARGADA),
        (_escaneo("DC1234", "CJ5678", "ANEXO"), {}, [], v.ERROR_SIN_JG),
        (COMPLETO, {"dc": ""}, [], v.ERROR_NUMERO_DC_CJ),
        (COMPLETO, {"cj": "0"}, [], v.ERROR_NUMERO_DC_CJ),
        (COMPLETO, {}, [], v.ERROR_SIN_ANALISIS),
        (COMPLETO, {}, [_resultado(1, "5270"), _resultado(2, "")], v.ERROR_JP_SIN_JG),
        (COMPLETO, {}, [_resultado(1, "ABC")], v.ERROR_JP_SIN_JG),
        (COMPLETO, {}, [_resultado(1, "5270"), _resultado(2, "05270")], v.ERROR_JG_REPETIDO),
        (COMPLETO, {}, [_resultado(1, "9999")], v.ERROR_JG_INEXISTENTE),
        (COMPLETO, {"anio": ""}, [_resultado(1, "5270")], v.ERROR_ANIO),
        (COMPLETO, {"anio": "2025/2026"}, [_resultado(1, "5270")], v.ERROR_ANIO),
    ],
)
def test_motivos_para_no_procesar(escaneo, cambios, resultados, error):
    assert _validar(escaneo, resultados, **cambios) == error


def test_modo_sin_justificantes_no_mira_el_analisis():
    assert _validar(sin_justificantes_pago=True, anio="") == ""  # el año se pide al procesar
    assert _validar(sin_justificantes_pago=True, anio="26") == v.ERROR_ANIO


def test_asignacion_manual_cuenta():
    r = _resultado(1, "")
    assert _validar(resultados=[r]) == v.ERROR_JP_SIN_JG
    r.jg_manual = "5283"
    assert _validar(resultados=[r]) == ""


def _fila(jg: str) -> ExcelRowData:
    return ExcelRowData(1, jg, "", Decimal("1"), Decimal("0"), "", "B", "C")


@pytest.mark.parametrize(
    ("jgs", "anio"),
    [
        (["2026/000000005270", "2026/5283"], "2026"),
        (["2026/1", "2025/2"], "2025/2026"),
        ([], ""),
        (["basura"], ""),
    ],
)
def test_anio_detectado(jgs, anio):
    assert v.anio_detectado([_fila(j) for j in jgs]) == anio
