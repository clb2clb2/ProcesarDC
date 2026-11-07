"""Tests con la ventana Tk real: tabla de resultados, colores y asignacion manual.

Se omiten si no hay entorno grafico disponible.
"""

from __future__ import annotations

import time
import tkinter as tk
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


def _analizar(w, excel="DATOS JG.xlsx", origen="origen_contenedor_ok.pdf"):
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

    monkeypatch.setattr(app_mod.simpledialog, "askstring", lambda *a, **k: f"2026/00000{jg}")
    ventana._on_main_double_click(_evento(ventana, segunda))

    filas = _filas(ventana)
    assert filas[1][0][6] == jg
    assert filas[0][1] == filas[1][1] == ("jg_duplicado",)
    assert ventana.status_var.get().startswith("Asignacion manual actualizada.")

    # Vaciar el dialogo quita la asignacion manual.
    monkeypatch.setattr(app_mod.simpledialog, "askstring", lambda *a, **k: "")
    ventana._on_main_double_click(_evento(ventana, ventana.tree_main.get_children()[1]))
    assert _filas(ventana)[1][1] != ("jg_duplicado",)


def test_flecha_copia_el_primer_candidato(ventana):
    _analizar(ventana, excel="DATOS JG2.xlsx")
    tree = ventana.tree_main
    iid = next(i for i in tree.get_children() if ventana.main_row_by_iid[i].candidatos)
    resultado = ventana.main_row_by_iid[iid]

    ventana._on_main_click_action(_evento(ventana, iid, "jg_apply"))

    assert resultado.jg_manual == resultado.candidatos[0]
    assert ventana.status_var.get().startswith("JG candidato copiado a JG asignado.")


def test_reiniciar(ventana):
    _analizar(ventana)
    ventana.reset_state()
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
    assert ventana._aplicar_origen([(FIXTURES / "origen_contenedor_ok.pdf").resolve()]) == ""
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
    assert ventana._aplicar_origen([(FIXTURES / "origen_contenedor_ok.pdf").resolve()]) == ""
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
