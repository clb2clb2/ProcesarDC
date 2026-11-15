"""Reglas de los PDFs de origen: archivos DC/CJ/RT, contenedores "DOC ", archivos "JG" y otros."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from conftest import EJ, FIXTURES
from procesardc import salida
from procesardc.secciones import (
    ARCHIVO_CODIGO,
    ARCHIVO_DOC,
    ARCHIVO_JG,
    ARCHIVO_OTRO,
    escanear_origen,
    numero_jg_de_marcador,
    tipo_de_archivo,
    validar_carga,
)

PAGINAS = PdfReader(str(FIXTURES / "DOC contenedor ok.pdf")).pages  # 6 paginas de muestra


def pdf(carpeta: Path, nombre: str, paginas: int, marcadores: list[tuple[str, int]] = ()) -> Path:
    writer = PdfWriter()
    for i in range(paginas):
        writer.add_page(PAGINAS[i % len(PAGINAS)])
    for titulo, pagina in marcadores:
        writer.add_outline_item(titulo, pagina)
    ruta = carpeta / nombre
    with open(ruta, "wb") as fh:
        writer.write(fh)
    return ruta


def resumen(escaneo):
    return [(s.title, s.category, s.numeric_id, s.start_page, s.end_page) for s in escaneo.secciones]


@pytest.mark.parametrize(
    ("nombre", "tipo"),
    [
        ("DC3391", ARCHIVO_CODIGO), ("CJ0238 escaneado", ARCHIVO_CODIGO), ("rt536", ARCHIVO_CODIGO),
        ("DOC lote abril", ARCHIVO_DOC), ("doc 2026", ARCHIVO_DOC),
        ("DOCUMENTACION", ARCHIVO_OTRO), ("DOC", ARCHIVO_OTRO), ("DOC_lote", ARCHIVO_OTRO),
        ("JG 12064-17390", ARCHIVO_JG), ("jg5270", ARCHIVO_JG), ("JGx", ARCHIVO_JG),
        ("ANEXO", ARCHIVO_OTRO), ("5270", ARCHIVO_OTRO), ("DC", ARCHIVO_OTRO),
    ],
)
def test_tipo_de_archivo(nombre, tipo):
    assert tipo_de_archivo(nombre) == tipo


@pytest.mark.parametrize(
    ("titulo", "numero"),
    [("5270", "5270"), ("05283", "5283"), ("JG5270", "5270"), ("jg0012", "12"),
     ("5270 Iberdrola", ""), ("JG 5270", ""), ("DC1", ""), ("ANEXO", "")],
)
def test_marcadores_de_justificante(titulo, numero):
    assert numero_jg_de_marcador(titulo) == numero


def test_doc_reparte_por_marcadores(tmp_path):
    ruta = pdf(tmp_path, "DOC lote.pdf", 6, [
        ("DC7546 escaneado", 0), ("CJ705", 1), ("RT1604-transf", 2), ("JG12064", 3), ("15174", 4), ("PAGO REMESA", 5),
    ])
    escaneo = escanear_origen([ruta])
    assert escaneo.errores == []
    assert resumen(escaneo) == [
        ("DC7546 escaneado", "DC", "", 0, 1),
        ("CJ705", "CJ", "", 1, 2),
        ("RT1604-transf", "RT", "", 2, 3),
        ("JG12064", "JG", "12064", 3, 4),
        ("15174", "JG", "15174", 4, 5),
        ("PAGO REMESA", "OTHER", "", 5, 6),
    ]
    assert escaneo.numero_con_prefijo("DC") == "7546" and escaneo.numero_con_prefijo("RT") == "1604"


def test_doc_sin_marcadores_o_con_paginas_sueltas(tmp_path):
    escaneo = escanear_origen([pdf(tmp_path, "DOC vacio.pdf", 2)])
    assert escaneo.secciones == [] and "no tiene marcadores" in validar_carga(escaneo)

    escaneo = escanear_origen([pdf(tmp_path, "DOC portada.pdf", 4, [("DC1", 2), ("CJ2", 3)])])
    assert escaneo.secciones == []
    assert "las páginas 1 a 2 antes del primer marcador" in validar_carga(escaneo)


def test_archivo_jg_con_marcadores(tmp_path):
    escaneo = escanear_origen([pdf(tmp_path, "JG 12064-15174.pdf", 3, [("12064", 0), ("JG15174", 2)])])
    assert escaneo.errores == []
    assert resumen(escaneo) == [("12064", "JG", "12064", 0, 2), ("JG15174", "JG", "15174", 2, 3)]

    # Un marcador que no es un justificante es un error que lo nombra.
    escaneo = escanear_origen([pdf(tmp_path, "JG lote.pdf", 3, [("12064", 0), ("DC1.pdf", 1)])])
    assert escaneo.secciones == []
    assert "el marcador «DC1.pdf» (página 2)" in validar_carga(escaneo)

    # Paginas antes del primer justificante.
    escaneo = escanear_origen([pdf(tmp_path, "JG portada.pdf", 3, [("12064", 1)])])
    assert "la página 1 antes del primer marcador" in validar_carga(escaneo)


def test_archivo_jg_sin_marcadores(tmp_path):
    # JG + numero: un solo justificante con todas sus paginas.
    escaneo = escanear_origen([pdf(tmp_path, "JG05270 factura luz.pdf", 2)])
    assert resumen(escaneo) == [("JG05270 factura luz", "JG", "5270", 0, 2)]
    assert not escaneo.secciones[0].from_marker

    # Marcadores que no son de justificante y nombre JG + numero: el nombre manda.
    escaneo = escanear_origen([pdf(tmp_path, "JG5283.pdf", 2, [("DC1.pdf", 0)])])
    assert resumen(escaneo) == [("JG5283", "JG", "5283", 0, 2)]

    # Sin marcadores ni numero tras "JG": error.
    escaneo = escanear_origen([pdf(tmp_path, "JG 12064-17390.pdf", 2)])
    assert escaneo.secciones == []
    assert "no tiene marcadores con números de justificante" in validar_carga(escaneo)


def test_otros_archivos_se_archivan_enteros(tmp_path):
    # Aunque tenga marcadores con codigos, un nombre que no es DOC ni JG se archiva tal cual.
    escaneo = escanear_origen([pdf(tmp_path, "DOCUMENTACION.pdf", 3, [("DC1", 0), ("5270", 1)]),
                               pdf(tmp_path, "5290.pdf", 1)])
    assert resumen(escaneo) == [("DOCUMENTACION", "OTHER", "", None, None), ("5290", "OTHER", "", None, None)]


def test_jg_entero_recibe_sus_pagos_y_rt_con_numero(tmp_path):
    jg = pdf(tmp_path, "JG5270.pdf", 2)
    rt = pdf(tmp_path, "RT1604 transferencias.pdf", 1)
    escaneo = escanear_origen([EJ / "DC3391.pdf", EJ / "CJ0238.pdf", jg, rt])
    assert validar_carga(escaneo) == ""

    carpeta = tmp_path / "salida"
    plan = salida.planificar(carpeta, escaneo.secciones, dc=3391, cj=238)
    salida.generar(plan, jp_pdf=EJ / "JP536.pdf", paginas_jp_por_jg={"5270": [1, 2]})
    assert sorted(p.name for p in carpeta.iterdir()) == ["CJ238.pdf", "DC3391.pdf", "JG5270.pdf", "RT1604.pdf"]
    assert len(PdfReader(str(carpeta / "JG5270.pdf")).pages) == 2 + 2  # sus paginas + 2 de pago
