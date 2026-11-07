"""procesardc.secciones: escaneo de PDFs origen y validaciones de carga."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from procesardc import ventana as app_mod
from conftest import EJ, FIXTURES, analizar, cargar_origen, generar_salida
from procesardc import secciones
from procesardc.modelos import OriginSection
from procesardc.secciones import EscaneoOrigen, escanear_origen, validar_carga, validar_dc_cj_unicos


def _resumen(escaneo: EscaneoOrigen) -> list[tuple]:
    return [
        (s.source_path.name, s.title, s.start_page, s.end_page, s.numeric_id, s.category, s.from_marker)
        for s in escaneo.secciones
    ]


@pytest.mark.parametrize(
    ("titulo", "categoria"),
    [("DC1234", "DC"), ("cj0238 extra", "CJ"), (" RT9 ", "RT"), ("DC", "OTHER"), ("ANEXO", "OTHER")],
)
def test_clasificar_titulo(titulo, categoria):
    assert secciones.clasificar_titulo(titulo) == categoria


def test_numero_con_prefijo_y_nombres():
    assert secciones.numero_con_prefijo("CJ0238", "CJ") == "238"
    assert secciones.numero_con_prefijo("dc000", "DC") == "0"
    assert secciones.numero_con_prefijo("XDC12", "DC") == ""
    assert secciones.es_nombre_con_prefijo("DC3391 escaneado")
    assert not secciones.es_nombre_con_prefijo("Documento DC3391")
    assert secciones.normalizar_titulo("  ANEXO   2 ") == "ANEXO 2"


def test_escanear_contenedor():
    escaneo = escanear_origen([FIXTURES / "origen_contenedor_ok.pdf"])
    nombre = "origen_contenedor_ok.pdf"
    assert escaneo.errores == []
    assert _resumen(escaneo) == [
        (nombre, "DC1234", 0, 1, "", "DC", True),
        (nombre, "CJ5678", 1, 2, "", "CJ", True),
        (nombre, "RT9001", 2, 3, "", "RT", True),
        (nombre, "ANEXO", 3, 4, "", "OTHER", True),
        (nombre, "5270", 4, 5, "5270", "JG", True),
        (nombre, "5283", 5, 6, "5283", "JG", True),
    ]
    assert escaneo.ids_jg == {"5270", "5283"}
    assert escaneo.otros == ["ANEXO"]
    assert escaneo.numero_con_prefijo("RT") == "9001"


def test_escanear_archivos_directos():
    escaneo = escanear_origen([EJ / "DC3391.pdf", EJ / "PARAM.pdf", FIXTURES / "ANEXO.pdf"])
    assert _resumen(escaneo) == [
        # Tiene marcadores internos, pero el nombre DC#### manda.
        ("DC3391.pdf", "DC3391", None, None, "", "DC", False),
        # Un unico marcador: se extrae como seccion.
        ("PARAM.pdf", "PARAM", 0, 2, "", "OTHER", True),
        # Sin marcadores: archivo directo con su nombre.
        ("ANEXO.pdf", "ANEXO", None, None, "", "OTHER", False),
    ]


def test_marcadores_desordenados_anidados_y_en_la_misma_pagina(tmp_path):
    origen = PdfReader(str(FIXTURES / "origen_contenedor_ok.pdf"))
    writer = PdfWriter()
    for page in origen.pages:
        writer.add_page(page)
    writer.add_outline_item("0005283", 5)
    writer.add_outline_item("DC1234", 0)
    padre = writer.add_outline_item("  ANEXO   2 ", 2)
    writer.add_outline_item("5270", 3, parent=padre)
    writer.add_outline_item("TAPADO", 4)  # comparte pagina con el siguiente: se ignora
    writer.add_outline_item("CJ5678", 4)
    ruta = tmp_path / "mezcla.pdf"
    with open(ruta, "wb") as fh:
        writer.write(fh)

    escaneo = escanear_origen([ruta])
    assert _resumen(escaneo) == [
        ("mezcla.pdf", "DC1234", 0, 2, "", "DC", True),
        ("mezcla.pdf", "ANEXO 2", 2, 3, "", "OTHER", True),
        ("mezcla.pdf", "5270", 3, 4, "5270", "JG", True),
        ("mezcla.pdf", "CJ5678", 4, 5, "", "CJ", True),
        ("mezcla.pdf", "0005283", 5, 6, "5283", "JG", True),
    ]


def test_pdf_ilegible(tmp_path):
    roto = tmp_path / "roto.pdf"
    roto.write_bytes(b"esto no es un pdf")
    escaneo = escanear_origen([roto])
    assert escaneo.secciones == []
    assert len(escaneo.errores) == 1
    assert escaneo.errores[0].startswith("No se pudo leer el PDF de origen 'roto.pdf'")
    assert validar_carga(escaneo) == escaneo.errores[0]


def _seccion(title: str, categoria: str = "OTHER") -> OriginSection:
    numerico = title.isdigit()
    return OriginSection(
        Path(f"{title}.pdf"), title, None, None, numerico,
        (title.lstrip("0") or "0") if numerico else "", "JG" if numerico else categoria, False,
    )


@pytest.mark.parametrize(
    ("titulos", "error"),
    [
        (["ANEXO", "Anexo"], secciones.ERROR_CONFLICTO),
        (["ANEXÓ", "anexo "], secciones.ERROR_CONFLICTO),
        (["0123", "123"], secciones.ERROR_CONFLICTO),
        (["123", "ANEXO", "RT1"], ""),
    ],
)
def test_validar_carga_duplicados(titulos, error):
    escaneo = EscaneoOrigen([_seccion(t, secciones.clasificar_titulo(t)) for t in titulos])
    assert validar_carga(escaneo) == error


def test_validar_dc_cj():
    dc, cj = _seccion("DC1", "DC"), _seccion("CJ1", "CJ")
    assert validar_carga(EscaneoOrigen([dc, _seccion("DC2", "DC")])) == secciones.ERROR_VARIOS_DC
    assert validar_carga(EscaneoOrigen([cj, _seccion("CJ2", "CJ")])) == secciones.ERROR_VARIOS_CJ
    assert validar_dc_cj_unicos(EscaneoOrigen([cj])) == secciones.ERROR_DC_NO_UNICO
    assert validar_dc_cj_unicos(EscaneoOrigen([dc])) == secciones.ERROR_CJ_NO_UNICO
    assert validar_dc_cj_unicos(EscaneoOrigen([dc, cj])) == ""


def test_los_pdfs_origen_se_escanean_una_sola_vez(app_sin_ui, monkeypatch, tmp_path):
    llamadas = []
    original = app_mod.escanear_origen

    def contar(files):
        llamadas.append(list(files))
        return original(files)

    monkeypatch.setattr(app_mod, "escanear_origen", contar)

    assert cargar_origen(app_sin_ui, FIXTURES / "origen_contenedor_ok.pdf") == ""
    analizar(app_sin_ui, EJ / "JP536.pdf", EJ / "DATOS JG.xlsx")
    app_sin_ui._refresh_meta_fields()
    app_sin_ui.no_jp_mode_var.set(True)
    assert app_sin_ui._validate_before_processing() == ""
    generar_salida(app_sin_ui, tmp_path)

    assert len(llamadas) == 1


def test_carga_fallida_no_cambia_lo_ya_cargado(app_sin_ui):
    assert cargar_origen(app_sin_ui, FIXTURES / "origen_contenedor_ok.pdf") == ""
    antes = (list(app_sin_ui.origin_pdf_paths), app_sin_ui.origin_scan)

    assert cargar_origen(app_sin_ui, FIXTURES / "origen_conflicto_jg_duplicado.pdf") == secciones.ERROR_CONFLICTO
    assert (app_sin_ui.origin_pdf_paths, app_sin_ui.origin_scan) == antes
    assert app_sin_ui.field_vars["dc"].get() == "1234"
