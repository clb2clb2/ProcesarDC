"""Dialogo de asignacion manual de JG, con la pagina del justificante de pago a la vista.

`pedir_jg(...)` devuelve el texto escrito al pulsar "Asignar" ("" si se deja vacio, para
quitar la asignacion) y None si se cancela (Escape, "Cancelar" o cerrar la ventana).

Si se pasa `validar`, se llama con el texto antes de aceptarlo: si devuelve un mensaje, el
dialogo no se cierra y lo muestra en rojo bajo el campo.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

TITULO = "Asignación manual de JG"
ANCHO_TEXTO = 460  # si no hay imagen
COLOR_BORDE_IMAGEN = "#C8C8C8"
COLOR_ERROR = "#C42B1C"


class DialogoJG(tk.Toplevel):
    def __init__(
        self, parent: tk.Misc, mensaje: str, valor_inicial: str = "", imagen: tk.PhotoImage | None = None,
        fuente: str = "TkDefaultFont", estilo_principal: str = "Accent.TButton",
        validar: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(TITULO)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.resultado: str | None = None
        self.validar = validar
        self.imagen = imagen  # Tk no guarda referencia: se mantiene viva con el dialogo

        marco = ttk.Frame(self, padding=(18, 16, 18, 14))
        marco.pack(fill=tk.BOTH, expand=True)

        if imagen is not None:
            borde = tk.Frame(marco, bg=COLOR_BORDE_IMAGEN, padx=1, pady=1)
            borde.pack(anchor="center", pady=(0, 12))
            self.vista = tk.Label(borde, image=imagen, bd=0)
            self.vista.pack()
        ancho = imagen.width() if imagen is not None else ANCHO_TEXTO

        ttk.Label(marco, text=mensaje, font=fuente, wraplength=ancho, justify="left").pack(anchor="w")
        self.valor = tk.StringVar(value=valor_inicial)
        self.entrada = ttk.Entry(marco, textvariable=self.valor, width=22, font=fuente)
        self.entrada.pack(anchor="w", pady=(8, 0))
        # Mensaje de error bajo el campo (vacio mientras no haya error).
        self.error = ttk.Label(marco, text="", font=fuente, foreground=COLOR_ERROR, wraplength=ancho)
        self.error.pack(anchor="w", pady=(4, 8))
        self.valor.trace_add("write", lambda *_: self.error.configure(text=""))

        botones = ttk.Frame(marco)
        botones.pack(fill=tk.X)
        self.boton_asignar = ttk.Button(botones, text="Asignar", style=estilo_principal, command=self._asignar)
        self.boton_asignar.pack(side=tk.RIGHT)
        self.boton_cancelar = ttk.Button(botones, text="Cancelar", command=self.destroy)
        self.boton_cancelar.pack(side=tk.RIGHT, padx=(0, 8))

        self.bind("<Return>", lambda _e: self._asignar())
        self.bind("<KP_Enter>", lambda _e: self._asignar())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.entrada.focus_set()
        self.entrada.select_range(0, tk.END)

    def _asignar(self) -> None:
        texto = self.valor.get().strip()
        error = self.validar(texto) if (texto and self.validar) else ""
        if error:
            self.error.configure(text=error)
            self.entrada.focus_set()
            self.entrada.select_range(0, tk.END)
            return
        self.resultado = texto
        self.destroy()


def pedir_jg(
    parent: tk.Misc, mensaje: str, valor_inicial: str = "", imagen: tk.PhotoImage | None = None,
    fuente: str = "TkDefaultFont", validar: Callable[[str], str] | None = None,
) -> str | None:
    """Abre el dialogo (modal), centrado sobre la ventana, y espera la respuesta."""
    dialogo = DialogoJG(parent, mensaje, valor_inicial, imagen, fuente, validar=validar)
    raiz = parent.winfo_toplevel()
    dialogo.update_idletasks()
    x = raiz.winfo_rootx() + (raiz.winfo_width() - dialogo.winfo_reqwidth()) // 2
    y = raiz.winfo_rooty() + (raiz.winfo_height() - dialogo.winfo_reqheight()) // 3
    dialogo.geometry(f"+{max(0, x)}+{max(0, y)}")
    dialogo.grab_set()
    dialogo.wait_window()
    return dialogo.resultado
