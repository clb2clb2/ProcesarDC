"""Ventana principal de ProcesarDC (Tkinter).

Solo presenta datos y recoge decisiones del usuario; la logica vive en los demas
modulos de `procesardc`. Las tareas largas (analizar y procesar) se ejecutan en un
hilo y su resultado vuelve a la ventana con `after()`.
"""

from __future__ import annotations

import queue
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from pypdf import PdfReader

from . import ayuda, cruce, salida, tema
from .lectura_excel import leer_excel
from .modelos import Estado, ExcelRowData, PdfPageData, Resaltado, ResultadoCruce
from .normalizacion import formatear_decimal, normalizar_jg_manual
from .ordenacion import FECHA, IMPORTE, NUMERO, TEXTO
from .secciones import EscaneoOrigen, escanear_origen, validar_carga
from .tabla import ColumnasAjustables, OrdenTabla
from . import zona_soltar
from .zona_soltar import Lineas, Segmento, ZonaSoltar
from .validacion import anio_detectado, es_anio_valido, validar_para_procesar

try:
    from tkinterdnd2 import DND_FILES, REFUSE_DROP, TkinterDnD
except ImportError:
    DND_FILES = None
    REFUSE_DROP = None
    TkinterDnD = None


BaseTk = TkinterDnD.Tk if TkinterDnD else tk.Tk

# Cada cuanto mira la ventana si ha terminado una tarea en segundo plano.
INTERVALO_TAREAS_MS = 50

# Textos de las zonas de carga.
TEXTO_ZONA_ORIGEN = "Arrastra aquí los PDFs de origen"
TEXTO_ZONA_JP = "Arrastra el PDF de justificantes de pago"
TEXTO_ZONA_EXCEL = "Arrastra el Excel de datos de justif. de gasto"
PISTA_CARGAR = "(o pulsa para cargar)"
# Alto minimo de las zonas de carga (crecen si su texto no cabe).
ALTO_ZONA_ORIGEN = 150
ALTO_ZONA = 68

# Ancho minimo de las columnas de texto largo, que se estrechan para que la tabla quepa sin barra horizontal.
ANCHO_MINIMO_AJUSTABLE = 120


MARCA_SI = "✔"
MARCA_NO = "✖"


def resumen_origen(escaneo: EscaneoOrigen) -> Lineas:
    """Lo detectado en los PDFs de origen, para la zona de carga (marcas en verde/rojo):

    DC: 1234 ✔, CJ: 5678 ✔, RT: 9001 ✔
    2 justificantes de gastos cargados ✔
    Otros archivos: ANEXO
    """

    def marca(hay: bool) -> Segmento:
        return (MARCA_SI, zona_soltar.SI) if hay else (MARCA_NO, zona_soltar.NO)

    primera: list[Segmento] = []
    for prefijo in ("DC", "CJ", "RT"):
        numero = escaneo.numero_con_prefijo(prefijo)
        if primera:
            primera.append((", ", zona_soltar.TEXTO))
        primera += [(f"{prefijo}: {numero} " if numero else f"{prefijo}: ", zona_soltar.TEXTO), marca(bool(numero))]

    total = len(escaneo.ids_jg)
    texto_jg = "1 justificante de gastos cargado " if total == 1 else f"{total} justificantes de gastos cargados "
    otros = ", ".join(escaneo.otros) or "—"
    return [
        primera,
        [(texto_jg, zona_soltar.TEXTO), marca(total > 0)],
        [(f"Otros archivos: {otros}", zona_soltar.TEXTO)],
    ]


