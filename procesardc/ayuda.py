"""Ayuda de las zonas de carga: que archivos se esperan en cada una.

El contenido son bloques (parrafos, pasos con flecha, vinetas e imagenes); dentro del texto,
**asi** marca negrita. `mostrar(...)` abre una ventanita junto a la zona; solo hay una abierta a
la vez y se cierra con el boton, con Escape o abriendo otra.

Las imagenes son PNG en assets/ayuda (generados desde sus SVG con tools/generar_ayuda.py);
la ventana pide cada una por su nombre con la funcion `imagen` que recibe.
"""

from __future__ import annotations

import math
import re
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

PARRAFO = "p"
PASO = "paso"  # parrafo con flecha delante
CONTINUACION = "cont"  # parrafo sin flecha, alineado con el texto del paso anterior
ESPACIO = "esp"  # linea en blanco extra
VINETA = "li"
IMAGEN = "img"  # el texto del bloque es el nombre de la imagen (sin escala ni extension)

ANCHO_TEXTO = 460  # pixeles, si no hay imagenes mas anchas
ESPACIO_TRAS_IMAGEN = 36  # pixeles tras cada ilustracion, a modo de salto entre apartados
FLECHA = "→"
COLOR_FLECHA = "#005FB8"
# Alto maximo de la ventana (sin la barra de titulo), en pixeles de la app. Windows amplia la
# ventana con el escalado de la pantalla: al 150 %, 650 son unos 1024 px con la barra de titulo.
ALTO_VENTANA = 650
ALTO_MAXIMO_PANTALLA = 0.85  # y nunca mas de esta parte de la pantalla


@dataclass(frozen=True)
class Ayuda:
    titulo: str
    bloques: tuple[tuple[str, str], ...]  # (PARRAFO | PASO | VINETA | IMAGEN, texto)


AYUDA_ORIGEN = Ayuda(
    "Documentación del DC",
    (
        (PARRAFO, "**Carga aquí el Documento Contable y toda su documentación.**"),
        (PARRAFO, "Puedes arrastrar varios PDF a la vez, que el sistema reconocerá según los siguientes códigos:"),
        (ESPACIO, ""),
        (PASO, "Un PDF cuyo nombre empiece por **“DC”**, **“CJ”** o **“RT”** seguido del número (“DC7546.pdf”, "
               "“CJ705.pdf”, “RT1604.pdf”): el **Documento Contable**, la **Cuenta Justificativa** o la "
               "**Relación de Transferencias**."),
        (CONTINUACION, "Un PDF cuyo nombre empiece por **“JG”** se reconocerá como archivo de **Justificantes de "
                       "Gasto** (y no podrá tener otro tipo de documentación). Cada justificante individual estará "
                       "señalado por un marcador en su primera página cuyo nombre será el número de JG (por "
                       "ejemplo, “12064”)."),
        (IMAGEN, "origen_archivos_sueltos"),
        (PASO, "Un PDF cuyo nombre empiece por **“DOC ”** seguido de un espacio (por ejemplo, “DOC DC7546.pdf”) "
               "se reconocerá como un **PDF contenedor**, que reúne varios documentos. Cada marcador indica la "
               "primera página de uno y se reconoce con los mismos códigos: “DC…”, “CJ…”, “RT…”, o un número "
               "de JG."),
        (IMAGEN, "origen_un_solo_pdf"),
        (PASO, "Cualquier otro PDF, o cualquier marcador de un archivo “DOC” que no se corresponda con uno de "
               "esos códigos (por ejemplo, “PARAM”, “ANEXO”, “PAGO REMESA”…), se guardará con ese mismo nombre "
               "en la carpeta donde se archive el Documento Contable."),
    ),
)

AYUDA_JP = Ayuda(
    "Justificantes de pago",
    (
        (PARRAFO, "**Si el Documento Contable incluye una remesa de transferencias, carga aquí el PDF "
                  "descargado del banco con los justificantes de pago asociados.**"),
        (IMAGEN, "justificante_pago"),
    ),
)

