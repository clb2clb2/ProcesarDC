"""Utilidades para ttk.Treeview: ordenar por encabezado y ajustar columnas al ancho.

- `OrdenTabla`: cada clic en la misma columna alterna ascendente -> descendente -> orden
  original. El orden elegido se mantiene cuando la tabla se vuelve a rellenar (`al_rellenar`).
- `ColumnasAjustables`: la tabla cabe siempre a lo ancho, sin barra horizontal.
"""

from __future__ import annotations

from tkinter import ttk

from . import ordenacion

FLECHA_ASC = " ▲"
FLECHA_DESC = " ▼"

# Pixeles que el borde del Treeview (tema sv-ttk) resta al ancho util.
MARGEN_TABLA = 10


def repartir_ancho(disponible: int, pesos: dict[str, int], minimo: int) -> dict[str, int]:
    """Reparte `disponible` pixeles entre columnas en proporcion a `pesos`, sin bajar de `minimo`.

    Si no hay sitio para todas con el minimo, cada una se queda en el minimo.
    """
    if not pesos:
        return {}
    columnas = list(pesos)
    if disponible <= minimo * len(columnas):
        return {c: minimo for c in columnas}

    anchos: dict[str, int] = {}
    restantes = dict(pesos)
    sitio = disponible
    # Las que quedarian por debajo del minimo se fijan en el minimo y se reparte el resto.
    while True:
        total = sum(restantes.values())
        bajas = [c for c, p in restantes.items() if sitio * p / total < minimo]
        if not bajas:
            break
        for c in bajas:
            anchos[c] = minimo
            sitio -= minimo
            del restantes[c]

    total = sum(restantes.values())
    asignado = 0
    for i, (c, p) in enumerate(restantes.items()):
        ancho = sitio - asignado if i == len(restantes) - 1 else int(sitio * p / total)
        anchos[c] = ancho
        asignado += ancho
    return {c: anchos[c] for c in columnas}


def fijar_columna(disponible: int, pesos: dict[str, int], columna: str, ancho: int, minimo: int) -> dict[str, int]:
    """Deja `columna` con `ancho` (recortado para que quepan las demas con el minimo) y reparte
    el resto de `disponible` entre las demas en proporcion a `pesos`."""
    otras = {c: p for c, p in pesos.items() if c != columna}
    ancho = max(minimo, min(ancho, disponible - minimo * len(otras)))
    anchos = repartir_ancho(disponible - ancho, otras, minimo)
    anchos[columna] = ancho
    return {c: anchos[c] for c in pesos}


CURSOR_REDIMENSIONAR = "sb_h_double_arrow"


class ColumnasAjustables:
    """La tabla cabe siempre a lo ancho: las columnas fijas conservan su ancho y el resto se
    reparte entre las ajustables, en proporcion a su peso.

    Tk solo reparte la diferencia de ancho respecto al tamano anterior: si la tabla se muestra
    por primera vez mas estrecha que sus columnas, nunca las encoge. Por eso se hace aqui.

    El usuario puede arrastrar la separacion entre encabezados (el cursor cambia a <->): la
    columna se queda con el ancho elegido y las ajustables ceden o ganan el sitio, de modo que
    la tabla siga cabiendo. Las nuevas proporciones se mantienen al cambiar el tamano.
    """

    def __init__(self, tree: ttk.Treeview, pesos: dict[str, int], minimo: int) -> None:
        self.tree = tree
        self.pesos = dict(pesos)
        self.minimo = minimo
        self._anchos_al_pulsar: dict[str, int] | None = None
        for col in tree["columns"]:
            tree.column(col, stretch=False)
        tree.bind("<Configure>", self.ajustar, add="+")
        tree.bind("<Motion>", self._mover_raton, add="+")
        tree.bind("<Leave>", lambda _e: self._cursor(""), add="+")
        tree.bind("<ButtonPress-1>", self._pulsar, add="+")
        tree.bind("<ButtonRelease-1>", self._soltar, add="+")

    def _anchos(self) -> dict[str, int]:
        return {c: int(self.tree.column(c, "width")) for c in self.tree["columns"]}

    def _fijas(self, anchos: dict[str, int]) -> int:
        return sum(a for c, a in anchos.items() if c not in self.pesos)

    def _util(self) -> int:
        return self.tree.winfo_width() - MARGEN_TABLA

    def ajustar(self, _event=None) -> None:
        disponible = self._util() - self._fijas(self._anchos())
        for col, ancho in repartir_ancho(disponible, self.pesos, self.minimo).items():
            self.tree.column(col, width=ancho)

    def sobre_separador(self, x: int, y: int) -> bool:
        return self.tree.identify_region(x, y) == "separator"

    def _cursor(self, cursor: str) -> None:
        if str(self.tree.cget("cursor")) != cursor:
            self.tree.configure(cursor=cursor)

    def _mover_raton(self, event) -> None:
        if self._anchos_al_pulsar is None:  # mientras se arrastra, Tk mantiene el cursor
            self._cursor(CURSOR_REDIMENSIONAR if self.sobre_separador(event.x, event.y) else "")

    def _pulsar(self, event) -> None:
        self._anchos_al_pulsar = self._anchos() if self.sobre_separador(event.x, event.y) else None

    def _soltar(self, _event) -> None:
        antes, self._anchos_al_pulsar = self._anchos_al_pulsar, None
        if antes is None:
            return
        ahora = self._anchos()
        cambiadas = [c for c in ahora if ahora[c] != antes[c]]
        if cambiadas:
            self.columna_redimensionada(cambiadas[0], ahora[cambiadas[0]])

    def columna_redimensionada(self, columna: str, ancho: int) -> None:
        """Reajusta la tabla tras dar a `columna` el `ancho` que ha elegido el usuario."""
        anchos = self._anchos()
        if columna in self.pesos:
            disponible = self._util() - self._fijas(anchos)
            nuevos = fijar_columna(disponible, {c: anchos[c] for c in self.pesos}, columna, ancho, self.minimo)
            for col, a in nuevos.items():
                self.tree.column(col, width=a)
            self.pesos = dict(nuevos)  # las proporciones elegidas se mantienen
        else:
            # Columna fija: no puede dejar a las ajustables por debajo del minimo.
            otras_fijas = self._fijas(anchos) - anchos[columna]
            maximo = self._util() - otras_fijas - self.minimo * len(self.pesos)
            self.tree.column(columna, width=max(20, min(ancho, maximo)))
            self.ajustar()


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
