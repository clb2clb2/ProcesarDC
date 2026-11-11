"""Zona de carga de ficheros: se arrastran encima o se pulsa para abrir el selector.

Tk no redondea esquinas ni suaviza lineas, asi que la zona es un Canvas: las esquinas y el
icono (flecha hacia arriba sobre una bandeja) son imagenes calculadas con suavizado, y los
lados son rectangulos. Estados: normal, encima (raton o fichero arrastrado) y deshabilitada.
"""

from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from dataclasses import dataclass

SUBMUESTRAS = 4  # por eje, para suavizar las esquinas

# Icono: alto respecto al de la zona y separacion del borde izquierdo.
PROPORCION_ICONO = 0.36
MARGEN_ICONO = 20
MARGEN_VERTICAL = 12  # minimo entre el texto y los bordes de arriba y abajo

# Icono de ayuda ("?" en un circulo) en la esquina superior derecha.
TAM_AYUDA = 20
GROSOR_AYUDA = 1.4
MARGEN_AYUDA = 8
HOLGURA_AYUDA = 4  # pixeles alrededor del icono que tambien cuentan como clic en el

NORMAL = "normal"
ENCIMA = "encima"
DESHABILITADA = "deshabilitada"

# Icono "subir": trazos (segmentos) sobre una rejilla de 512 x 512, con extremos redondeados.
ICONO_REJILLA = 512
ICONO_GROSOR = 52
ICONO_TRAZOS = (
    ((256, 50), (256, 338)),  # asta de la flecha
    ((130, 150), (256, 46)),  # punta, lado izquierdo
    ((256, 46), (382, 150)),  # punta, lado derecho
    ((44, 360), (44, 440)),  # bandeja: lado izquierdo
    ((44, 440), (468, 440)),  # bandeja: fondo
    ((468, 440), (468, 360)),  # bandeja: lado derecho
)


@dataclass(frozen=True)
class EstiloZona:
    fondo_exterior: str  # color de la ventana (lo que se ve fuera de las esquinas)
    fondo: str
    borde: str
    grosor_borde: int
    texto: str
    pista: str  # linea pequena de debajo, "(o pulsa para cargar)"
    icono: str
    si: str  # marca ✔
    no: str  # marca ✖


# Texto con estilos: lineas formadas por trozos (texto, estilo).
TEXTO = "texto"
SI = "si"  # marca ✔: letra pequena y color `si`
NO = "no"  # marca ✖: letra pequena y color `no`
Segmento = tuple[str, str]
Lineas = list[list[Segmento]]


def a_lineas(texto: str | Lineas) -> Lineas:
    if isinstance(texto, str):
        return [[(linea, TEXTO)] for linea in texto.split("\n")]
    return texto


def texto_plano(lineas: str | Lineas) -> str:
    return "\n".join("".join(t for t, _estilo in linea) for linea in a_lineas(lineas))


def partir_en_renglones(
    linea: list[Segmento], ancho: float, medir: Callable[[str, str], float]
) -> list[list[Segmento]]:
    """Reparte una linea en renglones de `ancho` como maximo, cortando entre palabras.

    `medir(texto, estilo)` da el ancho en pixeles. Una palabra mas ancha que `ancho` ocupa
    un renglon ella sola.
    """
    palabras = [(p, estilo) for texto, estilo in linea for p in re.findall(r"\S+\s*|\s+", texto)]
    renglones: list[list[Segmento]] = [[]]
    ocupado = 0.0
    for palabra, estilo in palabras:
        if renglones[-1] and ocupado + medir(palabra.rstrip(), estilo) > ancho:
            renglones.append([])
            ocupado = 0.0
            palabra = palabra.lstrip()
            if not palabra:
                continue
        renglones[-1].append((palabra, estilo))
        ocupado += medir(palabra, estilo)
    return renglones


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(round(c)) for c in rgb)