AYUDA_EXCEL = Ayuda(
    "Datos de Justificantes de Gasto",
    (
        (PARRAFO, "**Carga aquí un Excel descargado de UXXI Económico con los datos de los Justificantes "
                  "de Gasto asociados a este Documento Contable.**"),
        (ESPACIO, ""),
        (PARRAFO, "Entra en UXXI Económico y haz una búsqueda paramétrica que incluya los siguientes datos: "
                  "**Nº Registro justificante**, **Fecha de pago**, **Importe Total**, **Importe retención**, "
                  "**Nº factura proveedor**, **Nombre proveedor** y **Descripción**."),
        (IMAGEN, "excel_datos_a_incluir"),
        (PARRAFO, "E indica el número del documento contable en la pestaña Datos Asoc. 1/2:"),
        (IMAGEN, "excel_documento_contable"),
        (PARRAFO, "Exporta el resultado de la búsqueda como archivo “.xlsx”, y guárdalo para cargarlo en "
                  "esta zona."),
        (IMAGEN, "excel_exportar"),
        (PARRAFO, "El sistema analizará los datos de cada uno de los JG para unirlos al Justificante de Pago "
                  "correspondiente."),
    ),
)


def trozos(texto: str) -> list[tuple[str, bool]]:
    """Texto con **negritas** -> [(trozo, es_negrita), ...]."""
    partes = re.split(r"\*\*(.+?)\*\*", texto)
    return [(p, i % 2 == 1) for i, p in enumerate(partes) if p]


