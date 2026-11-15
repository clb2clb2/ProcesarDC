"""procesardc.ayuda: contenido de las ayudas y marcado de negritas."""

from __future__ import annotations

from procesardc import ayuda, ventana


def test_trozos_con_negrita():
    assert ayuda.trozos("Hola **DC7546** y **CJ705**.") == [
        ("Hola ", False), ("DC7546", True), (" y ", False), ("CJ705", True), (".", False),
    ]
    assert ayuda.trozos("sin marcas") == [("sin marcas", False)]


def test_las_ilustraciones_existen_a_todas_las_escalas():
    for tipo, nombre in ayuda.AYUDA_ORIGEN.bloques:
        if tipo == ayuda.IMAGEN:
            for escala in ventana.ESCALAS_AYUDA:
                assert ventana.ruta_recurso(f"assets/ayuda/{nombre}@{escala}.png").exists(), (nombre, escala)
