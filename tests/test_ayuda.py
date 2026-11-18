"""procesardc.ayuda: contenido de las ayudas y marcado de negritas."""

from __future__ import annotations

from procesardc import ayuda, ventana


def test_trozos_con_negrita():
    assert ayuda.trozos("Hola **DC7546** y **CJ705**.") == [
        ("Hola ", False), ("DC7546", True), (" y ", False), ("CJ705", True), (".", False),
    ]
    assert ayuda.trozos("sin marcas") == [("sin marcas", False)]


def test_las_ilustraciones_existen_a_todas_las_escalas():
    for contenido in (ayuda.AYUDA_ORIGEN, ayuda.AYUDA_JP, ayuda.AYUDA_EXCEL):
        for tipo, nombre in contenido.bloques:
            if tipo == ayuda.IMAGEN:
                for escala in ventana.ESCALAS_AYUDA:
                    assert ventana.ruta_recurso(f"assets/ayuda/{nombre}@{escala}.png").exists(), (nombre, escala)


def test_ayuda_de_justificantes_de_pago():
    assert ayuda.AYUDA_JP.titulo == "Justificantes de pago"
    assert ayuda.AYUDA_JP.bloques[-1] == (ayuda.IMAGEN, "justificante_pago")
    # Toda la frase en negrita, como en el documento.
    assert ayuda.trozos(ayuda.AYUDA_JP.bloques[0][1]) == [
        ("Si el Documento Contable incluye una remesa de transferencias, carga aquí el PDF descargado "
         "del banco con los justificantes de pago asociados.", True),
    ]


def test_ayuda_de_datos_de_justificantes_de_gasto():
    assert ayuda.AYUDA_EXCEL.titulo == "Datos de Justificantes de Gasto"
    imagenes = [nombre for tipo, nombre in ayuda.AYUDA_EXCEL.bloques if tipo == ayuda.IMAGEN]
    assert imagenes == ["excel_datos_a_incluir", "excel_documento_contable", "excel_exportar"]
    # La primera frase va entera en negrita; en la segunda, solo los nombres de los campos.
    primera, campos, *resto = [t for tipo, t in ayuda.AYUDA_EXCEL.bloques if tipo == ayuda.PARRAFO]
    assert [n for _t, n in ayuda.trozos(primera)] == [True]
    assert [t for t, n in ayuda.trozos(campos) if n] == [
        "Nº Registro justificante", "Fecha de pago", "Importe Total", "Importe retención",
        "Nº factura proveedor", "Nombre proveedor", "Descripción",
    ]
    assert campos.startswith("Entra en UXXI Económico ")
    assert "en la pestaña Datos Asoc. 1/2:" in resto[0]
    assert not any(n for texto in resto for _t, n in ayuda.trozos(texto))
