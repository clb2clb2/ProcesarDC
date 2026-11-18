"""Tests con la ventana Tk real: tabla de resultados, colores y asignacion manual.

Se omiten si no hay entorno grafico disponible.
"""

from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from procesardc import ventana as app_mod
from conftest import EJ, FIXTURES


@pytest.fixture(scope="module")
def _ventana_unica():
    # Una sola ventana raiz por proceso: crear varias seguidas con tkinterdnd2 no es fiable.
    try:
        w = app_mod.App()
    except tk.TclError as exc:
        pytest.skip(f"Sin entorno grafico: {exc}")
    w.geometry("1500x860+0+0")
    w.update()
    yield w
    w.destroy()


@pytest.fixture
def ventana(_ventana_unica):
    _ventana_unica.reset_state()
    _ventana_unica.update()
    return _ventana_unica


def _esperar_tarea(w, timeout=60.0):
    """Procesa eventos de Tk hasta que termina la tarea en segundo plano."""
    limite = time.monotonic() + timeout
    while w.active_job is not None:
        assert time.monotonic() < limite, f"La tarea {w.active_job} no termina"
        w.update()
        time.sleep(0.01)
    w.update()


def _estado_botones(w):
    return {nombre: str(getattr(w, nombre)["state"]) for nombre in ("btn_analyze", "btn_process", "btn_reset")}


def _analizar(w, excel="DATOS JG.xlsx", origen="DOC contenedor ok.pdf"):
    assert w._aplicar_origen([(FIXTURES / origen).resolve()]) == ""
    w._set_jp_pdf(EJ / "JP536.pdf")
    w._set_excel(EJ / excel)
    w.analyze()  # hilo real
    assert w.active_job == "analyze"
    assert _estado_botones(w) == {"btn_analyze": "disabled", "btn_process": "disabled", "btn_reset": "disabled"}
    _esperar_tarea(w)


def _filas(w):
    tree = w.tree_main
    return [(tree.item(iid, "values"), tree.item(iid, "tags")) for iid in tree.get_children()]


