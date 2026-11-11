"""Icono de la app: assets/procesardc.ico (generado con tools/generar_icono.py)."""

from __future__ import annotations

import struct

from procesardc import ventana

TAMANOS_WINDOWS = {16, 20, 24, 32, 40, 48, 64, 96, 128, 256}


def test_el_ico_trae_todos_los_tamanos():
    ruta = ventana.ruta_recurso(ventana.RUTA_ICONO)
    datos = ruta.read_bytes()
    _reservado, tipo, n = struct.unpack("<HHH", datos[:6])
    assert tipo == 1  # icono
    tamanos = set()
    for i in range(n):
        ancho, alto, _c, _r, _p, bits, largo, desplazamiento = struct.unpack("<BBBBHHII", datos[6 + 16 * i:22 + 16 * i])
        assert ancho == alto and bits == 32
        assert datos[desplazamiento:desplazamiento + 8] == b"\x89PNG\r\n\x1a\n"
        assert desplazamiento + largo <= len(datos)
        tamanos.add(ancho or 256)
    assert tamanos == TAMANOS_WINDOWS


def test_el_svg_de_origen_esta_en_assets():
    assert ventana.ruta_recurso("assets/ProcesarDC_icono.svg").exists()
