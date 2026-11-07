"""Escaneo de PDFs origen, validaciones y ficheros de salida (escenarios de la guia de pruebas)."""

from __future__ import annotations

import pytest
from pypdf import PdfReader, PdfWriter

from conftest import EJ, FIXTURES, PDF_COMPLETO, analizar, cargar_origen, generar_salida

CONFLICTO = (
    "¡Atención! Hay marcadores o archivos en conflicto "
    "(duplicados entre secciones extraídas y/o archivos directos)."
)


def paginas(ruta) -> int:
    return len(PdfReader(str(ruta)).pages)


def contenido(carpeta) -> dict[str, int]:
    return {p.name: paginas(p) for p in sorted(carpeta.iterdir())}


def test_escenario_a_contenedor_sin_justificantes(app_sin_ui, tmp_path):
    assert cargar_origen(app_sin_ui, FIXTURES / "origen_contenedor_ok.pdf") == ""
    campos = {k: v.get() for k, v in app_sin_ui.field_vars.items()}
    assert campos == {
        "anio": "",
        "dc": "1234",
        "cj": "5678",
        "jg_origen": "JG encontrados: 2",
        "rt": "9001",
        "otros": "ANEXO",
    }

    app_sin_ui.no_jp_mode_var.set(True)
    assert app_sin_ui._validate_before_processing() == ""

    app_sin_ui.field_vars["anio"].set("2026")  # lo que se confirmaria en el dialogo
    carpeta = generar_salida(app_sin_ui, tmp_path)

    assert carpeta.name == "2026000001234 (REMESA INV)"
    assert contenido(carpeta) == {
        "ANEXO.pdf": 1,
        "CJ5678.pdf": 1,
        "DC1234.pdf": 1,
        "JG5270.pdf": 1,
        "JG5283.pdf": 1,
        "RT9001.pdf": 1,
    }


@pytest.mark.parametrize(
    "origenes",
    [
        pytest.param(["origen_conflicto_texto_duplicado.pdf"], id="B-texto-duplicado"),
        pytest.param(["origen_conflicto_jg_duplicado.pdf"], id="C-jg-duplicado"),
        pytest.param(["origen_contenedor_ok.pdf", "ANEXO.pdf"], id="D-marcador-vs-archivo"),
    ],
)
def test_escenarios_de_conflicto(app_sin_ui, origenes):
    assert cargar_origen(app_sin_ui, *(FIXTURES / n for n in origenes)) == CONFLICTO
    assert app_sin_ui.origin_pdf_paths == []


def test_dos_documentos_contables(app_sin_ui):
    error = cargar_origen(app_sin_ui, FIXTURES / "origen_contenedor_ok.pdf", EJ / "DC3391.pdf")
    assert error == "¡Atención! Debes cargar un solo archivo de Documento Contable (DC)."


def _contenedor_solo_jg(tmp_path):
    origen = PdfReader(str(FIXTURES / "origen_contenedor_ok.pdf"))
    writer = PdfWriter()
    writer.add_page(origen.pages[4])
    writer.add_page(origen.pages[5])
    writer.add_outline_item("5270", 0)
    writer.add_outline_item("05283", 1)
    ruta = tmp_path / "justificantes.pdf"
    with open(ruta, "wb") as fh:
        writer.write(fh)
    return ruta


def test_archivos_directos_mas_contenedor_de_jg(app_sin_ui, tmp_path):
    # DC3391/CJ0238/RT536 tienen marcadores internos, pero su nombre hace que se copien tal cual.
    jg = _contenedor_solo_jg(tmp_path)
    error = cargar_origen(
        app_sin_ui, EJ / "DC3391.pdf", EJ / "CJ0238.pdf", EJ / "RT536.pdf", EJ / "PARAM.pdf", jg
    )
    assert error == ""
    assert app_sin_ui.field_vars["dc"].get() == "3391"
    assert app_sin_ui.field_vars["cj"].get() == "238"
    assert app_sin_ui.field_vars["rt"].get() == "536"
    assert app_sin_ui.field_vars["otros"].get() == "PARAM"

    app_sin_ui.no_jp_mode_var.set(True)
    app_sin_ui.doc_type_var.set("Tarjeta INV")
    app_sin_ui.field_vars["anio"].set("2026")
    assert app_sin_ui._validate_before_processing() == ""
    carpeta = generar_salida(app_sin_ui, tmp_path / "salida")

    assert carpeta.name == "2026000003391 (TARJETA INV)"
    assert contenido(carpeta) == {
        "CJ238.pdf": 7,
        "DC3391.pdf": 3,
        "JG5270.pdf": 1,
        "JG5283.pdf": 1,  # el marcador "05283" pierde los ceros a la izquierda
        "PARAM.pdf": 2,
        "RT536.pdf": 5,
    }


def test_sin_jg_no_se_puede_procesar(app_sin_ui):
    assert cargar_origen(app_sin_ui, EJ / "DC3391.pdf", EJ / "CJ0238.pdf") == ""
    app_sin_ui.no_jp_mode_var.set(True)
    assert app_sin_ui._validate_before_processing() == (
        "No se han cargado Justificantes de Gasto válidos, o el archivo no tiene marcadores"
    )


@pytest.mark.skipif(not PDF_COMPLETO.exists(), reason="Falta el PDF grande del escenario E (ver GUIA_PRUEBAS)")
def test_escenario_e_modo_normal_completo(app_sin_ui, tmp_path):
    assert cargar_origen(app_sin_ui, PDF_COMPLETO) == ""
    analizar(app_sin_ui, EJ / "JP536.pdf", EJ / "DATOS JG.xlsx")
    assert app_sin_ui._validate_before_processing() == ""

    secciones = app_sin_ui.origin_scan.secciones
    paginas_jg = {s.numeric_id: s.end_page - s.start_page for s in secciones if s.is_numeric}
    asignados = {r.id_jg for r in app_sin_ui.main_results}
    assert len(paginas_jg) == 26 and len(asignados) == 25

    carpeta = generar_salida(app_sin_ui, tmp_path)
    assert carpeta.name == "2026000001234 (REMESA INV)"

    esperado = {"DC1234.pdf": 1, "CJ5678.pdf": 1}
    for jg, n in paginas_jg.items():
        esperado[f"JG{jg}.pdf"] = n + (1 if jg in asignados else 0)
    assert contenido(carpeta) == dict(sorted(esperado.items()))
