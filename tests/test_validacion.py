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


# --- JG marcados en el PDF frente a los del Excel ----------------------------


def _jg(*numeros: str, archivo: str = "JG 1-9.pdf", desde_marcador: bool = True) -> list[OriginSection]:
    """Secciones JG de un archivo, una por pagina y en el orden dado."""
    return [
        OriginSection(Path(archivo), f"{n}", i, i + 1, True, n, "JG", desde_marcador)
        for i, n in enumerate(numeros)
    ]


def _sugerencias(secciones, excel) -> list[str]:
    from procesardc.sugerencias_jg import sugerencias, textos

    return textos(sugerencias(secciones, set(excel)))


def test_jg_pdf_y_excel_iguales_o_sin_alguno_no_avisan():
    assert v.comparar_jg_pdf_excel(_jg("1", "2"), {"2", "1"}) == ("", False)
    assert v.comparar_jg_pdf_excel([], {"1"}) == ("", False)
    assert v.comparar_jg_pdf_excel(_jg("1"), set()) == ("", False)


def test_jg_pdf_y_excel_de_distinto_dc():
    excel = {str(n) for n in range(10)}
    assert v.comparar_jg_pdf_excel(_jg("0", "1", "2", "3", "99"), excel) == (v.ERROR_ARCHIVOS_NO_CORRESPONDEN, True)
    # Pocos JG del Excel, pero muchos marcadores de otro DC en el PDF.
    muchos = _jg(*sorted(excel | {str(n) for n in range(100, 120)}, key=int))
    assert v.comparar_jg_pdf_excel(muchos, excel)[1] is True


def test_mensaje_de_erratas_con_sugerencias():
    mensaje, ajenos = v.comparar_jg_pdf_excel(_jg("21437", "22315", "23825"), {"21436", "22315", "23825"})
    assert not ajenos
    assert mensaje.splitlines() == [
        "Los justificantes de gasto marcados en el PDF no coinciden con el Excel de datos de JG:",
        "",
        "• En «JG 1-9.pdf», página 1: cambie el marcador «21437» por «21436».",
        "",
        v.AVISO_REVISAR_MARCADORES,
    ]


@pytest.mark.parametrize(
    "erroneo, correcto",
    [("21437", "21436"), ("2446", "24446"), ("244446", "24446"), ("24464", "24446")],
)
def test_sugiere_el_jg_parecido(erroneo, correcto):
    assert _sugerencias(_jg("100", erroneo, "90000"), {"100", correcto, "90000"}) == [
        f"En «JG 1-9.pdf», página 2: cambie el marcador «{erroneo}» por «{correcto}»."
    ]


def test_sugiere_por_orden_aunque_no_se_parezca():
    # Entre 5000 y 7000 solo falta el 6123: el marcador 1111 tiene que ser ese.
    assert _sugerencias(_jg("5000", "1111", "7000"), {"5000", "6123", "7000"}) == [
        "En «JG 1-9.pdf», página 2: cambie el marcador «1111» por «6123»."
    ]


def test_no_sugiere_si_es_ambiguo():
    # 5271 se parece igual a 5270 y a 5272, y los dos caben por orden.
    lineas = _sugerencias(_jg("5000", "5271", "9000"), {"5000", "5270", "5272", "9000"})
    assert lineas[0] == "En «JG 1-9.pdf», página 2: el marcador «5271» no corresponde a ningún JG del Excel."
    assert lineas[1].startswith("Falta el marcador del JG 5270")
    assert lineas[2].startswith("Falta el marcador del JG 5272")


def test_marcador_que_falta_con_pista_de_donde_va():
    assert _sugerencias(_jg("100", "200", "400"), {"100", "200", "300", "400"}) == [
        "Falta el marcador del JG 300 (por el orden, después del JG 200, que empieza en la página 2 de «JG 1-9.pdf»)."
    ]


def test_marcador_sobrante_sin_pareja():
    assert _sugerencias(_jg("100", "150", "200"), {"100", "200"}) == [
        "En «JG 1-9.pdf», página 2: el marcador «150» no corresponde a ningún JG del Excel."
    ]


def test_jg_deducido_del_nombre_del_archivo():
    secciones = _jg("100", "200") + _jg("5271", archivo="JG 5271.pdf", desde_marcador=False)
    assert _sugerencias(secciones, {"100", "200", "5270"}) == [
        "Cambie el nombre del archivo «JG 5271.pdf» para que sea del JG 5270."
    ]


def test_distancia_entre_numeros():
    from procesardc.sugerencias_jg import distancia

    assert distancia("21437", "21436") == 1  # un digito distinto
    assert distancia("2446", "24446") == 1  # falta uno
    assert distancia("24464", "24446") == 1  # dos contiguos intercambiados
    assert distancia("1111", "6123") == 3