def _mezclar(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> str:
    return _hex(tuple(x + (y - x) * t for x, y in zip(a, b)))


def pixeles_esquina(radio: int, grosor: int, exterior: str, borde: str, fondo: str) -> list[list[str]]:
    """Colores de la esquina superior izquierda (radio x radio), con el centro del arco en (radio, radio)."""
    colores = [_rgb(exterior), _rgb(borde), _rgb(fondo)]
    filas: list[list[str]] = []
    for y in range(radio):
        fila = []
        for x in range(radio):
            cuenta = [0, 0, 0]
            for sy in range(SUBMUESTRAS):
                for sx in range(SUBMUESTRAS):
                    px = x + (sx + 0.5) / SUBMUESTRAS
                    py = y + (sy + 0.5) / SUBMUESTRAS
                    d = ((radio - px) ** 2 + (radio - py) ** 2) ** 0.5
                    cuenta[0 if d > radio else 1 if d > radio - grosor else 2] += 1
            total = SUBMUESTRAS * SUBMUESTRAS
            fila.append(_hex(tuple(sum(c[i] * n for c, n in zip(colores, cuenta)) / total for i in range(3))))
        filas.append(fila)
    return filas


def _distancia_a_segmento(px: float, py: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def pixeles_icono(tam: int, color: str, fondo: str) -> list[list[str]]:
    """Icono "subir" de tam x tam pixeles, suavizado: cada pixel mezcla `color` y `fondo`
    segun lo cerca que este su centro del trazo (en pixeles)."""
    escala = tam / ICONO_REJILLA
    medio_grosor = ICONO_GROSOR / 2 * escala
    c_icono, c_fondo = _rgb(color), _rgb(fondo)
    trazos = [((a[0] * escala, a[1] * escala), (b[0] * escala, b[1] * escala)) for a, b in ICONO_TRAZOS]
    filas = []
    for y in range(tam):
        fila = []
        for x in range(tam):
            d = min(_distancia_a_segmento(x + 0.5, y + 0.5, a, b) for a, b in trazos)
            cobertura = max(0.0, min(1.0, medio_grosor - d + 0.5))
            fila.append(_mezclar(c_fondo, c_icono, cobertura))
        filas.append(fila)
    return filas


def pixeles_anillo(tam: int, grosor: float, color: str, fondo: str) -> list[list[str]]:
    """Circunferencia de tam x tam pixeles y `grosor` de trazo, suavizada."""
    c_color, c_fondo = _rgb(color), _rgb(fondo)
    centro = tam / 2
    radio = tam / 2 - grosor / 2 - 0.5
    filas = []
    for y in range(tam):
        fila = []
        for x in range(tam):
            d = ((x + 0.5 - centro) ** 2 + (y + 0.5 - centro) ** 2) ** 0.5
            cobertura = max(0.0, min(1.0, grosor / 2 - abs(d - radio) + 0.5))
            fila.append(_mezclar(c_fondo, c_color, cobertura))
        filas.append(fila)
    return filas


def _imagen(master: tk.Misc, pixeles: list[list[str]]) -> tk.PhotoImage:
    img = tk.PhotoImage(master=master, width=len(pixeles[0]), height=len(pixeles))
    img.put(" ".join("{" + " ".join(fila) + "}" for fila in pixeles))
    return img


class ZonaSoltar(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        texto: str | Lineas,
        pista: str,
        estilos: dict[str, EstiloZona],
        al_pulsar: Callable[[], None] | None = None,
        al_ayuda: Callable[[], None] | None = None,
        fuente: str = "TkDefaultFont",
        fuente_pista: str = "TkSmallCaptionFont",
        alto: int = 84,
        radio: int = 10,
    ) -> None:
        """`fuente_pista` se usa tambien para las marcas ✔ y ✖ (mas pequenas que el texto)."""
        super().__init__(parent, height=alto, highlightthickness=0, bd=0, bg=estilos[NORMAL].fondo_exterior)
        self._alto_minimo = alto
        self._lineas, self._pista = a_lineas(texto), pista
        self._estilos = estilos
        self._al_pulsar = al_pulsar
        self._fuentes = {
            TEXTO: tkfont.nametofont(fuente, root=self),
            SI: tkfont.nametofont(fuente_pista, root=self),
            NO: tkfont.nametofont(fuente_pista, root=self),
        }
        self._fuente_pista = fuente_pista
        self._al_ayuda = al_ayuda
        self._raton_en_ayuda = False
        self._fuente_ayuda = tkfont.Font(
            root=self, family=self._fuentes[TEXTO].actual("family"), size=-int(TAM_AYUDA * 0.62), weight="bold"
        )
        self._radio = radio
        self._habilitada = True
        self._raton_encima = False
        self._arrastre_encima = False
        self._imagenes: dict[tuple, tk.PhotoImage] = {}

        self.bind("<Configure>", lambda _e: self._dibujar())
        self.bind("<Enter>", lambda _e: self._set_raton(True))
        self.bind("<Leave>", lambda _e: self._set_raton(False))
        self.bind("<Motion>", self._mover_raton)
        self.bind("<ButtonRelease-1>", self._pulsar)
        self._actualizar_cursor()

    # --- estado -------------------------------------------------------------------------
    @property
    def texto(self) -> str:
        """Texto sin estilos (lineas separadas por saltos de linea)."""
        return texto_plano(self._lineas)

    @property
    def lineas(self) -> Lineas:
        return self._lineas

    @property
    def pista(self) -> str:
        return self._pista

    @property
    def habilitada(self) -> bool:
        return self._habilitada

    @property
    def estado(self) -> str:
        if not self._habilitada:
            return DESHABILITADA
        return ENCIMA if (self._raton_encima or self._arrastre_encima) else NORMAL

    def set_texto(self, texto: str | Lineas, pista: str | None = None) -> None:
        self._lineas = a_lineas(texto)
        if pista is not None:
            self._pista = pista
        self._dibujar()

    def habilitar(self, habilitada: bool) -> None:
        if habilitada != self._habilitada:
            self._habilitada = habilitada
            self._actualizar_cursor()
            self._dibujar()

    def resaltar(self, activa: bool) -> None:
        """Fichero arrastrado encima (o que sale)."""
        self._arrastre_encima = activa
        self._dibujar()

    def _set_raton(self, encima: bool) -> None:
        self._raton_encima = encima
        if not encima:
            self._raton_en_ayuda = False
            self._actualizar_cursor()
        self._dibujar()

    def rect_ayuda(self) -> tuple[float, float, float, float] | None:
        """Zona sensible del icono de ayuda (con algo de holgura), o None si no hay ayuda."""
        if self._al_ayuda is None:
            return None
        x1 = self.winfo_width() - MARGEN_AYUDA
        x0, y0 = x1 - TAM_AYUDA, MARGEN_AYUDA
        h = HOLGURA_AYUDA
        return x0 - h, y0 - h, x1 + h, y0 + TAM_AYUDA + h

    def _sobre_ayuda(self, x: float, y: float) -> bool:
        rect = self.rect_ayuda()
        return rect is not None and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def _mover_raton(self, event) -> None:
        sobre = self._sobre_ayuda(event.x, event.y)
        if sobre != self._raton_en_ayuda:
            self._raton_en_ayuda = sobre
            self._actualizar_cursor()
            self._dibujar_ayuda(self._estilos[self.estado])

    def _pulsar(self, event) -> None:
        if self._sobre_ayuda(event.x, event.y):
            self._al_ayuda()  # la ayuda funciona aunque la zona este deshabilitada
            return
        dentro = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if self._habilitada and dentro and self._al_pulsar:
            self._al_pulsar()

    def _actualizar_cursor(self) -> None:
        self.configure(cursor="hand2" if (self._habilitada or self._raton_en_ayuda) else "")

    # --- dibujo -------------------------------------------------------------------------
    def _esquinas(self, e: EstiloZona) -> list[tk.PhotoImage]:
        """Sup. izq., sup. der., inf. izq. e inf. der.; se calculan una vez por estilo."""
        claves = [("esquina", e, i) for i in range(4)]
        if claves[0] not in self._imagenes:
            base = pixeles_esquina(self._radio, e.grosor_borde, e.fondo_exterior, e.borde, e.fondo)
            variantes = [base, [f[::-1] for f in base], base[::-1], [f[::-1] for f in base[::-1]]]
            for clave, pixeles in zip(claves, variantes):
                self._imagenes[clave] = _imagen(self, pixeles)
        return [self._imagenes[c] for c in claves]

    def _icono(self, e: EstiloZona, tam: int) -> tk.PhotoImage:
        clave = ("icono", e.icono, e.fondo, tam)
        if clave not in self._imagenes:
            self._imagenes[clave] = _imagen(self, pixeles_icono(tam, e.icono, e.fondo))
        return self._imagenes[clave]

    def _dibujar_ayuda(self, e: EstiloZona) -> None:
        """Icono "?" en un circulo; en el color del borde con el raton encima."""
        self.delete("ayuda")
        if self._al_ayuda is None:
            return
        color = e.borde if self._raton_en_ayuda else e.pista
        clave = ("ayuda", color, e.fondo)
        if clave not in self._imagenes:
            self._imagenes[clave] = _imagen(self, pixeles_anillo(TAM_AYUDA, GROSOR_AYUDA, color, e.fondo))
        cx = self.winfo_width() - MARGEN_AYUDA - TAM_AYUDA / 2
        cy = MARGEN_AYUDA + TAM_AYUDA / 2
        self.create_image(cx, cy, image=self._imagenes[clave], tags="ayuda")
        self.create_text(cx, cy, text="?", font=self._fuente_ayuda, fill=color, tags=("ayuda", "ayuda_texto"))

    def _dibujar_texto(self, centro_x: float, ancho_texto: float, e: EstiloZona) -> float:
        """Dibuja las lineas desde y=0, cada renglon centrado; devuelve la y final.

        Cada trozo va con su fuente y color; todos los de un renglon comparten la linea base.
        """
        colores = {TEXTO: e.texto, SI: e.si, NO: e.no}

        def medir(texto: str, estilo: str) -> float:
            return self._fuentes[estilo].measure(texto)

        y = 0.0
        for linea in self._lineas:
            for renglon in partir_en_renglones(linea, ancho_texto, medir):
                if not renglon:
                    renglon = [("", TEXTO)]
                estilos = {estilo for _t, estilo in renglon}
                ascenso = max(self._fuentes[s].metrics("ascent") for s in estilos)
                descenso = max(self._fuentes[s].metrics("descent") for s in estilos)
                anchura = sum(medir(t, s) for t, s in renglon[:-1]) + medir(renglon[-1][0].rstrip(), renglon[-1][1])
                x = centro_x - anchura / 2
                for texto, estilo in renglon:
                    fuente = self._fuentes[estilo]
                    self.create_text(
                        x, y + ascenso - fuente.metrics("ascent"), text=texto, font=fuente,
                        fill=colores[estilo], anchor="nw", tags=("texto", estilo, "contenido"),
                    )
                    x += medir(texto, estilo)
                y += ascenso + descenso
        return y

    def _dibujar(self) -> None:
        self.delete("all")
        ancho, alto, r = self.winfo_width(), self.winfo_height(), self._radio
        if ancho < 2 * r or alto < 2 * r:
            return
        e = self._estilos[self.estado]
        g = e.grosor_borde

        # Relleno y bordes rectos (los rectangulos de Tk cubren [x0, x1) con outline vacio).
        self.create_rectangle(r, 0, ancho - r, alto, fill=e.fondo, outline="")
        self.create_rectangle(0, r, ancho, alto - r, fill=e.fondo, outline="")
        for x0, y0, x1, y1 in (
            (r, 0, ancho - r, g),
            (r, alto - g, ancho - r, alto),
            (0, r, g, alto - r),
            (ancho - g, r, ancho, alto - r),
        ):
            self.create_rectangle(x0, y0, x1, y1, fill=e.borde, outline="")

        si, sd, ii, id_ = self._esquinas(e)
        self.create_image(0, 0, image=si, anchor="nw")
        self.create_image(ancho - r, 0, image=sd, anchor="nw")
        self.create_image(0, alto - r, image=ii, anchor="nw")
        self.create_image(ancho - r, alto - r, image=id_, anchor="nw")

        # Icono a la izquierda, centrado en vertical.
        tam = int(self._alto_minimo * PROPORCION_ICONO)
        self.create_image(MARGEN_ICONO + tam / 2, alto / 2, image=self._icono(e, tam), tags="icono")

        # Texto (con marcas ✔/✖) y pista debajo, centrados en bloque; sin pisar el icono.
        ancho_texto = max(ancho - 2 * (MARGEN_ICONO + tam + 8), 10)
        y = self._dibujar_texto(ancho / 2, ancho_texto, e)
        if self._pista:
            self.create_text(
                ancho / 2, y + 1, text=self._pista, font=self._fuente_pista, fill=e.pista,
                width=ancho_texto, justify="center", anchor="n", tags=("pista", "contenido"),
            )
        _x0, y0, _x1, y1 = self.bbox("contenido")
        self.move("contenido", 0, alto / 2 - (y0 + y1) / 2)
        self._dibujar_ayuda(e)

        # Si el texto no cabe (varias lineas, ventana estrecha), la zona pide mas alto.
        deseado = max(self._alto_minimo, (y1 - y0) + 2 * MARGEN_VERTICAL)
        if deseado != int(self.cget("height")):
            self.configure(height=deseado)  # provoca <Configure> y se redibuja