def _evento(w, iid, columna="#1"):
    w.tree_main.see(iid)
    w.update()
    x, y, ancho, alto = w.tree_main.bbox(iid, columna)
    return SimpleNamespace(x=x + ancho // 2, y=y + alto // 2)


def test_tabla_tras_analizar(ventana):
    _analizar(ventana)
    filas = _filas(ventana)
    assert len(filas) == 25
    valores, _tags = filas[0]
    assert valores[0] == "1"  # pagina
    assert valores[6] == ventana.main_results[0].jg_efectivo
    assert ventana.status_var.get().startswith("Analisis completado. Encontrados: 25 | JG asignado vacio: 0")
    assert ventana.tabs.tab(ventana.tab_unassigned_excel, "text") == "Filas Excel no asignadas (1)"
    assert str(ventana.btn_process["state"]) == "normal"


def test_colores_e_incidencias(ventana):
    _analizar(ventana, excel="DATOS JG2.xlsx")
    tags_por_pagina = {int(v[0]): t for v, t in _filas(ventana)}
    for r in ventana.main_results:
        esperado = ("probable_ok",) if r.resaltado.value == "green" else ("incidencia",) if r.requiere_revision else ()
        assert tuple(tags_por_pagina[r.pagina.page_number]) == esperado
    assert any(t == ("incidencia",) for t in tags_por_pagina.values())


def test_detalle_de_discrepancias(ventana):
    _analizar(ventana, excel="DATOS JG2.xlsx")
    tree = ventana.tree_main
    con_detalle = [iid for iid in tree.get_children() if ventana.main_row_by_iid[iid].discrepancias]
    assert con_detalle
    tree.selection_set(con_detalle[0])
    ventana._on_main_selection_changed(None)
    texto = ventana.detail_var.get()
    campo = ventana.main_row_by_iid[con_detalle[0]].discrepancias[0].campo
    assert f"{campo}: [JP]" in texto and f"{campo}: [JG]" in texto


def test_doble_clic_asigna_y_resalta_duplicado(ventana, monkeypatch):
    _analizar(ventana)
    primera, segunda = ventana.tree_main.get_children()[:2]
    jg = ventana.main_row_by_iid[primera].jg_efectivo

    monkeypatch.setattr(app_mod.dialogo_jg, "pedir_jg", lambda *a, **k: f"2026/00000{jg}")
    ventana._on_main_double_click(_evento(ventana, segunda))

    filas = _filas(ventana)
    assert filas[1][0][6] == jg
    assert filas[0][1] == filas[1][1] == ("jg_duplicado",)
    assert ventana.status_var.get().startswith("Asignacion manual actualizada.")

    # Vaciar el dialogo quita la asignacion manual.
    monkeypatch.setattr(app_mod.dialogo_jg, "pedir_jg", lambda *a, **k: "")
    ventana._on_main_double_click(_evento(ventana, ventana.tree_main.get_children()[1]))
    assert _filas(ventana)[1][1] != ("jg_duplicado",)


def test_clic_en_candidato_lo_asigna(ventana):
    _analizar(ventana, excel="DATOS JG2.xlsx")
    tree = ventana.tree_main
    assert "jg_apply" not in tree["columns"]  # ya no hay columna de flecha
    iid = next(i for i in tree.get_children() if ventana.main_row_by_iid[i].candidatos)
    resultado = ventana.main_row_by_iid[iid]
    candidato = resultado.candidatos[0]

    # Sobre la celda del candidato, el cursor es una mano; fuera, no.
    evento = _evento(ventana, iid, "jg_candidates")
    ventana._cursor_sobre_candidatos(evento)
    assert str(tree["cursor"]) == "hand2"
    ventana._cursor_sobre_candidatos(_evento(ventana, iid, "fecha"))
    assert str(tree["cursor"]) == ""

    ventana._on_main_click_action(_evento(ventana, iid, "jg_candidates"))
    assert resultado.jg_manual == candidato
    assert ventana.status_var.get().startswith(f"JG candidato {candidato} copiado a JG asignado.")
    # La fila sigue seleccionada tras redibujar la tabla.
    assert ventana.main_row_by_iid[tree.selection()[0]] is resultado


def test_botones_de_candidatos_en_el_detalle(ventana):
    _analizar(ventana, excel="DATOS JG2.xlsx")
    tree = ventana.tree_main
    con = next(i for i in tree.get_children() if ventana.main_row_by_iid[i].candidatos)
    sin = next(i for i in tree.get_children() if not ventana.main_row_by_iid[i].candidatos)
    resultado = ventana.main_row_by_iid[con]

    tree.selection_set(sin)
    ventana._on_main_selection_changed(None)
    assert ventana.botones_candidatos == []

    tree.selection_set(con)
    ventana._on_main_selection_changed(None)
    textos = [str(b["text"]) for b in ventana.botones_candidatos]
    assert textos == [f"Asignar JG {c}" for c in resultado.candidatos]

    ventana.botones_candidatos[0].invoke()
    assert resultado.jg_manual == resultado.candidatos[0]


def test_candidato_pulsado():
    medir = len  # 1 pixel por caracter; el separador ", " mide 2
    assert app_mod.candidato_pulsado([], 3, medir) is None
    assert app_mod.candidato_pulsado(["5768"], 99, medir) == "5768"  # uno solo: cualquier punto
    # "5768, 5962": 5768 ocupa 0-4 y 5962 ocupa 6-10.
    assert app_mod.candidato_pulsado(["5768", "5962"], 2, medir) == "5768"
    assert app_mod.candidato_pulsado(["5768", "5962"], 8, medir) == "5962"
    assert app_mod.candidato_pulsado(["5768", "5962"], 11, medir) == "5962"
    assert app_mod.candidato_pulsado(["5768", "5962"], 40, medir) is None  # lejos del texto


def _columna(tree, col):
    return [tree.set(iid, col) for iid in tree.get_children()]


def _importe(texto):
    return Decimal(texto.replace(",", "."))


def test_ordenar_por_encabezado_cicla_asc_desc_original(ventana):
    _analizar(ventana)
    tree = ventana.tree_main
    paginas_originales = _columna(tree, "page")
    originales = [_importe(v) for v in _columna(tree, "importe")]
    assert originales != sorted(originales)  # si ya viniera ordenado, el test no probaria nada

    assert tree.heading("importe", "command")  # el clic en el encabezado tiene accion
    ventana.orden_main.clic_encabezado("importe")
    importes = [_importe(v) for v in _columna(tree, "importe")]
    assert importes == sorted(importes)
    assert tree.heading("importe", "text") == "Importe ▲"

    ventana.orden_main.clic_encabezado("importe")
    assert [_importe(v) for v in _columna(tree, "importe")] == sorted(importes, reverse=True)
    assert tree.heading("importe", "text") == "Importe ▼"

    ventana.orden_main.clic_encabezado("importe")
    assert _columna(tree, "page") == paginas_originales
    assert tree.heading("importe", "text") == "Importe"

    # Cambiar de columna empieza en ascendente y quita la flecha de la anterior.
    ventana.orden_main.clic_encabezado("importe")
    ventana.orden_main.clic_encabezado("page")
    assert [int(p) for p in _columna(tree, "page")] == sorted(int(p) for p in paginas_originales)
    assert tree.heading("importe", "text") == "Importe"
    assert tree.heading("page", "text") == "Pagina ▲"


def test_el_orden_se_mantiene_tras_asignar_y_se_quita_al_reiniciar(ventana, monkeypatch):
    _analizar(ventana)
    tree = ventana.tree_main
    ventana.orden_main.clic_encabezado("importe")
    ventana.orden_main.clic_encabezado("importe")  # descendente
    orden = _columna(tree, "page")

    segunda = tree.get_children()[1]
    jg = ventana.main_row_by_iid[segunda].jg_efectivo
    monkeypatch.setattr(app_mod.dialogo_jg, "pedir_jg", lambda *a, **k: jg)
    ventana._on_main_double_click(_evento(ventana, segunda))

    assert _columna(tree, "page") == orden
    assert tree.heading("importe", "text") == "Importe ▼"
    # El mapa fila -> resultado sigue apuntando a la fila correcta tras reordenar.
    for iid in tree.get_children():
        assert tree.set(iid, "page") == str(ventana.main_row_by_iid[iid].pagina.page_number)

    ventana.reset_state()
    assert tree.heading("importe", "text") == "Importe"
    _analizar(ventana)
    assert [int(p) for p in _columna(tree, "page")] == list(range(1, 26))


def test_clic_en_encabezado_no_edita_filas(ventana, monkeypatch):
    _analizar(ventana)
    tree = ventana.tree_main
    tree.yview_moveto(0)
    ventana.update()

    def no_debe_llamarse(*_a, **_k):
        raise AssertionError("No debe abrir el dialogo de asignacion")

    monkeypatch.setattr(app_mod.dialogo_jg, "pedir_jg", no_debe_llamarse)
    x_jg, _y, ancho, _alto = tree.bbox(tree.get_children()[0], "jg_candidates")
    encabezado = SimpleNamespace(x=x_jg + ancho // 2, y=5)
    assert tree.identify_region(encabezado.x, encabezado.y) == "heading"

    ventana._on_main_double_click(encabezado)
    ventana._on_main_click_action(encabezado)
    assert all(not r.jg_manual for r in ventana.main_results)


def test_ordenar_filas_excel_no_asignadas_por_fecha(ventana):
    _analizar(ventana, excel="DATOS JG2.xlsx")
    tree = ventana.tree_unassigned_excel
    assert len(tree.get_children()) > 1

    ventana.orden_excel.clic_encabezado("fecha")
    fechas = [datetime.strptime(f, "%d-%m-%Y") for f in _columna(tree, "fecha") if f]
    assert fechas == sorted(fechas)
    assert tree.heading("fecha", "text") == "Fecha pago ▲"


def test_tema_aplicado(ventana):
    from tkinter import ttk

    from procesardc import tema

    estilo = ttk.Style(ventana)
    assert estilo.theme_use() == "sun-valley-light"  # siempre claro, aunque Windows este en oscuro
    # Sin la llamada a configure_colors el fondo general queda sin definir (gris de Tk).
    assert str(estilo.lookup(".", "background")) == tema.PALETA.fondo
    assert str(ventana.tree_main.tag_configure("incidencia", "foreground")) == ventana.paleta.error
    assert str(ventana.tree_main.tag_configure("probable_ok", "foreground")) == ventana.paleta.ok
    assert str(ventana.btn_analyze["style"]) == tema.ESTILO_BOTON_PRINCIPAL

    # Encabezados planos (sin la imagen redondeada de sv-ttk) y con la letra normal.
    assert estilo.layout("Heading")[0][0] == tema.ELEMENTO_ENCABEZADO
    assert str(estilo.lookup("Heading", "font")) == tema.FUENTE
    assert ventana.tree_main.heading("importe", "text") == "Importe"
    assert ventana.tree_main.heading("fecha", "text") == "Fecha"



def _colores_zona(zona):
    return {zona.itemcget(i, "fill") for i in zona.find_all() if zona.type(i) == "rectangle"}


def _pulsar(zona):
    zona._pulsar(SimpleNamespace(x=5, y=5))


def test_zonas_de_carga_textos_y_estados(ventana):
    from procesardc import tema
    from procesardc.zona_soltar import DESHABILITADA, ENCIMA, NORMAL

    zonas = tema.PALETA.zonas
    zona = ventana.lbl_drop_jp
    ventana.update()
    assert not hasattr(ventana, "btn_load_jp")  # los botones de carga ya no existen
    assert (zona.texto, zona.pista) == ("Arrastra el PDF de justificantes de pago", "(o pulsa para cargar)")
    assert ventana.lbl_drop_origin.texto == "Arrastra aquí la documentación del DC"
    assert ventana.lbl_drop_excel.texto == "Arrastra el Excel de datos de justificantes de gasto"
    assert zona.itemcget("pista", "text") == "(o pulsa para cargar)"
    assert str(zona["cursor"]) == "hand2"
    # Icono pequeno a la izquierda, centrado en vertical, sin pisar el texto.
    x_icono, y_icono = zona.coords("icono")
    assert x_icono < zona.winfo_width() / 8 and abs(y_icono - zona.winfo_height() / 2) <= 1
    assert zona.bbox("icono")[2] < zona.bbox("contenido")[0]

    ventana._set_jp_pdf(EJ / "JP536.pdf")
    assert _texto_dibujado(zona) == "JP encontrados: 25"
    assert not zona.find_withtag("pista")  # cargado: sin "(o pulsa para cargar)"

    assert zona.estado == NORMAL and _colores_zona(zona) == {zonas[NORMAL].fondo, zonas[NORMAL].borde}
    zona.resaltar(True)  # fichero arrastrado encima
    assert zona.estado == ENCIMA and _colores_zona(zona) == {zonas[ENCIMA].fondo, zonas[ENCIMA].borde}
    assert _texto_dibujado(zona) == "JP encontrados: 25"  # el texto sobrevive al redibujo
    zona.resaltar(False)
    zona._set_raton(True)  # raton encima
    assert zona.estado == ENCIMA
    zona._set_raton(False)
    assert zona.estado == NORMAL

    ventana.no_jp_mode_var.set(True)
    ventana._on_toggle_no_jp_mode()
    assert zona.estado == DESHABILITADA and str(zona["cursor"]) == ""
    assert _colores_zona(zona) == {zonas[DESHABILITADA].fondo, zonas[DESHABILITADA].borde}
    assert ventana.lbl_drop_excel.estado == DESHABILITADA and ventana.lbl_drop_origin.habilitada

    ventana.reset_state()
    assert zona.habilitada and (zona.texto, zona.pista) == (
        "Arrastra el PDF de justificantes de pago", "(o pulsa para cargar)",
    )


def _texto_dibujado(zona):
    """Texto de los trozos dibujados, en orden (sin saltos de linea)."""
    return "".join(zona.itemcget(i, "text") for i in zona.find_withtag("texto"))


def test_disposicion_de_las_zonas(ventana):
    ventana.update()
    origen, jp, excel = ventana.lbl_drop_origin, ventana.lbl_drop_jp, ventana.lbl_drop_excel
    chk = ventana.chk_no_jp_mode
    ancho_total = origen.master.winfo_width()
    # La de origen ocupa la mitad izquierda y es mas alta que las otras dos.
    assert abs(origen.winfo_width() - ancho_total / 2) <= 10
    assert origen.winfo_height() > jp.winfo_height()
    # A la derecha, apilados: la casilla, la zona de JP y la de Excel.
    assert jp.winfo_rootx() > origen.winfo_rootx() + origen.winfo_width() - 1
    assert chk.winfo_rooty() < jp.winfo_rooty() < excel.winfo_rooty()
    assert jp.winfo_rootx() == excel.winfo_rootx()
    # Las tres zonas acaban a la misma altura por abajo.
    fondo = lambda w: w.winfo_rooty() + w.winfo_height()  # noqa: E731
    assert abs(fondo(origen) - fondo(excel)) <= 1


def test_zona_de_origen_muestra_lo_detectado(ventana):
    import tkinter.font as tkfont

    from procesardc import tema

    ventana._set_origin_pdfs([FIXTURES / "DOC contenedor ok.pdf"])
    ventana.update()
    zona = ventana.lbl_drop_origin
    assert zona.texto == (
        "DC: 1234 ✔, CJ: 5678 ✔, RT: 9001 ✔\n2 justificantes de gastos cargados ✔\nOtros archivos: ANEXO"
    )
    assert _texto_dibujado(zona) == zona.texto.replace("\n", "")
    assert not zona.find_withtag("pista")

    # Marcas ✔ en verde y con letra mas pequena que el texto.
    marcas = zona.find_withtag("si")
    assert len(marcas) == 4 and not zona.find_withtag("no")
    assert {zona.itemcget(i, "fill") for i in marcas} == {tema.PALETA.zonas["normal"].si}
    tam = lambda fuente: abs(tkfont.nametofont(fuente, root=ventana).actual("size"))  # noqa: E731
    assert tam(zona.itemcget(marcas[0], "font")) < tam(zona.itemcget(zona.find_withtag("texto")[0], "font"))

    # Con la ventana estrecha el texto ocupa mas renglones, pero sigue dentro de la zona.
    ventana.geometry("1200x860+0+0")
    ventana.update()
    ventana.update()
    _x0, y0, _x1, y1 = zona.bbox("contenido")
    assert y0 >= 0 and y1 <= zona.winfo_height()
    ventana.geometry("1500x860+0+0")
    ventana.update()


def _centro_ayuda(zona):
    x0, y0, x1, y1 = zona.rect_ayuda()
    return SimpleNamespace(x=(x0 + x1) / 2, y=(y0 + y1) / 2)


def test_icono_de_ayuda_en_las_tres_zonas(ventana, monkeypatch):
    from procesardc import ayuda, tema

    ventana.update()
    abiertas = []
    monkeypatch.setattr(app_mod.filedialog, "askopenfilename", lambda **k: abiertas.append("selector") or "")
    esperadas = {
        "lbl_drop_origin": ayuda.AYUDA_ORIGEN,
        "lbl_drop_jp": ayuda.AYUDA_JP,
        "lbl_drop_excel": ayuda.AYUDA_EXCEL,
    }
    for nombre, contenido in esperadas.items():
        zona = getattr(ventana, nombre)
        # Arriba a la derecha.
        x, y = zona.coords("ayuda_texto")
        assert x > zona.winfo_width() - 40 and y < 30
        # Pulsar el "?" abre la ayuda de la zona, no el selector de archivos.
        zona._pulsar(_centro_ayuda(zona))
        ventana.update()
        abierta = ventana._ventana_ayuda
        assert abierta.winfo_exists() and abierta.ayuda is contenido
        assert abiertas == []
    # Solo una a la vez: abrir la del Excel ha cerrado las anteriores.
    assert sum(isinstance(w, ayuda.VentanaAyuda) for w in ventana.winfo_children()) == 1

    # Escape la cierra (Tk descarta los eventos enviados a una ventana que aun no se ve).
    limite = time.monotonic() + 5
    while not abierta.winfo_viewable() and time.monotonic() < limite:
        ventana.update()
        time.sleep(0.02)
    abierta.focus_force()
    ventana.update()
    abierta.event_generate("<Escape>")
    ventana.update()
    assert not abierta.winfo_exists()

    # Con la zona deshabilitada (modo sin justificantes) la ayuda sigue funcionando.
    ventana.no_jp_mode_var.set(True)
    ventana._on_toggle_no_jp_mode()
    zona = ventana.lbl_drop_jp
    zona._mover_raton(_centro_ayuda(zona))
    assert str(zona["cursor"]) == "hand2"  # aunque la zona no admita clics
    # Circulo azul con "?" blanco; con el raton encima, el circulo cambia de tono.
    assert zona.itemcget("ayuda_texto", "fill").lower() == "#ffffff"
    circulo_encima = zona.itemcget("ayuda_circulo", "image")
    zona._mover_raton(SimpleNamespace(x=5, y=zona.winfo_height() - 5))
    assert zona.itemcget("ayuda_circulo", "image") != circulo_encima
    assert tema.PALETA.zonas["deshabilitada"].ayuda == tema.PALETA.zonas["normal"].ayuda  # sigue en azul
    zona._mover_raton(_centro_ayuda(zona))
    zona._pulsar(_centro_ayuda(zona))
    ventana.update()
    assert ventana._ventana_ayuda.ayuda is ayuda.AYUDA_JP
    ventana._ventana_ayuda.boton.invoke()  # "Entendido"
    zona._mover_raton(SimpleNamespace(x=5, y=zona.winfo_height() - 5))
    assert str(zona["cursor"]) == ""
    ventana.reset_state()


def test_pulsar_una_zona_abre_el_selector(ventana, monkeypatch):
    pedidos = []

    def elegir(**kwargs):
        pedidos.append(kwargs["title"])
        return str(EJ / "JP536.pdf")

    monkeypatch.setattr(app_mod.filedialog, "askopenfilename", elegir)
    _pulsar(ventana.lbl_drop_jp)
    assert pedidos == ["Seleccionar PDF Justif. Pago"]
    assert ventana.jp_pdf_path == EJ / "JP536.pdf"

    # Deshabilitada (modo sin justificantes) no abre nada.
    ventana.no_jp_mode_var.set(True)
    ventana._on_toggle_no_jp_mode()
    _pulsar(ventana.lbl_drop_jp)
    assert pedidos == ["Seleccionar PDF Justif. Pago"]

    # Soltar el boton fuera de la zona tampoco.
    ventana.no_jp_mode_var.set(False)
    ventana._on_toggle_no_jp_mode()
    ventana.lbl_drop_jp._pulsar(SimpleNamespace(x=-5, y=5))
    assert len(pedidos) == 1


def test_zonas_bloqueadas_mientras_analiza(ventana):
    assert ventana._aplicar_origen([(FIXTURES / "DOC contenedor ok.pdf").resolve()]) == ""
    ventana._set_jp_pdf(EJ / "JP536.pdf")
    ventana._set_excel(EJ / "DATOS JG.xlsx")
    ventana.analyze()
    zonas = (ventana.lbl_drop_origin, ventana.lbl_drop_jp, ventana.lbl_drop_excel)
    assert not any(z.habilitada for z in zonas)
    _esperar_tarea(ventana)
    assert all(z.habilitada for z in zonas)


def _separador(tree):
    """Coordenadas de la primera separacion entre encabezados."""
    for x in range(1, tree.winfo_width()):
        if tree.identify_region(x, 8) == "separator":
            return x, 8
    raise AssertionError("No se encuentra ninguna separacion")


def test_cursor_de_redimensionar_columnas(ventana):
    _analizar(ventana)
    tree = ventana.tree_main
    columnas = tree.columnas_ajustables
    x, y = _separador(tree)
    columnas._mover_raton(SimpleNamespace(x=x, y=y))
    assert str(tree["cursor"]) == "sb_h_double_arrow"
    x_celda, y_celda, _w, _h = tree.bbox(tree.get_children()[0], "fecha")
    columnas._mover_raton(SimpleNamespace(x=x_celda + 5, y=y_celda + 5))
    assert str(tree["cursor"]) == ""


@pytest.mark.parametrize("columna, cambio", [("concepto", 200), ("beneficiario", -100), ("factura", 300)])
def test_redimensionar_columna_mantiene_la_tabla_dentro(ventana, columna, cambio):
    _analizar(ventana)
    tree = ventana.tree_main
    ventana.update()
    columnas = tree.columnas_ajustables
    pesos_originales = dict(columnas.pesos)
    pedido = int(tree.column(columna, "width")) + cambio

    tree.column(columna, width=pedido)  # lo que hace Tk al arrastrar la separacion
    columnas.columna_redimensionada(columna, pedido)

    anchos = {c: int(tree.column(c, "width")) for c in tree["columns"]}
    assert sum(anchos.values()) <= tree.winfo_width()
    assert anchos[columna] == pedido
    assert min(anchos[c] for c in ("beneficiario", "concepto")) >= app_mod.ANCHO_MINIMO_AJUSTABLE

    # Al cambiar el tamano de la ventana se mantienen las proporciones elegidas.
    if columna in columnas.pesos:
        proporcion = anchos[columna] / sum(anchos[c] for c in columnas.pesos)
        ventana.geometry("1700x860+0+0")
        ventana.update()
        nuevos = {c: int(tree.column(c, "width")) for c in columnas.pesos}
        assert abs(nuevos[columna] / sum(nuevos.values()) - proporcion) < 0.01
        ventana.geometry("1500x860+0+0")
        ventana.update()
    # Deja la tabla como al principio para los demas tests.
    columnas.pesos = pesos_originales
    tree.column("factura", width=140)
    columnas.ajustar()


@pytest.mark.parametrize("ancho", [1200, 1500, 1900])
def test_tablas_sin_barra_horizontal(ventana, ancho):
    _analizar(ventana)
    ventana.geometry(f"{ancho}x860+0+0")
    for tree in (ventana.tree_main, ventana.tree_unassigned_excel):
        assert not str(tree["xscrollcommand"])
        ventana.tabs.select(tree.master.master)
        ventana.update()
        anchos = [int(tree.column(c, "width")) for c in tree["columns"]]
        assert sum(anchos) <= tree.winfo_width(), (ancho, anchos, tree.winfo_width())
        # Las columnas que se ajustan no bajan del minimo.
        assert min(int(tree.column(c, "width")) for c in ("beneficiario", "concepto")) >= app_mod.ANCHO_MINIMO_AJUSTABLE
    ventana.tabs.select(0)
    ventana.geometry("1500x860+0+0")
    ventana.update()


def test_reiniciar(ventana):
    _analizar(ventana)
    ventana.cmb_doc_type.current(3)  # "Manual ORD"
    ventana.reset_state()
    assert ventana.doc_type_var.get() == "Remesa INV" and ventana.cmb_doc_type.get() == "Remesa INV"
    assert _filas(ventana) == []
    assert ventana.main_results == [] and ventana.origin_scan.secciones == []
    assert ventana.field_vars["dc"].get() == ""


class Dialogos:
    """Sustituye los dialogos modales y guarda los mensajes mostrados."""

    def __init__(self, monkeypatch, carpeta: Path, anio: str | None = None, sobrescribir: bool = True):
        self.mensajes: list[tuple[str, str, str]] = []
        monkeypatch.setattr(app_mod.filedialog, "askdirectory", lambda **k: str(carpeta))
        monkeypatch.setattr(app_mod.simpledialog, "askstring", lambda *a, **k: anio)
        monkeypatch.setattr(app_mod.messagebox, "askyesno", lambda *a, **k: sobrescribir)
        for tipo in ("showinfo", "showerror", "showwarning"):
            monkeypatch.setattr(app_mod.messagebox, tipo, self._guardar(tipo))

    def _guardar(self, tipo):
        def guardar(titulo, mensaje, **_k):
            self.mensajes.append((tipo, titulo, mensaje))

        return guardar


def test_procesar_en_segundo_plano(ventana, monkeypatch, tmp_path):
    dialogos = Dialogos(monkeypatch, tmp_path, anio="2026")
    assert ventana._aplicar_origen([(FIXTURES / "DOC contenedor ok.pdf").resolve()]) == ""
    ventana.no_jp_mode_var.set(True)
    ventana._on_toggle_no_jp_mode()
    ventana._update_action_buttons()

    ventana.process_documents()
    assert ventana.active_job == "process"
    assert _estado_botones(ventana)["btn_process"] == "disabled"
    ventana.process_documents()  # un segundo clic mientras procesa no hace nada
    _esperar_tarea(ventana)

    carpeta = tmp_path / "2026000001234 (REMESA INV)"
    assert sorted(p.name for p in carpeta.iterdir()) == [
        "ANEXO.pdf", "CJ5678.pdf", "DC1234.pdf", "JG5270.pdf", "JG5283.pdf", "RT9001.pdf",
    ]
    assert dialogos.mensajes == [("showinfo", "Procesar", "Proceso completado correctamente.")]
    assert ventana.status_var.get() == f"Proceso completado. Carpeta generada: {carpeta}"
    assert _estado_botones(ventana)["btn_process"] == "normal"


def test_procesar_modo_normal_anade_paginas_jp(ventana, monkeypatch, tmp_path):
    dialogos = Dialogos(monkeypatch, tmp_path)
    _analizar(ventana)
    # El contenedor pequeño solo tiene los JG 5270 y 5283: se dejan dos paginas JP asignadas.
    for r in ventana.main_results:
        r.jg_manual = ""
    resto = [r for r in ventana.main_results if r.jg_efectivo not in {"5270", "5283"}]
    ventana.main_results = [r for r in ventana.main_results if r not in resto]
    assert ventana._validate_before_processing() == ""

    ventana.process_documents()
    _esperar_tarea(ventana)

    assert dialogos.mensajes[-1][0] == "showinfo"
    carpeta = tmp_path / "2026000001234 (REMESA INV)"
    from pypdf import PdfReader

    assert len(PdfReader(str(carpeta / "JG5270.pdf")).pages) == 2
    assert len(PdfReader(str(carpeta / "JG5283.pdf")).pages) == 2


def test_procesar_fallido_avisa_y_desbloquea(ventana, monkeypatch, tmp_path):
    dialogos = Dialogos(monkeypatch, tmp_path, anio="2026")
    assert ventana._aplicar_origen([(FIXTURES / "DOC contenedor ok.pdf").resolve()]) == ""
    ventana.no_jp_mode_var.set(True)

    def falla(*_a, **_k):
        raise OSError("disco lleno")

    monkeypatch.setattr(app_mod.salida, "generar", falla)
    ventana.process_documents()
    _esperar_tarea(ventana)

    assert dialogos.mensajes == [("showerror", "Error", "No se pudo completar el procesamiento: disco lleno")]
    assert ventana.status_var.get() == "No se pudo completar el procesamiento."
    assert _estado_botones(ventana)["btn_reset"] == "normal"


def test_analisis_fallido_avisa_y_desbloquea(ventana, monkeypatch, tmp_path):
    dialogos = Dialogos(monkeypatch, tmp_path)
    ventana.jp_pdf_path = EJ / "JP536.pdf"
    ventana.excel_path = tmp_path / "no_existe.xlsx"

    ventana.analyze()
    _esperar_tarea(ventana)

    assert len(dialogos.mensajes) == 1
    tipo, titulo, mensaje = dialogos.mensajes[0]
    assert (tipo, titulo) == ("showerror", "Error")
    assert mensaje.startswith("Fallo durante el analisis:") and "no_existe.xlsx" in mensaje
    assert _estado_botones(ventana)["btn_reset"] == "normal"


def test_ayuda_de_origen_con_ilustraciones(ventana, monkeypatch):
    from procesardc import ayuda

    ventana.update()
    zona = ventana.lbl_drop_origin
    zona._pulsar(_centro_ayuda(zona))
    ventana.update()
    texto = ventana._ventana_ayuda.texto
    # Las dos ilustraciones van intercaladas en el texto, en orden.
    assert texto.image_names() == ("origen_archivos_sueltos", "origen_un_solo_pdf")
    # Los codigos van en negrita; los pasos llevan la flecha.
    negritas = texto.tag_ranges("negrita")
    trozos_negrita = [texto.get(negritas[i], negritas[i + 1]) for i in range(0, len(negritas), 2)]
    assert {"“DC”", "“JG”", "“DOC ”", "Documento Contable", "PDF contenedor"} <= set(trozos_negrita)
    assert texto.get("1.0", "end").count(ayuda.FLECHA) == 3
    assert texto.get("1.0", "2.0").strip() == "Documentación del DC"
    # Tras cada ilustracion queda un espacio amplio.
    assert int(texto.tag_cget("imagen", "spacing3")) == ayuda.ESPACIO_TRAS_IMAGEN
    assert str(texto["state"]) == "disabled"
    # Alto limitado, con barra de desplazamiento porque el contenido no cabe.
    assert ventana._ventana_ayuda.winfo_height() <= ayuda.ALTO_VENTANA
    assert ventana._ventana_ayuda.barra.winfo_ismapped()
    ventana._ventana_ayuda.destroy()

    # Si falta un PNG, la ayuda se abre igual, sin esa imagen.
    monkeypatch.setattr(ventana, "_imagen_ayuda", lambda nombre: None)
    zona._pulsar(_centro_ayuda(zona))
    ventana.update()
    assert not ventana._ventana_ayuda.texto.image_names()
    ventana._ventana_ayuda.destroy()


@pytest.mark.parametrize("zona", ["lbl_drop_origin", "lbl_drop_jp", "lbl_drop_excel"])
def test_las_ayudas_se_abren_por_el_principio(ventana, zona):
    ventana.update()
    z = getattr(ventana, zona)
    z._pulsar(_centro_ayuda(z))
    ventana.update()
    abierta = ventana._ventana_ayuda
    assert abierta.texto.yview()[0] == 0.0
    assert abierta.winfo_height() <= __import__("procesardc.ayuda", fromlist=["x"]).ALTO_VENTANA
    abierta.destroy()


def test_pestana_con_filas_sin_asignar_destacadas(ventana):
    import tkinter.font as tkfont

    from procesardc import tema

    barra = ventana.barra_pestanas
    pagina = ventana.tab_unassigned_excel
    p = barra.pestanas[str(pagina)]
    assert not p["contador"].winfo_ismapped()  # sin datos: sin contador

    _analizar(ventana)
    assert barra.texto_completo(pagina) == "Filas Excel no asignadas (1)"
    assert p["contador"].cget("text") == " (1)"
    assert p["contador"].cget("fg") == tema.PALETA.pestanas.contador
    negrita = tkfont.nametofont(p["contador"].cget("font"), root=ventana).actual("weight")
    normal = tkfont.nametofont(p["etiqueta"].cget("font"), root=ventana).actual("weight")
    assert negrita == "bold" and normal == "normal"

    # Pulsar la pestana la selecciona y la subraya; la otra deja de estarlo.
    p["etiqueta"].event_generate("<Button-1>")
    ventana.update()
    assert ventana.tabs.select() == str(pagina)
    principal = barra.pestanas[ventana.tabs.tabs()[0]]
    assert p["subrayado"].cget("bg") == tema.PALETA.pestanas.subrayado
    assert principal["subrayado"].cget("bg") != tema.PALETA.pestanas.subrayado
    ventana.tabs.select(0)

    ventana.reset_state()
    assert not p["contador"].winfo_ismapped() and barra.texto_completo(pagina) == "Filas Excel no asignadas"


def test_jg_asignado_y_candidatos_con_el_mismo_ancho(ventana):
    _analizar(ventana)
    ventana.update()
    tree = ventana.tree_main
    assert int(tree.column("jg", "width")) == int(tree.column("jg_candidates", "width"))
    ventana.geometry("1900x860+0+0")
    ventana.update()
    assert int(tree.column("jg", "width")) == int(tree.column("jg_candidates", "width"))
    ventana.geometry("1500x860+0+0")
    ventana.update()


def test_tooltip_sobre_los_candidatos(ventana):
    from procesardc import tooltip

    _analizar(ventana, excel="DATOS JG2.xlsx")
    tree = ventana.tree_main
    tip = ventana.tooltip_candidatos
    con = next(i for i in tree.get_children() if ventana.main_row_by_iid[i].candidatos)

    def esperar_pausa():
        limite = time.monotonic() + tooltip.RETARDO_MS / 1000 + 1
        while not tip.visible and time.monotonic() < limite:
            ventana.update()
            time.sleep(0.02)

    ventana._cursor_sobre_candidatos(_evento(ventana, con, "jg_candidates"))
    assert not tip.visible  # aparece tras una breve pausa
    esperar_pausa()
    assert tip.visible and tip.texto == "Pulsa para asignar"

    # Fuera de los candidatos se oculta y no vuelve a aparecer.
    ventana._cursor_sobre_candidatos(_evento(ventana, con, "fecha"))
    assert not tip.visible
    esperar_pausa()
    assert not tip.visible


def test_dialogo_de_asignacion_muestra_la_pagina(ventana, monkeypatch):
    _analizar(ventana)
    llamadas = []

    def falso(parent, mensaje, valor_inicial="", imagen=None, fuente=None, validar=None):
        llamadas.append((mensaje, valor_inicial, imagen, validar))
        return "5283"

    monkeypatch.setattr(app_mod.dialogo_jg, "pedir_jg", falso)
    tree = ventana.tree_main
    iid = tree.get_children()[2]
    pagina = ventana.main_row_by_iid[iid].pagina.page_number
    ventana._on_main_double_click(_evento(ventana, iid))

    mensaje, _valor, imagen, validar = llamadas[0]
    assert validar == ventana._error_jg_manual  # el dialogo comprueba que el JG existe
    assert mensaje == (
        f"Indique el número de JG al que quiere asignar este Justificante de Pago (página {pagina})."
    )
    # La pagina del justificante, dibujada al ancho previsto con su proporcion (apaisada).
    assert imagen is not None and imagen.width() == app_mod.ANCHO_VISTA_JP
    assert imagen.height() < imagen.width()
    assert ventana.main_row_by_iid[tree.get_children()[2]].jg_manual == "5283"


def test_dialogo_jg_botones_y_validacion(ventana):
    from procesardc.dialogo_jg import DialogoJG

    def abrir(valor="", validar=None):
        d = DialogoJG(ventana, "Mensaje", valor, validar=validar)
        ventana.update()
        return d

    d = abrir("5270")
    assert not hasattr(d, "boton_quitar")  # ya no hay boton "Quitar asignacion"
    d.valor.set(" 6743 ")
    d.boton_asignar.invoke()
    assert d.resultado == "6743"

    d = abrir("5270")
    d.boton_cancelar.invoke()
    assert d.resultado is None

    # Con un JG que no existe, el dialogo sigue abierto y avisa en rojo; al corregirlo se acepta.
    d = abrir("", validar=lambda texto: "" if texto == "5270" else "No existe")
    d.valor.set("9999")
    d.boton_asignar.invoke()
    assert d.winfo_exists() and d.resultado is None and str(d.error["text"]) == "No existe"
    d.valor.set("5270")
    assert str(d.error["text"]) == ""  # el aviso se borra al escribir
    d.boton_asignar.invoke()
    assert d.resultado == "5270"

    # Vaciar el campo y asignar quita la asignacion (no se valida).
    d = abrir("5270", validar=lambda texto: "No existe")
    d.valor.set("")
    d.boton_asignar.invoke()
    assert d.resultado == ""


def test_jg_manual_debe_existir_en_el_dc(ventana):
    _analizar(ventana)  # Excel DATOS JG.xlsx y documentacion con los JG 5270 y 5283
    error = app_mod.ERROR_JG_NO_EXISTE
    assert error == "Ese número de JG no existe en este Documento Contable"
    assert ventana._error_jg_manual("5270") == ""
    assert ventana._error_jg_manual("2026/0005283") == ""  # cualquier formato del mismo numero
    assert ventana._error_jg_manual("05270-26") == ""
    assert ventana._error_jg_manual("99999") == error  # no esta en el Excel
    assert ventana._error_jg_manual("abc") == error
    # Esta en el Excel pero no entre los JG de la documentacion cargada.
    otro = next(
        n for n in (app_mod.id_numerico_jg(app_mod.normalizar_jg_manual(f.jg)) for f in ventana.excel_data)
        if n not in ventana.origin_scan.ids_jg
    )
    assert ventana._error_jg_manual(otro) == error
