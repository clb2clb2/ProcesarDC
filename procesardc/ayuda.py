"""Ayuda de las zonas de carga: que archivos se esperan en cada una.

`mostrar(parent, ayuda, cerca_de)` abre una ventanita junto al widget `cerca_de`.
Solo hay una abierta a la vez; se cierra con el boton, con Escape o abriendo otra.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

PARRAFO = "p"
VINETA = "li"

ANCHO_TEXTO = 460  # pixeles


@dataclass(frozen=True)
class Ayuda:
    titulo: str
    bloques: tuple[tuple[str, str], ...]  # (PARRAFO | VINETA, texto)


AYUDA_ORIGEN = Ayuda(
    "PDFs de origen",
    (
        (PARRAFO, "Uno o varios PDF con la documentación del Documento Contable. "
                  "Se admiten dos formas, que pueden combinarse:"),
        (VINETA, "Archivos sueltos nombrados por su tipo y número: DC3391.pdf (Documento Contable), "
                 "CJ0238.pdf (Cuenta Justificativa) y RT536.pdf. Se copian tal cual."),
        (VINETA, "Un PDF con marcadores, en el que cada marcador indica dónde empieza un documento: "
                 "DC…, CJ… y RT… como los archivos sueltos; los marcadores numéricos (por ejemplo, "
                 "5270) son los justificantes de gasto (JG), y cualquier otro título (ANEXO, PARAM…) "
                 "se guarda con ese nombre."),
        (VINETA, "Un PDF sin marcadores con otro nombre se copia con su nombre (por ejemplo, ANEXO.pdf)."),
        (PARRAFO, "Tiene que haber exactamente un DC y una CJ, y al menos un JG. "
                  "No se puede repetir ningún documento ni número de JG."),
    ),
)

AYUDA_JP = Ayuda(
    "PDF de justificantes de pago",
    (
        (PARRAFO, "Un único PDF con las órdenes de transferencia emitidas por el banco, "
                  "una transferencia por página."),
        (PARRAFO, "De cada página se leen la fecha de operación, el importe ordenado, el beneficiario "
                  "y el concepto (con el número de factura) para cruzarlos con el Excel."),
        (PARRAFO, "No hace falta si se marca «DC sin justificantes de pago»."),
    ),
)

AYUDA_EXCEL = Ayuda(
    "Excel de justificantes de gasto",
    (
        (PARRAFO, "El Excel (.xlsx) exportado de UXXI con la selección paramétrica de justificantes "
                  "del gasto. Debe tener estas columnas:"),
        (VINETA, "Nº reg. justific. (con el formato AAAA/NNNN)"),
        (VINETA, "Fecha pago"),
        (VINETA, "Importe total e Importe retención"),
        (VINETA, "Factura proveedor"),
        (VINETA, "Nombre proveedor"),
        (VINETA, "Descripción"),
        (PARRAFO, "Las filas a las que les falte alguno de estos datos se descartan, y se avisa de ello."),
        (PARRAFO, "No hace falta si se marca «DC sin justificantes de pago»."),
    ),
)


class VentanaAyuda(tk.Toplevel):
    def __init__(self, parent: tk.Misc, ayuda: Ayuda, fuente: str, fuente_titulo: str) -> None:
        super().__init__(parent)
        self.ayuda = ayuda
        self.title(f"Ayuda: {ayuda.titulo}")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        marco = ttk.Frame(self, padding=(18, 14, 18, 14))
        marco.pack(fill=tk.BOTH, expand=True)
        ttk.Label(marco, text=ayuda.titulo, font=fuente_titulo).pack(anchor="w", pady=(0, 8))
        for tipo, texto in ayuda.bloques:
            if tipo == VINETA:
                fila = ttk.Frame(marco)
                fila.pack(fill=tk.X, anchor="w", pady=(0, 3))
                ttk.Label(fila, text="•", font=fuente).pack(side=tk.LEFT, anchor="n", padx=(6, 6))
                ttk.Label(fila, text=texto, font=fuente, wraplength=ANCHO_TEXTO - 24, justify="left").pack(
                    side=tk.LEFT, anchor="w"
                )
            else:
                ttk.Label(marco, text=texto, font=fuente, wraplength=ANCHO_TEXTO, justify="left").pack(
                    anchor="w", pady=(4, 6)
                )
        self.boton = ttk.Button(marco, text="Entendido", command=self.destroy, style="Accent.TButton")
        self.boton.pack(anchor="e", pady=(8, 0))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.boton.focus_set()


def mostrar(parent: tk.Misc, ayuda: Ayuda, cerca_de: tk.Misc, fuente: str, fuente_titulo: str) -> VentanaAyuda:
    """Abre la ayuda sobre la esquina superior derecha de `cerca_de` (donde esta el icono),
    sin salirse de la pantalla. Cierra la que hubiera abierta."""
    raiz = parent.winfo_toplevel()
    anterior = getattr(raiz, "_ventana_ayuda", None)
    if anterior is not None and anterior.winfo_exists():
        anterior.destroy()

    ventana = VentanaAyuda(raiz, ayuda, fuente, fuente_titulo)
    raiz._ventana_ayuda = ventana
    ventana.update_idletasks()
    ancho, alto = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
    x = cerca_de.winfo_rootx() + cerca_de.winfo_width() - ancho
    y = cerca_de.winfo_rooty() + 8
    x = max(0, min(x, ventana.winfo_screenwidth() - ancho))
    y = max(0, min(y, ventana.winfo_screenheight() - alto - 40))
    ventana.geometry(f"+{x}+{y}")
    return ventana
