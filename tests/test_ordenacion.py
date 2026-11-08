"""procesardc.ordenacion: orden de las columnas de las tablas segun su tipo."""

from __future__ import annotations

import pytest

from procesardc import ordenacion as o


def _ordenar(valores, tipo, descendente=False):
    return o.ordenar(valores, valores, tipo, descendente)


@pytest.mark.parametrize(
    ("valores", "tipo", "esperado"),
    [
        (["25", "7", "100"], o.NUMERO, ["7", "25", "100"]),
        (["131,00", "9,50", "1.375,77", "1375,76"], o.IMPORTE, ["9,50", "131,00", "1375,76", "1.375,77"]),
        (["02-01-2026", "31-12-2025", "15/01/2026"], o.FECHA, ["31-12-2025", "02-01-2026", "15/01/2026"]),
        (["10012-26", "5270-26", "5283-26"], o.TEXTO, ["5270-26", "5283-26", "10012-26"]),
        (["zapata", "Álvarez", "BELTRAN"], o.TEXTO, ["Álvarez", "BELTRAN", "zapata"]),
        (["PID2021-12", "PID2021-9", "PID"], o.TEXTO, ["PID", "PID2021-9", "PID2021-12"]),
    ],
)
def test_orden_por_tipo(valores, tipo, esperado):
    assert _ordenar(valores, tipo) == esperado
    assert _ordenar(valores, tipo, descendente=True) == esperado[::-1]


@pytest.mark.parametrize(
    ("valores", "tipo"),
    [
        (["", "10,00", "basura", "2,00"], o.IMPORTE),
        (["", "05-01-2026", "sin fecha", "01-01-2026"], o.FECHA),
        (["", "3", "x", "1"], o.NUMERO),
        (["", "b", "  ", "a"], o.TEXTO),
    ],
)
def test_vacios_e_ilegibles_siempre_al_final_en_su_orden(valores, tipo):
    for descendente in (False, True):
        resultado = _ordenar(valores, tipo, descendente)
        sin_clave = [v for v in valores if o.clave(v, tipo) is None]
        assert resultado[len(valores) - len(sin_clave):] == sin_clave


def test_orden_estable_y_filas_distintas_de_valores():
    filas = ["p1", "p2", "p3", "p4"]
    valores = ["5,00", "1,00", "5,00", "1,00"]
    assert o.ordenar(filas, valores, o.IMPORTE) == ["p2", "p4", "p1", "p3"]
    assert o.ordenar(filas, valores, o.IMPORTE, descendente=True) == ["p1", "p3", "p2", "p4"]
