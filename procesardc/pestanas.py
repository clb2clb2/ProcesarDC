"""Fila de pestanas propia para un ttk.Notebook, con un contador destacado en cada pestana.

Las pestanas de ttk solo admiten un formato para todo su texto. Esta fila se dibuja encima
del Notebook (cuyas pestanas se ocultan) y permite, por ejemplo, poner en rojo y negrita
el numero de filas pendientes: "Filas Excel no asignadas (3)".
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

ESTILO_SIN_PESTANAS = "SinPestanas.TNotebook"
GROSOR_SUBRAYADO = 3


@dataclass(frozen=True)
class EstiloPestanas:
    fondo: str
    texto: str  # pestana activa
    texto_inactiva: str
    texto_encima: str  # raton encima de una pestana inactiva
    subrayado: str  # linea bajo la pestana activa
    linea_base: str  # linea fina bajo toda la fila
    contador: str  # color del contador destacado


def ocultar_pestanas(estilo: ttk.Style) -> str:
    """Estilo de Notebook sin su fila de pestanas (se usa con BarraPestanas)."""
    estilo.layout(f"{ESTILO_SIN_PESTANAS}.Tab", [])
    return ESTILO_SIN_PESTANAS


class BarraPestanas(tk.Frame):
    def __init__(
        self, parent: tk.Misc, cuaderno: ttk.Notebook, estilo: EstiloPestanas, fuente: str, fuente_contador: str
    ) -> None:
        super().__init__(parent, bg=estilo.fondo, highlightthickness=0, bd=0)
        self.cuaderno = cuaderno
        self.estilo = estilo
        self.fuente, self.fuente_contador = fuente, fuente_contador
        self.pestanas: dict[str, dict[str, tk.Widget]] = {}  # por nombre de la pagina en el Notebook
        self._raton: str | None = None

        self.fila = tk.Frame(self, bg=estilo.fondo)
        self.fila.pack(side=tk.TOP, anchor="w")
        tk.Frame(self, bg=estilo.linea_base, height=1).pack(side=tk.TOP, fill=tk.X)
        cuaderno.bind("<<NotebookTabChanged>>", lambda _e: self._pintar(), add="+")

    def agregar(self, pagina: tk.Widget, texto: str) -> None:
        """Anade al Notebook la `pagina` y su pestana a esta fila."""
        self.cuaderno.add(pagina, text=texto)
        nombre = str(pagina)
        e = self.estilo
        caja = tk.Frame(self.fila, bg=e.fondo, cursor="hand2")
        caja.pack(side=tk.LEFT, padx=(0, 6))
        interior = tk.Frame(caja, bg=e.fondo)
        interior.pack(side=tk.TOP, padx=14, pady=(8, 6))
        etiqueta = tk.Label(interior, text=texto, font=self.fuente, bg=e.fondo, bd=0)
        etiqueta.pack(side=tk.LEFT)
        contador = tk.Label(interior, text="", font=self.fuente_contador, fg=e.contador, bg=e.fondo, bd=0)
        subrayado = tk.Frame(caja, height=GROSOR_SUBRAYADO, bg=e.fondo)
        subrayado.pack(side=tk.BOTTOM, fill=tk.X)
        self.pestanas[nombre] = {"caja": caja, "etiqueta": etiqueta, "contador": contador, "subrayado": subrayado}

        for widget in (caja, interior, etiqueta, contador):
            widget.bind("<Button-1>", lambda _e, p=pagina: self.cuaderno.select(p))
            widget.bind("<Enter>", lambda _e, n=nombre: self._set_raton(n))
            widget.bind("<Leave>", lambda _e: self._set_raton(None))
        self._pintar()

    def set_texto(self, pagina: tk.Widget, texto: str, contador: int = 0) -> None:
        """Texto de la pestana y contador destacado entre parentesis (oculto si es 0)."""
        p = self.pestanas[str(pagina)]
        p["etiqueta"].configure(text=texto)
        if contador:
            p["contador"].configure(text=f" ({contador})")
            p["contador"].pack(side=tk.LEFT)
        else:
            p["contador"].configure(text="")
            p["contador"].pack_forget()
        # Se mantiene tambien en la pestana (oculta) del Notebook, con el texto completo.
        self.cuaderno.tab(pagina, text=f"{texto} ({contador})" if contador else texto)

    def texto_completo(self, pagina: tk.Widget) -> str:
        p = self.pestanas[str(pagina)]
        return p["etiqueta"].cget("text") + p["contador"].cget("text")

    def _set_raton(self, nombre: str | None) -> None:
        self._raton = nombre
        self._pintar()

    def _pintar(self) -> None:
        activa = self.cuaderno.select()
        e = self.estilo
        for nombre, p in self.pestanas.items():
            es_activa = nombre == activa
            color = e.texto if es_activa else e.texto_encima if nombre == self._raton else e.texto_inactiva
            p["etiqueta"].configure(fg=color)
            p["subrayado"].configure(bg=e.subrayado if es_activa else e.fondo)
