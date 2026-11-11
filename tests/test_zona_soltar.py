"""procesardc.zona_soltar: esquinas redondeadas suavizadas."""

from __future__ import annotations

from procesardc.zona_soltar import pixeles_esquina

EXTERIOR, BORDE, FONDO = "#ffffff", "#000000", "#0000ff"


def test_esquina_superior_izquierda():
    r = 10
    px = pixeles_esquina(r, 1, EXTERIOR, BORDE, FONDO)
    assert len(px) == r and all(len(fila) == r for fila in px)
    assert px[0][0] == EXTERIOR  # fuera del arco
    assert px[r - 1][r - 1] == FONDO  # junto al centro del arco
    # En los extremos del arco (arriba a la derecha, abajo a la izquierda) esta el borde.
    assert px[0][r - 1] == px[r - 1][0] == BORDE
    # Suavizado: a lo largo del arco hay tonos intermedios entre exterior, borde y fondo.
    intermedios = {c for fila in px for c in fila} - {EXTERIOR, BORDE, FONDO}
    assert len(intermedios) > 5
    # Simetrica respecto a la diagonal.
    assert all(px[y][x] == px[x][y] for y in range(r) for x in range(r))


def test_borde_mas_grueso_ocupa_mas_pixeles():
    fino = pixeles_esquina(10, 1, EXTERIOR, BORDE, FONDO)
    grueso = pixeles_esquina(10, 3, EXTERIOR, BORDE, FONDO)
    contar = lambda px: sum(fila.count(BORDE) for fila in px)  # noqa: E731
    assert contar(grueso) > contar(fino)


def test_icono_subir():
    from procesardc.zona_soltar import pixeles_icono

    tam, color, fondo = 64, "#000000", "#ffffff"
    px = pixeles_icono(tam, color, fondo)
    assert len(px) == tam and all(len(f) == tam for f in px)
    assert px[0][0] == fondo and px[tam // 2][4] == fondo  # esquina y lateral, vacios
    assert px[tam // 2][tam // 2] == color  # asta de la flecha
    assert px[int(tam * 440 / 512)][tam // 2] == color  # fondo de la bandeja
    assert px[int(tam * 200 / 512)][int(tam * 44 / 512)] == fondo  # la bandeja no llega tan arriba
    intermedios = {c for f in px for c in f} - {color, fondo}
    assert len(intermedios) > 10  # bordes suavizados


def test_partir_en_renglones():
    from procesardc.zona_soltar import NO, SI, TEXTO, partir_en_renglones

    medir = lambda texto, estilo: len(texto)  # noqa: E731  (1 pixel por caracter)
    linea = [("DC: 1234 ", TEXTO), ("v", SI), (", CJ: ", TEXTO), ("x", NO)]

    # Cabe entera: un solo renglon, con los estilos de cada trozo.
    assert partir_en_renglones(linea, 100, medir) == [
        [("DC: ", TEXTO), ("1234 ", TEXTO), ("v", SI), (", ", TEXTO), ("CJ: ", TEXTO), ("x", NO)]
    ]
    # Estrecha: corta entre palabras y la marca sigue a su texto si cabe.
    renglones = partir_en_renglones(linea, 10, medir)
    assert ["".join(t for t, _ in r) for r in renglones] == ["DC: 1234 v", ", CJ: x"]
    assert renglones[0][-1] == ("v", SI) and renglones[1][-1] == ("x", NO)
    # Una palabra mas ancha que el renglon va sola.
    assert partir_en_renglones([("supercalifragilistico x", TEXTO)], 5, medir) == [
        [("supercalifragilistico ", TEXTO)],
        [("x", TEXTO)],
    ]


def test_a_lineas_y_texto_plano():
    from procesardc.zona_soltar import SI, TEXTO, a_lineas, texto_plano

    assert a_lineas("uno") == [[("uno", TEXTO)]]
    assert len(a_lineas("uno" + chr(10) + "dos")) == 2
    lineas = [[("A ", TEXTO), ("✔", SI)], [("B", TEXTO)]]
    assert texto_plano(lineas) == "A ✔" + chr(10) + "B"


def test_anillo_de_ayuda():
    from procesardc.zona_soltar import pixeles_anillo

    tam, color, fondo = 20, "#000000", "#ffffff"
    px = pixeles_anillo(tam, 1.4, color, fondo)
    assert len(px) == tam and all(len(f) == tam for f in px)
    assert px[tam // 2][tam // 2] == fondo  # hueco central (ahi va el "?")
    assert px[0][0] == fondo  # fuera del circulo
    # En el trazo (borde izquierdo, a media altura) el pixel es oscuro.
    r, g, b = (int(px[tam // 2][1][i : i + 2], 16) for i in (1, 3, 5))
    assert r < 128 and g < 128 and b < 128
