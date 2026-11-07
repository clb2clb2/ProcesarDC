"""Lectura del Excel de UXXI "Seleccion parametrica de justificantes del gasto"."""

from datetime import datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook

from conftest import EJ
from procesardc.lectura_excel import leer_excel

CABECERAS = [
    "Nº reg. justific.",
    "Fecha Pago",
    "Importe Total",
    "Importe Retención",
    "Factura proveedor",
    "Nombre Proveedor",
    "Descripción",
]


@pytest.mark.parametrize(
    ("nombre", "validas", "primer_jg", "primer_neto"),
    [
        ("DATOS JG.xlsx", 26, "2026/000000005270", Decimal("1375.77")),
        ("DATOS JG2.xlsx", 26, "2026/000000005270", Decimal("1375.77")),
        ("DATOS JG3.xlsx", 25, "2026/000000004880", Decimal("2204.80")),
    ],
)
def test_excel_reales_de_uxxi(nombre, validas, primer_jg, primer_neto):
    filas, descartadas = leer_excel(EJ / nombre)
    assert len(filas) == validas
    assert descartadas == []
    assert filas[0].jg == primer_jg
    assert filas[0].importe_neto == primer_neto
    assert all(f.fecha.endswith("-2026") for f in filas)


def test_anio_detectado_desde_el_excel(app_sin_ui):
    app_sin_ui.excel_data, _ = leer_excel(EJ / "DATOS JG.xlsx")
    app_sin_ui._refresh_anio_field()
    assert app_sin_ui.field_vars["anio"].get() == "2026"


def _excel(tmp_path, filas, cabeceras=CABECERAS):
    wb = Workbook()
    ws = wb.active
    ws.append(["UNIVERSIDAD DE EXTREMADURA"])
    ws.append([])
    ws.append(cabeceras)
    for fila in filas:
        ws.append(fila)
    ruta = tmp_path / "datos.xlsx"
    wb.save(ruta)
    return ruta


def test_excel_con_celdas_numericas_y_filas_descartadas(tmp_path):
    ruta = _excel(
        tmp_path,
        [
            ["2026/000000005270", datetime(2026, 4, 17), 1375.77, 0, "108", "RAY", "Disc pump"],
            ["2026/5283", "18/04/2026", "100,00", "15,00", "F1", "ACME", "Material"],
            ["2026/000000005300", "18/04/2026", "50,00", "0,00", "F2", "ACME", None],
            [None, None, "24.979,75", "219,04"],
            ["Usuario: VVNUALES   Grupo: 34"],
        ],
    )
    filas, descartadas = leer_excel(ruta)

    assert [f.jg for f in filas] == ["2026/000000005270", "2026/5283"]
    assert filas[0].fecha == "17-04-2026"
    assert filas[0].importe_neto == Decimal("1375.77")
    assert filas[1].importe_neto == Decimal("85.00")
    assert filas[1].beneficiario == "ACME"
    # Solo la fila con JG y sin descripcion; ni el total ni el pie de UXXI.
    assert descartadas == [6]


def test_excel_sin_columna_obligatoria(tmp_path):
    ruta = _excel(tmp_path, [], cabeceras=CABECERAS[:-1])
    with pytest.raises(ValueError, match="descripcion"):
        leer_excel(ruta)


def test_excel_sin_cabecera(tmp_path):
    ruta = _excel(tmp_path, [], cabeceras=["otra", "cosa"])
    with pytest.raises(ValueError, match="cabeceras"):
        leer_excel(ruta)
