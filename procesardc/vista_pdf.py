"""Vista previa de una pagina de PDF como imagen de Tk (con pypdfium2, sin Pillow).

pypdfium2 dibuja la pagina en un mapa de bits RGB; se envuelve en formato PPM, que Tk
admite de serie, y se pasa a PhotoImage.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path


def pagina_ppm(ruta: Path, pagina: int, ancho: int) -> bytes:
    """PPM (RGB) de la `pagina` (1 = primera) del PDF, escalada a `ancho` pixeles."""
    import pypdfium2 as pdfium  # se importa al usarla: la app funciona sin vista previa si falta

    pdf = pdfium.PdfDocument(str(ruta))
    try:
        hoja = pdf[pagina - 1]
        ancho_pt, _alto_pt = hoja.get_size()
        mapa = hoja.render(scale=ancho / ancho_pt, rev_byteorder=True)  # RGB, no BGR
        w, h, paso = mapa.width, mapa.height, mapa.stride
        crudo = bytes(mapa.buffer)
        filas = b"".join(crudo[y * paso: y * paso + w * 3] for y in range(h))  # sin el relleno de cada fila
        return b"P6\n%d %d\n255\n" % (w, h) + filas
    finally:
        pdf.close()


def imagen_pagina(master: tk.Misc, ruta: Path, pagina: int, ancho: int) -> tk.PhotoImage | None:
    """PhotoImage de la pagina, o None si no se puede dibujar (sin pypdfium2, PDF ilegible...)."""
    try:
        # Tk 8.6 acepta el PPM en binario (en base64 no lo reconoce).
        return tk.PhotoImage(master=master, data=pagina_ppm(ruta, pagina, ancho), format="ppm")
    except Exception:
        return None
