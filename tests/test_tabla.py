"""procesardc.tabla.repartir_ancho: reparto del ancho entre columnas ajustables."""

from __future__ import annotations

from procesardc.tabla import repartir_ancho

PESOS = {"beneficiario": 280, "concepto": 340, "candidatos": 220}


def test_reparto_proporcional_y_exacto():
    anchos = repartir_ancho(840, PESOS, 100)
    assert anchos == PESOS  # mismo ancho que el de diseno
    anchos = repartir_ancho(1681, PESOS, 100)
    assert sum(anchos.values()) == 1681
    assert anchos["concepto"] > anchos["beneficiario"] > anchos["candidatos"]


def test_ninguna_baja_del_minimo():
    anchos = repartir_ancho(400, PESOS, 120)
    assert sum(anchos.values()) == 400
    assert min(anchos.values()) >= 120
    assert anchos["candidatos"] == 120  # la mas pequena se queda en el minimo


def test_sin_sitio_todas_al_minimo():
    assert repartir_ancho(200, PESOS, 120) == {c: 120 for c in PESOS}
    assert repartir_ancho(-50, PESOS, 120) == {c: 120 for c in PESOS}
    assert repartir_ancho(500, {}, 120) == {}


def test_fijar_columna():
    from procesardc.tabla import fijar_columna

    anchos = fijar_columna(840, PESOS, "concepto", 500, 100)
    assert anchos["concepto"] == 500 and sum(anchos.values()) == 840
    assert anchos["beneficiario"] > anchos["candidatos"] >= 100
    # Si no cabe, se recorta para que las demas queden en el minimo.
    anchos = fijar_columna(840, PESOS, "concepto", 2000, 100)
    assert anchos == {"beneficiario": 100, "concepto": 640, "candidatos": 100}
    # Tampoco baja del minimo.
    assert fijar_columna(840, PESOS, "concepto", 10, 100)["concepto"] == 100
