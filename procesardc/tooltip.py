"""Tooltip sencillo para Tk: un recuadro con texto junto al cursor, tras una breve pausa."""

from __future__ import annotations

import tkinter as tk

RETARDO_MS = 450
DESPLAZAMIENTO = (14, 20)  # pixeles a la derecha y por debajo del cursor


class Tooltip:
    def __init__(
        self, widget: tk.Misc, fuente: str = "TkDefaultFont", fondo: str = "#FFFFFF",
        texto_color: str = "#1C1C1C", borde: str = "#C8C8C8", retardo_ms: int = RETARDO_MS,
    ) -> None:
        self.widget = widget
        self.fuente, self.fondo, self.texto_color, self.borde = fuente, fondo, texto_color, borde
        self.retardo_ms = retardo_ms
        self.ventana: tk.Toplevel | None = None
        self.texto = ""
        self._posicion = (0, 0)
        self._pendiente: str | None = None

    @property
    def visible(self) -> bool:
        return self.ventana is not None

    def mostrar(self, texto: str, x_pantalla: int, y_pantalla: int) -> None:
        """Muestra `texto` cerca de (x, y) de pantalla: tras la pausa si aun no se ve; si ya se
        ve con el mismo texto, solo lo mueve."""
        self._posicion = (x_pantalla + DESPLAZAMIENTO[0], y_pantalla + DESPLAZAMIENTO[1])
        if self.visible and texto == self.texto:
            self.ventana.geometry(f"+{self._posicion[0]}+{self._posicion[1]}")
            return
        self.texto = texto
        if self.visible:
            self._crear()
        elif self._pendiente is None:
            self._pendiente = self.widget.after(self.retardo_ms, self._crear)

    def ocultar(self) -> None:
        if self._pendiente is not None:
            self.widget.after_cancel(self._pendiente)
            self._pendiente = None
        if self.ventana is not None:
            self.ventana.destroy()
            self.ventana = None

    def _crear(self) -> None:
        self._pendiente = None
        if self.ventana is not None:
            self.ventana.destroy()
        self.ventana = tk.Toplevel(self.widget)
        self.ventana.overrideredirect(True)  # sin barra de titulo ni bordes de ventana
        self.ventana.attributes("-topmost", True)
        marco = tk.Frame(self.ventana, bg=self.borde, padx=1, pady=1)
        marco.pack()
        tk.Label(
            marco, text=self.texto, font=self.fuente, bg=self.fondo, fg=self.texto_color, padx=8, pady=3
        ).pack()
        self.ventana.geometry(f"+{self._posicion[0]}+{self._posicion[1]}")
