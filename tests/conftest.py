"""Utilidades comunes para los tests de caracterizacion de ProcesarDC.

Los tests ejercitan la clase App sin abrir ventana: se crea la instancia con
App.__new__ y se sustituyen las variables y widgets de Tk por dobles minimos.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from procesardc import cruce
from procesardc import ventana as app_mod
from procesardc.secciones import EscaneoOrigen

RAIZ = Path(__file__).resolve().parent.parent
EJ = RAIZ / "ej"
FIXTURES = EJ / "fixtures"

# PDF grande (~75 MB) que no esta en el repositorio. Se puede indicar otra ruta con
# la variable de entorno PROCESARDC_PDF_COMPLETO; si no existe, el escenario E se omite.
PDF_COMPLETO = Path(
    os.environ.get("PROCESARDC_PDF_COMPLETO", FIXTURES / "origen_contenedor_normal_completo.pdf")
)


class VarFalsa:
    """Sustituto de tk.StringVar / tk.BooleanVar."""

    def __init__(self, valor=""):
        self.valor = valor

    def get(self):
        return self.valor

    def set(self, valor) -> None:
        self.valor = valor


class EntryFalso:
    """Sustituto de ttk.Entry: solo acepta configure()."""

    def configure(self, **_kwargs) -> None:
        pass


def crear_app_sin_ui() -> app_mod.App:
    inst = app_mod.App.__new__(app_mod.App)
    inst.base_dir = RAIZ
    inst.ej_dir = EJ
    inst.origin_pdf_paths = []
    inst.origin_scan = EscaneoOrigen()
    inst.jp_pdf_path = None
    inst.excel_path = None
    inst.jp_pdf_data = []
    inst.excel_data = []
    inst.main_results = []
    inst.excel_unassigned_results = []
    inst.main_row_by_iid = {}
    inst.active_job = None
    inst.doc_type_var = VarFalsa("Remesa INV")
    inst.no_jp_mode_var = VarFalsa(False)
    inst.field_vars = {
        "anio": VarFalsa(""),
        "dc": VarFalsa(""),
        "cj": VarFalsa(""),
        "jg_origen": VarFalsa("X"),
        "rt": VarFalsa("—"),
        "otros": VarFalsa("—"),
    }
    inst.entry_map = {key: EntryFalso() for key in inst.field_vars}
    return inst


def cargar_origen(inst: app_mod.App, *rutas: Path) -> str:
    """Equivalente a _set_origin_pdfs sin dialogos: devuelve el error de validacion o ''."""
    archivos = sorted({r.resolve() for r in rutas}, key=lambda p: p.name.lower())
    return inst._aplicar_origen(archivos)


def analizar(inst: app_mod.App, jp: Path, excel: Path) -> None:
    """Analisis JP vs Excel sincrono; deja el estado como _on_analyze_done (sin tablas)."""
    inst.jp_pdf_path = jp
    inst.excel_path = excel
    pdf_data, excel_data, resultados = cruce.analizar_ficheros(jp, excel)
    inst.jp_pdf_data = pdf_data
    inst.excel_data = excel_data
    inst.main_results = resultados
    inst._rebuild_excel_unassigned_results()
    inst._refresh_meta_fields()


def generar_salida(inst: app_mod.App, destino: Path) -> Path:
    """Lo que hace process_documents tras los dialogos (carpeta destino, año y sobrescritura)."""
    plan = inst._planificar_salida(destino, inst.field_vars["anio"].get().strip())
    assert not plan.duplicados()
    inst._preparar_salida(plan)()
    return plan.carpeta


@pytest.fixture
def app_sin_ui() -> app_mod.App:
    return crear_app_sin_ui()
