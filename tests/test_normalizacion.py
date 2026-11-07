"""Funciones puras de normalizacion: textos, firmas, importes, fechas y formatos de JG."""

from datetime import datetime
from decimal import Decimal

import pytest

from procesardc import cruce, lectura_excel, lectura_jp
from procesardc import normalizacion as norm
from procesardc.modelos import ExcelRowData, PdfPageData


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("1.375,77", "1375.77"),
        ("0,00", "0.00"),
        ("1.375,77 EUR", "1375.77"),
        ("1.375,77 €", "1375.77"),
        ("-1.375,77", "-1375.77"),
        ("1.375", "1375.00"),
        ("1.234.567", "1234567.00"),
        ("12.5", "12.50"),
        ("0,005", "0.01"),
        (1375.77, "1375.77"),
        (100, "100.00"),
        (100.0, "100.00"),
        (Decimal("3.456"), "3.46"),
        ("", None),
        ("   ", None),
        (None, None),
        (True, None),
        ("abc", None),
    ],
)
def test_parse_decimal(valor, esperado):
    resultado = norm.parse_decimal(valor)
    assert (str(resultado) if resultado is not None else None) == esperado


def test_format_decimal():
    assert norm.formatear_decimal(Decimal("1375.77")) == "1375,77"
    assert norm.formatear_decimal(None) == ""


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (datetime(2026, 4, 17), "17-04-2026"),
        ("17/04/2026", "17-04-2026"),
        ("17-04-2026", "17-04-2026"),
        ("2026-04-17", "17-04-2026"),
        ("17.04.2026", "17.04.2026"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_excel_date(valor, esperado):
    assert norm.normalizar_fecha_excel(valor) == esperado


def test_normalize_text_quita_acentos_y_espacios():
    assert norm.normalizar_texto("  Ñandú   café ") == "NANDU CAFE"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("Nº reg. justific.", "n reg. justific."),
        ("Fecha Pago", "fecha pago"),
        ("Importe Retención", "importe retencion"),
        ("Descripción", "descripcion"),
        (None, ""),
    ],
)
def test_normalize_header_name(valor, esperado):
    assert norm.normalizar_cabecera(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("2026/000000005270", "5270-26"),
        ("2026/5270", "5270-26"),
        ("5270-26", "5270-26"),
        ("abc", "abc"),
        ("", ""),
    ],
)
def test_format_jg(valor, esperado):
    assert norm.formatear_jg(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("5270-26", "5270"),
        ("5270 - 26", "5270"),
        ("005270", "5270"),
        ("0", "0"),
        ("5270ABC", "5270"),
        ("ABC", "ABC"),
        ("", ""),
    ],
)
def test_jg_number_only(valor, esperado):
    assert norm.jg_solo_numero(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        # Todas las formas quedan en el numero (antes "2026/..." quedaba como "5270-26").
        ("2026/000000005270", "5270"),
        ("5270-26", "5270"),
        ("05270-26", "5270"),
        ("5270", "5270"),
        (" abc ", "ABC"),
        ("", ""),
    ],
)
def test_normalize_manual_jg_input(valor, esperado):
    assert norm.normalizar_jg_manual(valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("5270-26", "5270"), ("05270", "5270"), ("X", ""), ("", "")],
)
def test_extract_numeric_jg_id(valor, esperado):
    assert norm.id_numerico_jg(valor) == esperado


def test_concept_signature():
    assert norm.firma_concepto("PMFD (5270-26) Disc Pump") == "PMFD527026DISCPUMP"
    # Une palabras cortadas por la extraccion de texto del PDF.
    assert norm.firma_concepto("C OMPRA DE MATERIA L") == "COMPRADEMATERIAL"
    assert norm.firma_concepto("A" * 100) == "A" * 75


def test_beneficiary_signature():
    assert norm.firma_beneficiario("Ray & Ingeniería, S.L.") == "RAYINGENIERIA,S.L."
    assert len(norm.firma_beneficiario("X" * 40)) == 25


def test_factura_signature():
    assert norm.firma_factura("fac_ 001 / 26") == "FAC001/26"


@pytest.mark.parametrize(
    ("bloque", "esperado"),
    [
        ("Factura: 108 - PMFD (5270-26) Disc", ("108", "PMFD (5270-26) Disc")),
        # Elige el separador cuyo lado derecho empieza por 4 letras.
        ("Factura: A-1 - 22 - Compra material", ("A-1 - 22", "Compra material")),
        # Si no hay ninguno asi, usa el primer " - ".
        ("Factura: 12 - 34", ("12", "34")),
        ("Pago sin factura", ("", "Pago sin factura")),
        ("Factura: sin separador", ("", "Factura: sin separador")),
    ],
)
def test_split_factura_concepto(bloque, esperado):
    assert lectura_jp.separar_factura_concepto(bloque) == esperado


def _pagina(fecha="17-04-2026", factura="", concepto=""):
    return PdfPageData("JP.pdf", 1, fecha, Decimal("1.00"), factura, "BENEF", concepto)


def test_extract_probable_jg():
    assert cruce.extraer_jg_probable(_pagina(factura="F 0123-26")) == ("123-26", "factura")
    assert cruce.extraer_jg_probable(_pagina(concepto="PMFD (5270-26) Disc")) == ("5270-26", "concepto")
    # El año de la fecha manda: -25 no encaja con una fecha de 2026.
    assert cruce.extraer_jg_probable(_pagina(concepto="PMFD (5270-25) Disc")) == ("", "")
    # Solo se mira el principio del concepto (30 caracteres).
    assert cruce.extraer_jg_probable(_pagina(concepto="X" * 30 + "(5270-26)")) == ("", "")
    assert cruce.extraer_jg_probable(_pagina(fecha="", concepto="(5270-26)")) == ("", "")


@pytest.mark.parametrize(
    "beneficiario",
    [
        "EUR>> RAY INGENIERIA ELECTRONICA, S.L.\nPOR CUENTA DE: UNIVERSIDAD",  # texto de PyPDF2
        "EUR >> RAY INGENIERIA ELECTRONICA, S.L.\nPOR CUENTA DE: UNIVERSIDAD",  # texto de pypdf
    ],
)
def test_parse_pdf_page(beneficiario):
    texto = (
        "Fecha operación: 17-04-2026\nImporte ordenado: 1.375,77 EUR\n"
        f"{beneficiario}\n"
        "CONCEPTO: Factura: 108 - PMFD (5270-26) Disc Pump"
    )
    pagina = lectura_jp.parsear_pagina_jp(texto, 3, "JP.pdf")
    assert pagina == PdfPageData(
        source_name="JP.pdf",
        page_number=3,
        fecha="17-04-2026",
        importe=Decimal("1375.77"),
        factura="108",
        beneficiario="RAY INGENIERIA ELECTRONICA, S.L.",
        concepto="PMFD (5270-26) Disc Pump",
    )


def test_importe_neto():
    fila = ExcelRowData(1, "2026/1", "17-04-2026", Decimal("100.00"), Decimal("15.00"), "", "B", "C")
    assert fila.importe_neto == Decimal("85.00")
    assert ExcelRowData(1, "2026/1", "", None, Decimal("1"), "", "B", "C").importe_neto is None


@pytest.mark.parametrize(
    ("jg", "valido"),
    [
        ("2026/000000005270", True),
        ("2026/5270", True),
        ("1999/5270", False),
        ("Usuario: VVNUALES", False),
        ("", False),
    ],
)
def test_validacion_jg_excel(jg, valido):
    assert lectura_excel.es_fila_valida(jg, "17-04-2026", Decimal("1"), Decimal("0"), "B", "C") is valido
