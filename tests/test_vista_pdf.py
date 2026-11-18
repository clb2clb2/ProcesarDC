"""procesardc.vista_pdf: pagina de PDF como imagen PPM para Tk."""

from __future__ import annotations

from pathlib import Path

from conftest import EJ
from procesardc.vista_pdf import pagina_ppm


def test_pagina_ppm():
    datos = pagina_ppm(EJ / "JP536.pdf", 18, 400)
    cabecera, ancho, alto, maximo = datos.split(b"\n", 3)[0], *datos.split(b"\n", 3)[1].split(), datos.split(b"\n", 3)[2]
    assert cabecera == b"P6" and int(ancho) == 400 and maximo == b"255"
    assert len(datos) == len(b"P6\n400 %d\n255\n" % int(alto)) + 400 * int(alto) * 3
    assert 150 < int(alto) < 220  # pagina apaisada (595 x 281 pt)


def test_pdf_que_no_existe_da_error():
    import pytest

    with pytest.raises(Exception):
        pagina_ppm(Path("no_existe.pdf"), 1, 400)
