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

# Fuentes que define sv-ttk al cargarse.
FUENTE = "SunValleyBodyFont"
FUENTE_NEGRITA = "SunValleyBodyStrongFont"

# Estilos.
ESTILO_BOTON_PRINCIPAL = "Accent.TButton"  # propio de sv-ttk
ESTILO_CAMPO = "TEntry"
ESTILO_CAMPO_FALTA = "Falta.TEntry"


@dataclass(frozen=True)
class Paleta:
    fondo: str
    texto: str
    ok: str  # fila que cuadra o JG probable
    error: str  # fila con incidencia, dato que falta
    duplicado_texto: str
    duplicado_fondo: str
    zona_fondo: str
    zona_borde: str
    zona_activa_fondo: str
    zona_activa_borde: str


PALETA = Paleta(
    fondo="#fafafa",
    texto="#1c1c1c",
    ok="#0f7b0f",
    error="#c42b1c",
    duplicado_texto="#ffffff",
    duplicado_fondo="#c42b1c",
    zona_fondo="#ffffff",
    zona_borde="#d1d1d1",
    zona_activa_fondo="#e5f1fb",
    zona_activa_borde="#005fb8",
)


def aplicar(root: tk.Tk) -> Paleta:
    sv_ttk.set_theme("light", root)
    # sv-ttk pone el fondo, el texto y la fuente general al recibir <<ThemeChanged>>, pero Tk
    # solo lo envia si ya hay widgets ttk; con la ventana aun vacia hay que llamarlo a mano.
    root.tk.call("configure_colors")

    estilo = ttk.Style(root)
    estilo.configure(ESTILO_CAMPO_FALTA, foreground=PALETA.error)
    estilo.map(ESTILO_CAMPO_FALTA, foreground=[("readonly", PALETA.error), ("disabled", PALETA.error)])
    return PALETA