def _app_base_dir() -> Path:
    # En el .exe de PyInstaller (onefile) __file__ apunta al directorio temporal de extraccion.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def ruta_recurso(relativa: str) -> Path:
    """Fichero empaquetado con la app: en el .exe esta en la carpeta temporal de PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relativa


RUTA_ICONO = "assets/procesardc.ico"


class App(BaseTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ProcesarDC")
        self._poner_icono()
        self.geometry("1500x860")
        self.minsize(1200, 740)

        self.base_dir = _app_base_dir()
        self.ej_dir = self.base_dir / "ej"

        self.origin_pdf_paths: list[Path] = []
        self.origin_scan = EscaneoOrigen()
        self.jp_pdf_path: Path | None = None
        self.excel_path: Path | None = None

        self.jp_pdf_data: list[PdfPageData] = []
        self.excel_data: list[ExcelRowData] = []

        self.main_results: list[ResultadoCruce] = []
        self.excel_unassigned_results: list[dict] = []
        self.main_row_by_iid: dict[str, ResultadoCruce] = {}
        self.doc_type_var = tk.StringVar(value="Remesa INV")
        self.no_jp_mode_var = tk.BooleanVar(value=False)

        self.active_job: str | None = None

        self.paleta = tema.aplicar(self)
        self._build_ui()
        self._refresh_meta_fields()
        self._update_action_buttons()

    def _poner_icono(self) -> None:
        """Icono de la ventana; `default` lo aplica tambien a la ayuda y a los dialogos."""
        icono = ruta_recurso(RUTA_ICONO)
        if not icono.exists():
            return
        try:
            self.iconbitmap(default=str(icono))
        except tk.TclError:
            pass  # sin icono propio, la app funciona igual

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        # Carga: a la izquierda (mitad del ancho) la zona de los PDFs de origen; a la derecha,
        # apilados, la casilla de "sin justificantes" y las zonas de JP y Excel.
        carga = ttk.Frame(root)
        carga.pack(fill=tk.X)
        carga.columnconfigure(0, weight=1, uniform="mitades")
        carga.columnconfigure(1, weight=1, uniform="mitades")

        self.lbl_drop_origin = self._build_drop_zone(
            carga, TEXTO_ZONA_ORIGEN, self.load_origin_pdfs, alto=ALTO_ZONA_ORIGEN, ayuda_zona=ayuda.AYUDA_ORIGEN
        )
        self.lbl_drop_origin.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        derecha = ttk.Frame(carga)
        derecha.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        derecha.columnconfigure(0, weight=1)
        self.chk_no_jp_mode = ttk.Checkbutton(
            derecha,
            text="DC sin justificantes de pago (tarjetas o pago manual)",
            variable=self.no_jp_mode_var,
            command=self._on_toggle_no_jp_mode,
        )
        self.chk_no_jp_mode.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.lbl_drop_jp = self._build_drop_zone(
            derecha, TEXTO_ZONA_JP, self.load_jp_pdf, alto=ALTO_ZONA, ayuda_zona=ayuda.AYUDA_JP
        )
        self.lbl_drop_jp.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        self.lbl_drop_excel = self._build_drop_zone(
            derecha, TEXTO_ZONA_EXCEL, self.load_excel, alto=ALTO_ZONA, ayuda_zona=ayuda.AYUDA_EXCEL
        )
        self.lbl_drop_excel.grid(row=2, column=0, sticky="nsew")
        # Si la zona de origen crece por su texto, las de la derecha se reparten el alto.
        derecha.rowconfigure(1, weight=1)
        derecha.rowconfigure(2, weight=1)

        if DND_FILES:
            self._wire_drop(self.lbl_drop_origin, self._on_drop_origin)
            self._wire_drop(self.lbl_drop_jp, self._on_drop_jp)
            self._wire_drop(self.lbl_drop_excel, self._on_drop_excel)

        # Valores que usan la validacion y el procesado (ya no se muestran en campos).
        self.field_vars = {
            "anio": tk.StringVar(value=""),
            "dc": tk.StringVar(value=""),
            "cj": tk.StringVar(value=""),
        }

        actions = ttk.Frame(root)
        actions.pack(fill=tk.X, pady=(10, 8))
        actions.columnconfigure(0, weight=0)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=0)

        self.btn_analyze = ttk.Button(
            actions, text="Analizar", command=self.analyze, style=tema.ESTILO_BOTON_PRINCIPAL
        )
        self.btn_analyze.grid(row=0, column=0, sticky="w")

        self.btn_reset = ttk.Button(actions, text="Reiniciar", command=self.confirm_reset_state)
        self.btn_reset.grid(row=0, column=2, sticky="e")

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        tab_main = ttk.Frame(self.tabs)
        tab_unassigned_excel = ttk.Frame(self.tabs)
        self.tab_unassigned_excel = tab_unassigned_excel

        self.tabs.add(tab_main, text="Resultado del analisis")
        self.tabs.add(tab_unassigned_excel, text="Filas Excel no asignadas")

        columns = [
            ("page", "Pagina", 70),
            ("fecha", "Fecha", 100),
            ("importe", "Importe", 100),
            ("factura", "Factura", 140),
            ("beneficiario", "Beneficiario", 280),
            ("concepto", "Concepto", 340),
            ("jg", "JG asignado", 120),
            ("jg_apply", "", 34),
            ("jg_candidates", "JG candidatos", 220),
        ]

        self.tree_main = self._build_table(tab_main, columns, ajustables={"beneficiario", "concepto", "jg_candidates"})
        self.tree_main.column("jg_apply", anchor="center")
        self.tree_main.tag_configure("incidencia", foreground=self.paleta.error)
        self.tree_main.tag_configure("probable_ok", foreground=self.paleta.ok)
        self.tree_main.tag_configure(
            "jg_duplicado", foreground=self.paleta.duplicado_texto, background=self.paleta.duplicado_fondo
        )
        self.tree_main.bind("<Double-1>", self._on_main_double_click, add="+")
        self.tree_main.bind("<<TreeviewSelect>>", self._on_main_selection_changed)
        self.tree_main.bind("<ButtonRelease-1>", self._on_main_click_action, add="+")
        self.orden_main = OrdenTabla(
            self.tree_main,
            {
                "page": NUMERO,
                "fecha": FECHA,
                "importe": IMPORTE,
                "factura": TEXTO,
                "beneficiario": TEXTO,
                "concepto": TEXTO,
                "jg": TEXTO,
                "jg_candidates": TEXTO,
            },
        )

        self.tree_unassigned_excel = self._build_table(
            tab_unassigned_excel,
            [
                ("jg", "JG", 120),
                ("fecha", "Fecha pago", 110),
                ("importe_neto", "Importe neto", 120),
                ("factura", "Factura", 140),
                ("beneficiario", "Beneficiario", 280),
                ("concepto", "Concepto", 560),
            ],
            ajustables={"beneficiario", "concepto"},
        )
        self.orden_excel = OrdenTabla(
            self.tree_unassigned_excel,
            {
                "jg": TEXTO,
                "fecha": FECHA,
                "importe_neto": IMPORTE,
                "factura": TEXTO,
                "beneficiario": TEXTO,
                "concepto": TEXTO,
            },
        )

        detail_frame = ttk.LabelFrame(tab_main, text="Detalle de discordancias", padding=(8, 6))
        detail_frame.pack(fill=tk.X, pady=(8, 0))

        self.detail_var = tk.StringVar(
            value="Seleccione una fila en rojo para ver el detalle de diferencias (JP/JG)."
        )
        self.lbl_mismatch_detail = ttk.Label(
            detail_frame,
            textvariable=self.detail_var,
            justify="left",
            anchor="w",
            wraplength=1420,
        )
        self.lbl_mismatch_detail.pack(fill=tk.X)

        process_frame = ttk.Frame(tab_main, padding=(0, 8, 0, 0))
        process_frame.pack(fill=tk.X)

        ttk.Label(process_frame, text="Tipo de Documento Contable:").pack(side=tk.LEFT)
        self.cmb_doc_type = ttk.Combobox(
            process_frame,
            textvariable=self.doc_type_var,
            values=["Remesa INV", "Tarjeta INV", "Remesa ORD", "Manual ORD", "Manual INV"],
            state="readonly",
            width=18,
        )
        self.cmb_doc_type.pack(side=tk.LEFT, padx=(8, 8))
        self.cmb_doc_type.current(0)

        self.btn_process = ttk.Button(
            process_frame, text="Procesar", command=self.process_documents, style=tema.ESTILO_BOTON_PRINCIPAL
        )
        self.btn_process.pack(side=tk.LEFT)
        self._update_unassigned_tab_title()

        self.status_var = tk.StringVar(value="Cargue PDF origen, JP y Excel para comenzar.")
        ttk.Label(root, textvariable=self.status_var, padding=(0, 8, 0, 0)).pack(fill=tk.X)

        if not DND_FILES:
            self.status_var.set(
                "Drag&drop no disponible: instale tkinterdnd2. Puede usar los botones de carga."
            )

    def _build_drop_zone(
        self, parent: ttk.Frame, title: str, al_pulsar, alto: int, ayuda_zona: ayuda.Ayuda
    ) -> ZonaSoltar:
        # Se arrastran ficheros encima o se pulsa para abrir el selector; el "?" abre la ayuda.
        zona = ZonaSoltar(
            parent, title, PISTA_CARGAR, self.paleta.zonas, al_pulsar=al_pulsar,
            al_ayuda=lambda: self._mostrar_ayuda(ayuda_zona, zona),
            fuente=tema.FUENTE, fuente_pista=tema.FUENTE_PISTA, alto=alto,
        )
        return zona

    def _mostrar_ayuda(self, ayuda_zona: ayuda.Ayuda, zona: ZonaSoltar) -> ayuda.VentanaAyuda:
        return ayuda.mostrar(self, ayuda_zona, zona, fuente=tema.FUENTE, fuente_titulo=tema.FUENTE_TITULO)

    @staticmethod
    def _wire_drop(widget: ZonaSoltar, handler) -> None:
        def entrar(event):
            if not widget.habilitada:
                return REFUSE_DROP
            widget.resaltar(True)
            return event.action

        def salir(event):
            widget.resaltar(False)
            return event.action

        def soltar(event):
            widget.resaltar(False)
            if not widget.habilitada:
                return REFUSE_DROP
            return handler(event)

        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<DropEnter>>", entrar)
        widget.dnd_bind("<<DropLeave>>", salir)
        widget.dnd_bind("<<Drop>>", soltar)

    def _build_table(
        self, parent: ttk.Frame, columns: list[tuple[str, str, int]], ajustables: set[str]
    ) -> ttk.Treeview:
        """Tabla sin barra horizontal: las columnas `ajustables` ceden o ganan ancho con la ventana."""
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)

        col_ids = [c[0] for c in columns]
        tree = ttk.Treeview(container, columns=col_ids, show="headings")

        for col_id, title, width in columns:
            tree.heading(col_id, text=title)
            tree.column(col_id, width=width, minwidth=20, anchor="w")
        # El ancho de diseno de cada columna ajustable es su peso en el reparto.
        tree.columnas_ajustables = ColumnasAjustables(
            tree, {c: w for c, _t, w in columns if c in ajustables}, ANCHO_MINIMO_AJUSTABLE
        )

        y_scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        return tree

    def _parse_drop_event_paths(self, raw_data: str) -> list[Path]:
        if not raw_data:
            return []

        paths: list[Path] = []
        for token in self.tk.splitlist(raw_data):
            clean = str(token).strip().strip("{}")
            if clean:
                paths.append(Path(clean))
        return paths

    def _on_drop_origin(self, event) -> None:
        files = [p for p in self._parse_drop_event_paths(event.data) if p.suffix.lower() == ".pdf"]
        if not files:
            messagebox.showwarning("Aviso", "Arrastre uno o mas archivos PDF validos.")
            return

        self._set_origin_pdfs(files)

    def _on_drop_jp(self, event) -> None:
        files = [p for p in self._parse_drop_event_paths(event.data) if p.suffix.lower() == ".pdf"]
        if len(files) != 1:
            messagebox.showwarning("Aviso", "Arrastre un unico PDF de justificantes de pago.")
            return

        self._set_jp_pdf(files[0])

    def _on_drop_excel(self, event) -> None:
        allowed = {".xlsx", ".xlsm", ".xltx", ".xltm"}
        files = [p for p in self._parse_drop_event_paths(event.data) if p.suffix.lower() in allowed]
        if len(files) != 1:
            messagebox.showwarning("Aviso", "Arrastre un unico archivo Excel valido.")
            return

        self._set_excel(files[0])

    def _update_action_buttons(self) -> None:
        self._actualizar_zonas()
        if self.active_job is not None:
            self.btn_analyze.configure(state=tk.DISABLED)
            self.btn_process.configure(state=tk.DISABLED)
            self.btn_reset.configure(state=tk.DISABLED)
            return

        no_jp_mode = bool(self.no_jp_mode_var.get())
        can_analyze = not no_jp_mode and self.jp_pdf_path is not None and self.excel_path is not None
        can_process_without_analyze = no_jp_mode and len(self.origin_pdf_paths) > 0
        self.btn_analyze.configure(state=tk.NORMAL if can_analyze else tk.DISABLED)
        self.btn_process.configure(
            state=tk.NORMAL if (len(self.main_results) > 0 or can_process_without_analyze) else tk.DISABLED
        )
        self.btn_reset.configure(state=tk.NORMAL)

    def _actualizar_zonas(self) -> None:
        """Las zonas de carga no responden mientras hay una tarea en marcha; las de JP y Excel,
        tampoco en el modo sin justificantes de pago."""
        libre = self.active_job is None
        con_jp = not self.no_jp_mode_var.get()
        self.lbl_drop_origin.habilitar(libre)
        self.lbl_drop_jp.habilitar(libre and con_jp)
        self.lbl_drop_excel.habilitar(libre and con_jp)

    def _on_toggle_no_jp_mode(self) -> None:
        no_jp_mode = bool(self.no_jp_mode_var.get())

        if no_jp_mode:
            self.status_var.set(
                "Modo sin justificantes de pago activo. No se requeriran JP ni Excel para procesar."
            )
        else:
            self.status_var.set("Modo normal activo. Cargue PDF JP y Excel para analizar.")

        self._update_action_buttons()

    def load_origin_pdfs(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Seleccionar PDFs origen",
            initialdir=str(self.ej_dir if self.ej_dir.exists() else self.base_dir),
            filetypes=[("PDF", "*.pdf")],
        )
        if not paths:
            return

        files = [Path(p) for p in paths]
        self._set_origin_pdfs(files)

    def _set_origin_pdfs(self, files: list[Path]) -> None:
        unique_sorted = sorted({f.resolve() for f in files if f.exists()}, key=lambda p: p.name.lower())
        if not unique_sorted:
            messagebox.showwarning("Aviso", "No se han seleccionado PDFs origen validos.")
            return

        error_message = self._aplicar_origen(unique_sorted)
        if error_message:
            messagebox.showerror("Error", error_message)
            return

        self.lbl_drop_origin.set_texto(resumen_origen(self.origin_scan), pista="")

        self.status_var.set(f"PDFs origen cargados: {len(self.origin_pdf_paths)}")
        self._update_action_buttons()

    def load_jp_pdf(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar PDF Justif. Pago",
            initialdir=str(self.ej_dir if self.ej_dir.exists() else self.base_dir),
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return

        self._set_jp_pdf(Path(path))

    def _set_jp_pdf(self, path: Path) -> None:
        try:
            reader = PdfReader(str(path))
            page_count = len(reader.pages)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo leer el PDF JP: {exc}")
            return

        self.jp_pdf_path = path
        self.lbl_drop_jp.set_texto(f"JP encontrados: {page_count}", pista="")
        self.status_var.set("PDF de justificantes de pago cargado correctamente.")
        self._update_action_buttons()

    def load_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar Excel datos Justif. Gastos",
            initialdir=str(self.ej_dir if self.ej_dir.exists() else self.base_dir),
            filetypes=[("Excel", "*.xlsx *.xlsm *.xltx *.xltm")],
        )
        if not path:
            return

        self._set_excel(Path(path))

    def _set_excel(self, path: Path) -> None:
        try:
            excel_rows, discarded_rows = leer_excel(path)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo leer el Excel: {exc}")
            return

        self.excel_path = path
        self.excel_data = excel_rows
        self.lbl_drop_excel.set_texto(f"JG en la tabla Excel: {len(self.excel_data)}", pista="")
        self._refresh_meta_fields()
        self.status_var.set("Excel de justificantes de gastos cargado correctamente.")
        self._update_action_buttons()

        if discarded_rows:
            shown = ", ".join(str(n) for n in discarded_rows[:15])
            if len(discarded_rows) > 15:
                shown += ", ..."
            messagebox.showwarning(
                "Filas del Excel descartadas",
                (
                    f"Se han descartado {len(discarded_rows)} fila(s) con número de justificante "
                    "porque les falta algún dato obligatorio (fecha de pago, importes, "
                    "proveedor o descripción) o el número no tiene el formato AAAA/NNNN.\n\n"
                    f"Filas: {shown}"
                ),
            )

    def _aplicar_origen(self, files: list[Path]) -> str:
        """Escanea y valida los PDFs origen; si son correctos, los deja cargados."""
        escaneo = escanear_origen(files)
        error_message = validar_carga(escaneo)
        if error_message:
            return error_message

        self.origin_pdf_paths = list(files)
        self.origin_scan = escaneo
        self._refresh_meta_fields()
        return ""

    def _refresh_meta_fields(self) -> None:
        escaneo = self.origin_scan
        self._refresh_anio_field()
        self._refresh_prefixed_number_field("dc", escaneo.numero_con_prefijo("DC"), missing_value="X")
        self._refresh_prefixed_number_field("cj", escaneo.numero_con_prefijo("CJ"), missing_value="X")

    def _refresh_anio_field(self) -> None:
        self.field_vars["anio"].set(anio_detectado(self.excel_data))

    def _refresh_prefixed_number_field(self, field_key: str, number: str, missing_value: str) -> None:
        self.field_vars[field_key].set(number or missing_value)

    def analyze(self) -> None:
        if self.no_jp_mode_var.get():
            messagebox.showinfo(
                "Analizar",
                "En modo sin justificantes de pago no es necesario analizar JP ni Excel.",
            )
            return

        if self.jp_pdf_path is None or self.excel_path is None:
            messagebox.showwarning("Aviso", "Debe cargar el PDF JP y el Excel antes de analizar.")
            return

        if self.active_job is not None:
            return

        self.status_var.set("Analizando JP vs JG...")
        jp, excel = self.jp_pdf_path, self.excel_path
        self._en_segundo_plano(
            "analyze",
            lambda: cruce.analizar_ficheros(jp, excel),
            self._on_analyze_done,
            self._on_analyze_failed,
        )

    def process_documents(self) -> None:
        if self.active_job is not None:
            return

        validation_error = self._validate_before_processing()
        if validation_error:
            messagebox.showerror("Error", validation_error)
            return

        parent_dir = filedialog.askdirectory(
            title="Seleccionar carpeta destino",
            initialdir=str(self.base_dir),
        )
        if not parent_dir:
            return

        try:
            year = self._resolve_output_year()
            if not year:
                return

            plan = self._planificar_salida(Path(parent_dir), year)

            if plan.duplicados():
                messagebox.showerror(
                    "Error",
                    "Existen conflictos internos de nombres en los archivos a generar. Revise los datos.",
                )
                return

            if plan.existentes():
                proceed = messagebox.askyesno(
                    "Conflicto de nombres",
                    (
                        "Ya existen archivos con el mismo nombre en la carpeta destino.\n"
                        "Si continua, se sobrescribiran.\n\n"
                        "Desea continuar?"
                    ),
                )
                if not proceed:
                    return

            tarea = self._preparar_salida(plan)
        except Exception as exc:
            self._on_process_failed(str(exc))
            return

        self.status_var.set(f"Procesando... Carpeta destino: {plan.carpeta}")
        self._en_segundo_plano(
            "process",
            tarea,
            lambda _resultado: self._on_process_done(plan.carpeta),
            self._on_process_failed,
        )

    def _on_process_done(self, output_dir: Path) -> None:
        self.status_var.set(f"Proceso completado. Carpeta generada: {output_dir}")
        messagebox.showinfo("Procesar", "Proceso completado correctamente.")

    def _on_process_failed(self, message: str) -> None:
        self.status_var.set("No se pudo completar el procesamiento.")
        messagebox.showerror("Error", f"No se pudo completar el procesamiento: {message}")

    def _resolve_output_year(self) -> str:
        current_year = str(datetime.now().year)
        existing_year = self.field_vars["anio"].get().strip()

        if es_anio_valido(existing_year):
            return existing_year

        if not self.no_jp_mode_var.get():
            return ""

        suggested = current_year
        chosen = simpledialog.askstring(
            "Confirmar año",
            "No se detectó año en los datos. Indique el año para la carpeta de salida:",
            initialvalue=suggested,
            parent=self,
        )

        if chosen is None:
            return ""

        chosen = str(chosen).strip()
        if not es_anio_valido(chosen):
            messagebox.showerror("Error", "El año indicado no es válido. Debe tener 4 dígitos.")
            return ""

        self.field_vars["anio"].set(chosen)
        return chosen

    def _validate_before_processing(self) -> str:
        return validar_para_procesar(
            self.origin_scan,
            dc=str(self.field_vars["dc"].get()),
            cj=str(self.field_vars["cj"].get()),
            anio=str(self.field_vars["anio"].get()),
            sin_justificantes_pago=bool(self.no_jp_mode_var.get()),
            resultados=self.main_results,
        )

    def _planificar_salida(self, parent_dir: Path, year: str) -> salida.PlanSalida:
        dc_number = int(self.field_vars["dc"].get().strip())
        cj_number = int(self.field_vars["cj"].get().strip())
        carpeta = parent_dir / salida.nombre_carpeta(year, dc_number, self.doc_type_var.get())
        return salida.planificar(carpeta, self.origin_scan.secciones, dc_number, cj_number)

    def _preparar_salida(self, plan: salida.PlanSalida) -> Callable[[], None]:
        """Tarea que escribe la salida, con los datos fijados ahora (no lee la ventana)."""
        if self.no_jp_mode_var.get():
            return lambda: salida.generar(plan)

        jp_pdf = self.jp_pdf_path
        paginas = cruce.paginas_jp_por_jg(self.main_results)
        return lambda: salida.generar(plan, jp_pdf, paginas)

    # --- Tareas en segundo plano -------------------------------------------

    def _en_segundo_plano(
        self,
        nombre: str,
        tarea: Callable[[], object],
        al_terminar: Callable[[object], None],
        al_fallar: Callable[[str], None],
    ) -> None:
        """Ejecuta `tarea` en un hilo con los botones bloqueados.

        El hilo no toca Tk: deja el resultado en una cola y la ventana la consulta con
        after() desde el hilo principal.
        """
        self.active_job = nombre
        self._update_action_buttons()
        cola: queue.Queue = queue.Queue(maxsize=1)

        def ejecutar() -> None:
            try:
                cola.put((True, tarea()))
            except Exception as exc:
                cola.put((False, str(exc)))

        threading.Thread(target=ejecutar, daemon=True).start()
        self.after(INTERVALO_TAREAS_MS, lambda: self._comprobar_tarea(cola, al_terminar, al_fallar))

    def _comprobar_tarea(self, cola: queue.Queue, al_terminar: Callable, al_fallar: Callable) -> None:
        try:
            ok, valor = cola.get_nowait()
        except queue.Empty:
            self.after(INTERVALO_TAREAS_MS, lambda: self._comprobar_tarea(cola, al_terminar, al_fallar))
            return

        self.active_job = None
        try:
            (al_terminar if ok else al_fallar)(valor)
        finally:
            # Despues del callback: p. ej. Procesar se activa cuando ya hay resultados.
            self._update_action_buttons()

    def _on_analyze_done(
        self, datos: tuple[list[PdfPageData], list[ExcelRowData], list[ResultadoCruce]]
    ) -> None:
        pdf_data, excel_data, main_results = datos
        self.jp_pdf_data = list(pdf_data)
        self.excel_data = list(excel_data)
        self.main_results = list(main_results)
        self._rebuild_excel_unassigned_results()
        self._refresh_tables()
        self._update_status_summary(prefix="Analisis completado. ")

    def _on_analyze_failed(self, message: str) -> None:
        messagebox.showerror("Error", f"Fallo durante el analisis: {message}")

    def _refresh_tables(self) -> None:
        for item in self.tree_main.get_children():
            self.tree_main.delete(item)
        self.main_row_by_iid = {}

        duplicated_jg = self._get_duplicated_assigned_jg_set()

        for row in self.main_results:
            pagina = row.pagina
            candidatos = " | ".join(row.candidatos)
            values = [
                pagina.page_number,
                pagina.fecha,
                formatear_decimal(pagina.importe),
                pagina.factura,
                pagina.beneficiario,
                pagina.concepto,
                row.jg_efectivo,
                "<-" if candidatos else "",
                candidatos,
            ]
            if row.jg_efectivo and cruce.clave_duplicado(row) in duplicated_jg:
                tags = ("jg_duplicado",)
            elif row.resaltado is Resaltado.VERDE:
                tags = ("probable_ok",)
            elif row.requiere_revision:
                tags = ("incidencia",)
            else:
                tags = ()

            iid = self.tree_main.insert("", tk.END, values=values, tags=tags)
            self.main_row_by_iid[iid] = row
        self.orden_main.al_rellenar()

        self._fill_tree(
            self.tree_unassigned_excel,
            self.excel_unassigned_results,
            ["jg", "fecha", "importe_neto", "factura", "beneficiario", "concepto"],
        )
        self.orden_excel.al_rellenar()
        self._update_unassigned_tab_title()

    @staticmethod
    def _fill_tree(tree: ttk.Treeview, rows: list[dict], keys: list[str]) -> None:
        for item in tree.get_children():
            tree.delete(item)

        for row in rows:
            values = [row.get(k, "") for k in keys]
            tree.insert("", tk.END, values=values)

    def _update_unassigned_tab_title(self) -> None:
        count = len(self.excel_unassigned_results)
        base_title = "Filas Excel no asignadas"
        title = f"{base_title} ({count})" if count != 0 else base_title
        self.tabs.tab(self.tab_unassigned_excel, text=title)

    def _on_main_selection_changed(self, _event) -> None:
        selected = self.tree_main.selection()
        if not selected:
            self.detail_var.set("Seleccione una fila en rojo para ver el detalle de diferencias (JP/JG).")
            return

        row = self.main_row_by_iid.get(selected[0])
        if not row:
            self.detail_var.set("Seleccione una fila en rojo para ver el detalle de diferencias (JP/JG).")
            return

        if not row.discrepancias:
            self.detail_var.set("La fila seleccionada no tiene discordancias detalladas.")
            return

        lines: list[str] = []
        for mm in row.discrepancias[:2]:
            lines.append(f"{mm.campo}: [JP] {mm.pdf or ''}")
            lines.append(f"{mm.campo}: [JG] {mm.excel or ''}")

        self.detail_var.set("\n".join(lines))

    def _es_clic_en_celda(self, event) -> bool:
        # Los clics en los encabezados son para ordenar, no para editar filas.
        return self.tree_main.identify_region(event.x, event.y) == "cell"

    def _on_main_double_click(self, event) -> None:
        if not self._es_clic_en_celda(event):
            return
        row_id = self.tree_main.identify_row(event.y)
        if not row_id:
            return

        row = self.main_row_by_iid.get(row_id)
        if not row:
            return

        source_name = row.pagina.source_name
        page_number = row.pagina.page_number
        user_value = simpledialog.askstring(
            "Asignacion manual de JG",
            (
                f"Archivo {source_name}, pagina {page_number}.\n"
                "Indique el JG manual (ej: 12345-26).\n"
                "Puede dejarlo vacio para limpiar la asignacion."
            ),
            initialvalue=row.jg_manual,
            parent=self,
        )

        if user_value is None:
            return

        row.jg_manual = normalizar_jg_manual(user_value)
        self._rebuild_excel_unassigned_results()
        self._refresh_tables()
        self._update_status_summary(prefix="Asignacion manual actualizada. ")

    def _on_main_click_action(self, event) -> None:
        if not self._es_clic_en_celda(event):
            return
        row_id = self.tree_main.identify_row(event.y)
        if not row_id:
            return

        col_ref = self.tree_main.identify_column(event.x)
        if not col_ref.startswith("#"):
            return

        try:
            col_idx = int(col_ref[1:]) - 1
        except ValueError:
            return

        columns = list(self.tree_main["columns"])
        if col_idx < 0 or col_idx >= len(columns):
            return

        if columns[col_idx] != "jg_apply":
            return

        row = self.main_row_by_iid.get(row_id)
        if not row:
            return

        if not row.candidatos:
            return

        row.jg_manual = row.candidatos[0]
        self._rebuild_excel_unassigned_results()
        self._refresh_tables()
        self._update_status_summary(prefix="JG candidato copiado a JG asignado. ")

    def _rebuild_excel_unassigned_results(self) -> None:
        self.excel_unassigned_results = cruce.filas_excel_no_asignadas(self.main_results, self.excel_data)

    def _count_found(self) -> int:
        return sum(1 for row in self.main_results if row.jg_efectivo)

    def _count_status(self, status: Estado) -> int:
        return sum(1 for row in self.main_results if row.estado is status)

    def _count_empty_assigned_jg(self) -> int:
        return sum(1 for row in self.main_results if not row.jg_efectivo)

    def _update_status_summary(self, prefix: str = "") -> None:
        self.status_var.set(
            (
                f"{prefix}"
                f"Encontrados: {self._count_found()} | "
                f"JG asignado vacio: {self._count_empty_assigned_jg()} | "
                f"No encontrados: {self._count_status(Estado.NO_ENCONTRADO)} | "
                f"Dudosos: {self._count_status(Estado.DUDOSO)} | "
                f"Excel no asignadas: {len(self.excel_unassigned_results)}"
            )
        )

    def _get_duplicated_assigned_jg_set(self) -> set[str]:
        return cruce.jg_duplicados(self.main_results)

    def reset_state(self) -> None:
        self.origin_pdf_paths = []
        self.origin_scan = EscaneoOrigen()
        self.jp_pdf_path = None
        self.excel_path = None

        self.jp_pdf_data = []
        self.excel_data = []
        self.main_results = []
        self.excel_unassigned_results = []

        self.lbl_drop_origin.set_texto(TEXTO_ZONA_ORIGEN, PISTA_CARGAR)
        self.lbl_drop_jp.set_texto(TEXTO_ZONA_JP, PISTA_CARGAR)
        self.lbl_drop_excel.set_texto(TEXTO_ZONA_EXCEL, PISTA_CARGAR)

        self.field_vars["anio"].set("")
        self.field_vars["dc"].set("")
        self.field_vars["cj"].set("")
        self.no_jp_mode_var.set(False)

        for item in self.tree_main.get_children():
            self.tree_main.delete(item)
        for item in self.tree_unassigned_excel.get_children():
            self.tree_unassigned_excel.delete(item)
        self.orden_main.quitar_orden()
        self.orden_excel.quitar_orden()

        self.main_row_by_iid = {}
        self._update_unassigned_tab_title()
        self.detail_var.set("Seleccione una fila en rojo para ver el detalle de diferencias (JP/JG).")
        self.status_var.set("Estado reiniciado. Cargue PDF origen, JP y Excel para comenzar.")
        self._update_action_buttons()

    def confirm_reset_state(self) -> None:
        proceed = messagebox.askyesno(
            "Confirmar reinicio",
            "Se perderan los datos cargados y los resultados actuales. Desea continuar?",
        )
        if not proceed:
            return

        self.reset_state()