class VentanaAyuda(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        ayuda: Ayuda,
        fuente: str,
        fuente_negrita: str,
        fuente_titulo: str,
        imagen: Callable[[str], tk.PhotoImage | None] = lambda _nombre: None,
    ) -> None:
        super().__init__(parent)
        self.ayuda = ayuda
        self.title(f"Ayuda: {ayuda.titulo}")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        estilo = ttk.Style(self)
        fondo = estilo.lookup(".", "background") or "#fafafa"
        color_texto = estilo.lookup(".", "foreground") or "#1c1c1c"
        letra = tkfont.nametofont(fuente, root=self)

        # Tk no guarda referencia a las imagenes: se guardan aqui mientras la ventana exista.
        self.imagenes: dict[str, tk.PhotoImage] = {}
        for tipo, nombre in ayuda.bloques:
            if tipo == IMAGEN and nombre not in self.imagenes:
                img = imagen(nombre)
                if img is not None:
                    self.imagenes[nombre] = img
        ancho = max([ANCHO_TEXTO] + [img.width() for img in self.imagenes.values()])

        marco = ttk.Frame(self, padding=(20, 16, 20, 16))
        marco.pack(fill=tk.BOTH, expand=True)
        cuerpo = ttk.Frame(marco)
        cuerpo.pack(fill=tk.BOTH, expand=True)

        self.texto = tk.Text(
            cuerpo, wrap="word", width=math.ceil(ancho / letra.measure("0")), height=1,
            font=fuente, background=fondo, foreground=color_texto, borderwidth=0, highlightthickness=0,
            padx=0, pady=0, cursor="arrow", spacing1=0, spacing2=2,
        )
        sangria = letra.measure(f"{FLECHA}  ")
        self.texto.tag_configure("titulo", font=fuente_titulo, spacing3=10)
        self.texto.tag_configure("bloque", spacing3=10)
        self.texto.tag_configure("negrita", font=fuente_negrita)
        self.texto.tag_configure("flecha", foreground=COLOR_FLECHA, font=fuente_negrita)
        self.texto.tag_configure("sangria", lmargin2=sangria)
        self.texto.tag_configure("vineta", lmargin1=8, lmargin2=8 + letra.measure("•  "), spacing3=3)
        self.texto.tag_configure("continuacion", lmargin1=sangria, lmargin2=sangria)
        # Espacio amplio tras cada ilustracion, para separar los apartados.
        self.texto.tag_configure("imagen", justify="center", spacing3=ESPACIO_TRAS_IMAGEN)

        self.texto.insert("end", ayuda.titulo + "\n", ("titulo",))
        for tipo, contenido in ayuda.bloques:
            if tipo == ESPACIO:
                self.texto.insert("end", "\n")
                continue
            if tipo == IMAGEN:
                if contenido in self.imagenes:  # si falta el PNG, la ayuda se muestra sin la imagen
                    inicio = self.texto.index("end-1c")
                    self.texto.image_create("end", image=self.imagenes[contenido], name=contenido)
                    self.texto.insert("end", "\n")
                    self.texto.tag_add("imagen", inicio, "end-1c")
                continue
            etiquetas = {
                VINETA: ("vineta",),
                PASO: ("bloque", "sangria"),
                CONTINUACION: ("bloque", "continuacion"),
            }.get(tipo, ("bloque",))
            if tipo == PASO:
                self.texto.insert("end", f"{FLECHA}  ", ("flecha",) + etiquetas)
            elif tipo == VINETA:
                self.texto.insert("end", "•  ", etiquetas)
            for trozo, negrita in trozos(contenido):
                self.texto.insert("end", trozo, etiquetas + (("negrita",) if negrita else ()))
            self.texto.insert("end", "\n", etiquetas)
        self.texto.delete("end-2c")  # sin salto de linea al final
        self.texto.configure(state="disabled")

        self.barra = ttk.Scrollbar(cuerpo, orient=tk.VERTICAL, command=self.texto.yview)
        self.texto.configure(yscrollcommand=self.barra.set)
        self.texto.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.boton = ttk.Button(marco, text="Entendido", command=self.destroy, style="Accent.TButton")
        self.boton.pack(anchor="e", pady=(12, 0))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.boton.focus_set()
        self._ajustar_alto(letra)

    def _ajustar_alto(self, letra: tkfont.Font) -> None:
        """Alto del texto segun su contenido, sin pasar de ALTO_VENTANA para la ventana entera;
        si no cabe, barra de desplazamiento (el titulo y el boton quedan siempre a la vista)."""
        self.update_idletasks()
        self.texto.configure(height=200)  # alto holgado para que se maquete todo el contenido
        self.update_idletasks()
        contenido = self.texto.count("1.0", "end", "ypixels")
        contenido = contenido[0] if isinstance(contenido, tuple) else int(contenido or 0)
        linea = letra.metrics("linespace")
        resto = self.winfo_reqheight() - self.texto.winfo_reqheight()  # margenes y boton
        alto_ventana = min(ALTO_VENTANA, int(self.winfo_screenheight() * ALTO_MAXIMO_PANTALLA))
        maximo = alto_ventana - resto
        if contenido > maximo:
            self.texto.configure(height=max(5, maximo // linea))
            self.barra.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        else:
            self.texto.configure(height=math.ceil(contenido / linea))
        # Al reducir el alto, Tk puede conservar un desplazamiento: se abre siempre por el principio.
        self.texto.mark_set("insert", "1.0")
        self.texto.yview_moveto(0)


def mostrar(
    parent: tk.Misc,
    ayuda: Ayuda,
    cerca_de: tk.Misc,
    fuente: str,
    fuente_negrita: str,
    fuente_titulo: str,
    imagen: Callable[[str], tk.PhotoImage | None] = lambda _nombre: None,
) -> VentanaAyuda:
    """Abre la ayuda sobre la esquina superior derecha de `cerca_de` (donde esta el icono),
    sin salirse de la pantalla. Cierra la que hubiera abierta."""
    raiz = parent.winfo_toplevel()
    anterior = getattr(raiz, "_ventana_ayuda", None)
    if anterior is not None and anterior.winfo_exists():
        anterior.destroy()

    ventana = VentanaAyuda(raiz, ayuda, fuente, fuente_negrita, fuente_titulo, imagen)
    raiz._ventana_ayuda = ventana
    ventana.update_idletasks()
    ancho, alto = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
    x = cerca_de.winfo_rootx() + cerca_de.winfo_width() - ancho
    y = cerca_de.winfo_rooty() + 8
    x = max(0, min(x, ventana.winfo_screenwidth() - ancho))
    y = max(0, min(y, ventana.winfo_screenheight() - alto - 40))
    ventana.geometry(f"+{x}+{y}")
    return ventana
