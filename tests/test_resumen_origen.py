"""procesardc.ventana.resumen_origen: texto de la zona de carga de los PDFs de origen."""

from __future__ import annotations

from pathlib import Path

import pytest

from procesardc import secciones
from procesardc.modelos import OriginSection
from procesardc.secciones import EscaneoOrigen
from procesardc.ventana import resumen_origen
from procesardc.zona_soltar import NO, SI, texto_plano


def _escaneo(*titulos: str) -> EscaneoOrigen:
    def seccion(titulo: str) -> OriginSection:
        numerico = titulo.isdigit()
        categoria = "JG" if numerico else secciones.clasificar_titulo(titulo)
        numero = (titulo.lstrip("0") or "0") if numerico else ""
        return OriginSection(Path(f"{titulo}.pdf"), titulo, None, None, numerico, numero, categoria, False)

    return EscaneoOrigen([seccion(t) for t in titulos])


@pytest.mark.parametrize(
    ("titulos", "esperado", "marcas"),
    [
        (
            ("DC1234", "CJ0238", "10012", "5270", "05283", "RT9001", "ANEXO", "PARAM"),
            "DC: 1234 ✔, CJ: 238 ✔, RT: 9001 ✔\n3 justificantes de gastos cargados ✔\nOtros archivos: ANEXO, PARAM",
            [SI, SI, SI, SI],
        ),
        (
            ("CJ5678", "5270"),
            "DC: ✖, CJ: 5678 ✔, RT: ✖\n1 justificante de gastos cargado ✔\nOtros archivos: —",
            [NO, SI, NO, SI],
        ),
        (
            ("DC1234",),
            "DC: 1234 ✔, CJ: ✖, RT: ✖\n0 justificantes de gastos cargados ✖\nOtros archivos: —",
            [SI, NO, NO, NO],
        ),
    ],
)
def test_resumen_origen(titulos, esperado, marcas):
    lineas = resumen_origen(_escaneo(*titulos))
    assert texto_plano(lineas) == esperado
    # Las marcas van en trozos aparte, con su estilo (letra pequena, verde o roja).
    trozos_marca = [(t, estilo) for linea in lineas for t, estilo in linea if estilo in (SI, NO)]
    assert [estilo for _t, estilo in trozos_marca] == marcas
    assert all(t == ("✔" if estilo == SI else "✖") for t, estilo in trozos_marca)
