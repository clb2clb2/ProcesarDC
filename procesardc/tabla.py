"""Ordenacion de un ttk.Treeview haciendo clic en los encabezados.

Cada clic en la misma columna alterna: ascendente -> descendente -> orden original.
El orden elegido se mantiene cuando la tabla se vuelve a rellenar (llamar a `al_rellenar`).
"""

from __future__ import annotations

from tkinter import ttk

from . import ordenacion

FLECHA_ASC = " ▲"
FLECHA_DESC = " ▼"


class OrdenTabla:
    def __init__(self, tree: ttk.Treeview, tipos: dict[str, str]) -> None:
        """`tipos`: columna -> tipo de `ordenacion`. Las columnas que no aparecen no se ordenan."""
        self.tree = tree
        self.tipos = dict(tipos)
        self.titulos = {col: tree.heading(col, "text") for col in self.tipos}
        self.columna: str | None = None
        self.descendente = False
        self._base: list[str] = []  # orden original (el de insercion)

        for col in self.tipos:
            tree.heading(col, command=lambda c=col: self.clic_encabezado(c))

    def clic_encabezado(self, columna: str) -> None:
        if columna != self.columna:
            self.columna, self.descendente = columna, False
        elif not self.descendente:
            self.descendente = True
        else:
            self.columna, self.descendente = None, False
        self._aplicar()
        self._pintar_titulos()

    def al_rellenar(self) -> None:
        """Llamar tras insertar las filas: guarda su orden como original y aplica el orden elegido."""
        self._base = list(self.tree.get_children())
        self._aplicar()

    def quitar_orden(self) -> None:
        self.columna, self.descendente = None, False
        self._base = list(self.tree.get_children())
        self._pintar_titulos()

    def _aplicar(self) -> None:
        existentes = set(self.tree.get_children())
        base = [iid for iid in self._base if iid in existentes]
        if self.columna is None:
            orden = base
        else:
            valores = [self.tree.set(iid, self.columna) for iid in base]
            orden = ordenacion.ordenar(base, valores, self.tipos[self.columna], self.descendente)
        for posicion, iid in enumerate(orden):
            self.tree.move(iid, "", posicion)

    def _pintar_titulos(self) -> None:
        for col, titulo in self.titulos.items():
            if col == self.columna:
                titulo += FLECHA_DESC if self.descendente else FLECHA_ASC
            self.tree.heading(col, text=titulo)
