"""Ventana que explica como corregir los marcadores de JG del PDF que no cuadran con el Excel.

Muestra una correccion cada vez (con "Anterior"/"Siguiente"): a la izquierda la pagina del PDF
donde esta el marcador, en la que se ve el numero del justificante, y a la derecha el marcador
actual tachado en rojo y el que deberia tener en verde.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from .sugerencias_jg import Sugerencia, Tipo

TITULO = "Revisión de marcadores de JG"
INTRO = "Los justificantes de gasto marcados en el PDF no coinciden con el Excel de datos de JG."
AVISO_FINAL = "Corrija los marcadores del PDF de justificantes de gasto y vuelva a cargar el archivo."

ANCHO_VISTA = 440
ALTO_VISTA = 560
ANCHO_DETALLE = 340
COLOR_BORDE_IMAGEN = "#C8C8C8"
COLOR_MAL = "#C42B1C"
COLOR_BIEN = "#0F7B0F"
COLOR_SECUNDARIO = "#5D5D5D"
TAMANO_NUMERO = 26

# Dibuja la pagina: (master, ruta, pagina, ancho, alto) -> PhotoImage | None.
Dibujante = Callable[[tk.Misc, Path, int, int, int], "tk.PhotoImage | None"]


def _dibujar_por_defecto(master, ruta, pagina, ancho, alto):
    from . import vista_pdf

    return vista_pdf.imagen_pagina(master, ruta, pagina, ancho, alto)


def pagina_a_mostrar(s: Sugerencia) -> tuple[Path | None, int, str]:
    """Pagina que se ensena para la sugerencia (archivo, pagina 1-based) y su pie."""
    if s.tipo is Tipo.FALTA:
        if s.anterior_archivo is None:
            return None, 0, ""
        return (
            s.anterior_archivo, s.anterior_pagina,
            f"Página {s.anterior_pagina} de «{s.anterior_archivo.name}»: empieza el JG {s.anterior}",
        )
    if s.archivo is None:
        return None, 0, ""
    return s.archivo, s.pagina, f"Página {s.pagina} de «{s.archivo.name}»"


def explicacion(s: Sugerencia) -> str:
    """Frase que acompana a los numeros en la ventana."""
    nombre = s.archivo.name if s.archivo else ""
    if s.tipo is Tipo.CAMBIAR:
        return (
            f"El marcador de la página {s.pagina} de «{nombre}» tiene una errata: "
            f"en el Excel no hay ningún JG {s.marcador}, y el {s.numero} no tiene marcador."
        )
    if s.tipo is Tipo.SOBRA:
        return (
            f"El marcador de la página {s.pagina} de «{nombre}» no corresponde a ningún JG del Excel. "
            "Compruebe el número escrito en la página o quite el marcador si sobra."
        )
    if s.tipo is Tipo.RENOMBRAR:
        return f"El nombre del archivo «{nombre}» indica un JG que no está en el Excel: cámbielo para que sea del JG {s.numero}."
    if s.tipo is Tipo.ARCHIVO_SOBRA:
        return f"El archivo «{nombre}» es del JG {s.marcador}, que no está en el Excel."
    texto = f"El JG {s.numero} está en el Excel, pero no hay ningún marcador con ese número."
    if s.anterior:
        texto += (
            f" Por el orden, su justificante debería ir después del JG {s.anterior}, "
            f"que empieza en la página {s.anterior_pagina}: añada el marcador en su primera página."
        )
    else:
        texto += " Añada el marcador en la primera página de ese justificante."
    return texto


def _numeros(s: Sugerencia) -> tuple[str, str, str, str]:
    """(etiqueta del actual, actual, etiqueta del correcto, correcto); "" si no se muestra."""
    if s.tipo in (Tipo.CAMBIAR, Tipo.RENOMBRAR):
        return "Marcador actual" if s.tipo is Tipo.CAMBIAR else "JG del nombre", s.marcador, "Debe ser", s.numero
    if s.tipo is Tipo.SOBRA:
        return "Marcador actual", s.marcador, "", ""
    if s.tipo is Tipo.ARCHIVO_SOBRA:
        return "JG del nombre", s.marcador, "", ""
    return "", "", "Marcador que falta", s.numero


class DialogoMarcadores(tk.Toplevel):
    def __init__(
        self, parent: tk.Misc, sugerencias: list[Sugerencia], fuente: str = "TkDefaultFont",
        fuente_negrita: str = "TkDefaultFont", estilo_principal: str = "Accent.TButton",
        dibujar: Dibujante = _dibujar_por_defecto,
    ) -> None:
        super().__init__(parent)
        self.title(TITULO)
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.sugerencias = sugerencias
        self.dibujar = dibujar
        self.indice = 0
        self._imagenes: dict[tuple[Path, int], tk.PhotoImage | None] = {}

        base = tkfont.nametofont(fuente).actual() if fuente in tkfont.names() else {"family": "Segoe UI"}
        self.fuente_numero = tkfont.Font(self, family=base["family"], size=TAMANO_NUMERO, weight="bold")
        self.fuente_tachada = tkfont.Font(
            self, family=base["family"], size=TAMANO_NUMERO, weight="bold", overstrike=True
        )

        marco = ttk.Frame(self, padding=(18, 16, 18, 14))
        marco.pack(fill=tk.BOTH, expand=True)
        ttk.Label(marco, text=INTRO, font=fuente_negrita).pack(anchor="w")
        self.contador = ttk.Label(marco, text="", font=fuente, foreground=COLOR_SECUNDARIO)
        self.contador.pack(anchor="w", pady=(2, 10))

        cuerpo = ttk.Frame(marco)
        cuerpo.pack(fill=tk.BOTH)

        # Vista de la pagina (tamano fijo para que la ventana no salte al navegar).
        izquierda = ttk.Frame(cuerpo)
        izquierda.pack(side=tk.LEFT, anchor="n")
        caja = tk.Frame(izquierda, width=ANCHO_VISTA + 2, height=ALTO_VISTA + 2)
        caja.pack_propagate(False)
        caja.pack()
        self.borde = tk.Frame(caja, bg=COLOR_BORDE_IMAGEN, padx=1, pady=1)
        self.vista = tk.Label(self.borde, bd=0)
        self.vista.pack()
        self.sin_vista = ttk.Label(caja, text="", font=fuente, foreground=COLOR_SECUNDARIO, wraplength=ANCHO_VISTA - 40)
        self.pie_vista = ttk.Label(izquierda, text="", font=fuente, foreground=COLOR_SECUNDARIO, wraplength=ANCHO_VISTA)
        self.pie_vista.pack(anchor="w", pady=(6, 0))
        self.caja_vista = caja

        derecha = ttk.Frame(cuerpo, width=ANCHO_DETALLE)
        derecha.pack(side=tk.LEFT, fill=tk.Y, padx=(20, 0))
        self.etiqueta_actual = ttk.Label(derecha, text="", font=fuente, foreground=COLOR_SECUNDARIO)
        self.numero_actual = ttk.Label(derecha, text="", font=self.fuente_tachada, foreground=COLOR_MAL)
        self.flecha = ttk.Label(derecha, text="↓", font=self.fuente_numero, foreground=COLOR_SECUNDARIO)
        self.etiqueta_correcto = ttk.Label(derecha, text="", font=fuente, foreground=COLOR_SECUNDARIO)
        self.numero_correcto = ttk.Label(derecha, text="", font=self.fuente_numero, foreground=COLOR_BIEN)
        self.texto = ttk.Label(derecha, text="", font=fuente, wraplength=ANCHO_DETALLE, justify="left")
        self.detalle = derecha

        ttk.Label(marco, text=AVISO_FINAL, font=fuente_negrita).pack(anchor="w", pady=(14, 10))
        botones = ttk.Frame(marco)
        botones.pack(fill=tk.X)
        self.boton_cerrar = ttk.Button(botones, text="Entendido", style=estilo_principal, command=self.destroy)
        self.boton_cerrar.pack(side=tk.RIGHT)
        self.boton_anterior = ttk.Button(botones, text="◀ Anterior", command=lambda: self.ir(self.indice - 1))
        self.boton_siguiente = ttk.Button(botones, text="Siguiente ▶", command=lambda: self.ir(self.indice + 1))
        if len(sugerencias) > 1:
            self.boton_anterior.pack(side=tk.LEFT)
            self.boton_siguiente.pack(side=tk.LEFT, padx=(8, 0))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.destroy())
        self.bind("<Left>", lambda _e: self.ir(self.indice - 1))
        self.bind("<Right>", lambda _e: self.ir(self.indice + 1))
        self.ir(0)
        self.boton_cerrar.focus_set()

    # --- navegacion ------------------------------------------------------------

    def ir(self, indice: int) -> None:
        if not 0 <= indice < len(self.sugerencias):
            return
        self.indice = indice
        s = self.sugerencias[indice]
        total = len(self.sugerencias)
        self.contador.configure(
            text=f"Corrección {indice + 1} de {total}" if total > 1 else "Hay que hacer esta corrección:"
        )
        self.boton_anterior.state(["disabled" if indice == 0 else "!disabled"])
        self.boton_siguiente.state(["disabled" if indice == total - 1 else "!disabled"])
        self._mostrar_pagina(s)
        self._mostrar_detalle(s)

    def _mostrar_pagina(self, s: Sugerencia) -> None:
        ruta, pagina, pie = pagina_a_mostrar(s)
        imagen = None
        if ruta is not None:
            clave = (ruta, pagina)
            if clave not in self._imagenes:
                self._imagenes[clave] = self.dibujar(self, ruta, pagina, ANCHO_VISTA, ALTO_VISTA)
            imagen = self._imagenes[clave]
        self.borde.place_forget()
        self.sin_vista.place_forget()
        if imagen is not None:
            self.vista.configure(image=imagen)
            self.borde.place(relx=0.5, rely=0, anchor="n")
            self.pie_vista.configure(text=pie)
        else:
            self.vista.configure(image="")
            self.sin_vista.configure(
                text="No se sabe en qué página va este marcador." if ruta is None else "Vista previa no disponible."
            )
            self.sin_vista.place(relx=0.5, rely=0.5, anchor="center")
            self.pie_vista.configure(text=pie)

    def _mostrar_detalle(self, s: Sugerencia) -> None:
        for w in self.detalle.winfo_children():
            w.pack_forget()
        etiqueta_actual, actual, etiqueta_correcto, correcto = _numeros(s)
        if actual:
            self.etiqueta_actual.configure(text=etiqueta_actual)
            self.etiqueta_actual.pack(anchor="w")
            # Tachado solo si hay un numero que lo sustituye.
            self.numero_actual.configure(
                text=actual, font=self.fuente_tachada if correcto else self.fuente_numero
            )
            self.numero_actual.pack(anchor="w")
        if actual and correcto:
            self.flecha.pack(anchor="w", padx=(18, 0))
        if correcto:
            self.etiqueta_correcto.configure(text=etiqueta_correcto)
            self.etiqueta_correcto.pack(anchor="w")
            self.numero_correcto.configure(text=correcto)
            self.numero_correcto.pack(anchor="w")
        self.texto.configure(text=explicacion(s))
        self.texto.pack(anchor="w", pady=(16, 0))


def mostrar(
    parent: tk.Misc, sugerencias: list[Sugerencia], fuente: str = "TkDefaultFont",
    fuente_negrita: str = "TkDefaultFont",
) -> None:
    """Abre la ventana (modal), centrada sobre la principal, y espera a que se cierre."""
    dialogo = DialogoMarcadores(parent, sugerencias, fuente, fuente_negrita)
    raiz = parent.winfo_toplevel()
    dialogo.update_idletasks()
    x = raiz.winfo_rootx() + (raiz.winfo_width() - dialogo.winfo_reqwidth()) // 2
    y = raiz.winfo_rooty() + (raiz.winfo_height() - dialogo.winfo_reqheight()) // 3
    dialogo.geometry(f"+{max(0, x)}+{max(0, y)}")
    dialogo.grab_set()
    dialogo.wait_window()
