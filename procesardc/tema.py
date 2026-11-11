"""Aspecto de la aplicacion: tema Sun Valley claro (sv-ttk, estilo Windows 11).

`aplicar(root)` carga el tema y devuelve la `Paleta` con los colores que el tema no
cubre: estados de las filas, zonas de arrastre y avisos. La app usa siempre el tema
claro, sea cual sea el modo de Windows.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

import sv_ttk

from .zona_soltar import DESHABILITADA, ENCIMA, NORMAL, EstiloZona

# Fuentes que define sv-ttk al cargarse.
FUENTE = "SunValleyBodyFont"
FUENTE_PISTA = "SunValleyCaptionFont"
FUENTE_TITULO = "SunValleyBodyStrongFont"

# Estilos.
ESTILO_BOTON_PRINCIPAL = "Accent.TButton"  # propio de sv-ttk


@dataclass(frozen=True)
class Paleta:
    fondo: str
    texto: str
    ok: str  # fila que cuadra o JG probable
    error: str  # fila con incidencia, dato que falta
    duplicado_texto: str
    duplicado_fondo: str
    zonas: dict[str, EstiloZona]  # zonas de carga: normal, encima (raton o fichero) y deshabilitada


PALETA = Paleta(
    fondo="#fafafa",
    texto="#1c1c1c",
    ok="#0f7b0f",
    error="#c42b1c",
    duplicado_texto="#ffffff",
    duplicado_fondo="#c42b1c",
    zonas={
        NORMAL: EstiloZona(
            fondo_exterior="#fafafa",
            fondo="#eef5fd",
            borde="#1f4f8f",
            grosor_borde=1,
            texto="#1c1c1c",
            pista="#5f6b7a",
            si="#0f7b0f",
            no="#c42b1c",
            icono="#d2d8e0",
        ),
        ENCIMA: EstiloZona(
            fondo_exterior="#fafafa",
            fondo="#d9e9fb",
            borde="#005fb8",
            grosor_borde=2,
            texto="#1c1c1c",
            pista="#4a5868",
            si="#0f7b0f",
            no="#c42b1c",
            icono="#b8c5d5",
        ),
        DESHABILITADA: EstiloZona(
            fondo_exterior="#fafafa",
            fondo="#f3f3f3",
            borde="#c8c8c8",
            grosor_borde=1,
            texto="#a0a0a0",
            pista="#b4b4b4",
            si="#b4b4b4",
            no="#b4b4b4",
            icono="#e2e2e2",
        ),
    },
)


def aplicar(root: tk.Tk) -> Paleta:
    sv_ttk.set_theme("light", root)
    # sv-ttk pone el fondo, el texto y la fuente general al recibir <<ThemeChanged>>, pero Tk
    # solo lo envia si ya hay widgets ttk; con la ventana aun vacia hay que llamarlo a mano.
    root.tk.call("configure_colors")

    estilo = ttk.Style(root)
    _encabezados_planos(root, estilo)
    return PALETA


# Encabezados de tabla planos (sv-ttk los dibuja con esquinas redondeadas y letra pequena).
ELEMENTO_ENCABEZADO = "Plano.Treeheading.cell"
ENCABEZADO_FONDOS = {"reposo": "#f0f0f0", "encima": "#e5e5e5", "pulsado": "#dadada"}
ENCABEZADO_LINEA_INFERIOR = "#cfcfcf"
ENCABEZADO_SEPARADOR = "#dcdcdc"


def _imagen_encabezado(root: tk.Misc, fondo: str) -> tk.PhotoImage:
    """4 x 4 pixeles: fondo, separador a la derecha y linea abajo. Con border=(0, 0, 1, 1)
    Tk estira el fondo y conserva el separador y la linea."""
    lado = 4
    filas = []
    for y in range(lado):
        fila = [
            ENCABEZADO_LINEA_INFERIOR if y == lado - 1 else ENCABEZADO_SEPARADOR if x == lado - 1 else fondo
            for x in range(lado)
        ]
        filas.append("{" + " ".join(fila) + "}")
    img = tk.PhotoImage(master=root, width=lado, height=lado)
    img.put(" ".join(filas))
    return img


def _encabezados_planos(root: tk.Tk, estilo: ttk.Style) -> None:
    if ELEMENTO_ENCABEZADO not in estilo.element_names():
        imagenes = {k: _imagen_encabezado(root, c) for k, c in ENCABEZADO_FONDOS.items()}
        root._imagenes_encabezado = imagenes  # Tk no guarda referencia: sin esto se borrarian
        estilo.element_create(
            ELEMENTO_ENCABEZADO, "image", imagenes["reposo"],
            ("pressed", imagenes["pulsado"]), ("active", imagenes["encima"]),
            border=(0, 0, 1, 1), padding=(8, 6, 8, 6), sticky="nsew",
        )
    # Mismo layout que el de sv-ttk, cambiando solo la celda de fondo.
    layout = [
        (ELEMENTO_ENCABEZADO if nombre == "Treeheading.cell" else nombre, opciones)
        for nombre, opciones in estilo.layout("Heading")
    ]
    estilo.layout("Heading", layout)
    estilo.configure("Heading", font=FUENTE)
