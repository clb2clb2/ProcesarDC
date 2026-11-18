"""Convierte las ilustraciones de la ayuda (assets/ayuda/*.svg) a PNG.

Cada SVG se dibuja con Edge o Chrome sin ventana a varias escalas (75, 100, 125, 150 y 200 %),
para que la app use la que corresponda al escalado de la pantalla y se vea nitida.
Genera assets/ayuda/<nombre>@<escala>.png. Solo usa la biblioteca estandar.

    python tools/generar_ayuda.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_icono import buscar_navegador, escribir_png, leer_png  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "assets" / "ayuda"
ESCALAS = (0.75, 1.0, 1.25, 1.5, 2.0)


def nombre_png(svg: Path, escala: float) -> Path:
    return svg.with_name(f"{svg.stem}@{int(escala * 100)}.png")


def tamano_svg(svg: Path) -> tuple[float, float]:
    """Tamano nominal (al 100 %): width/height del <svg> si los tiene; si no, su viewBox."""
    texto = svg.read_text(encoding="utf-8")
    raiz = re.search(r"<svg\b[^>]*>", texto, flags=re.S)
    raiz = raiz.group(0) if raiz else ""
    ancho = re.search(r'\swidth="([\d.]+)(?:px)?"', raiz)
    alto = re.search(r'\sheight="([\d.]+)(?:px)?"', raiz)
    if ancho and alto:
        return float(ancho.group(1)), float(alto.group(1))
    caja = re.search(r'viewBox="\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)\s*"', raiz)
    if not caja:
        sys.exit(f"{svg.name}: no tiene viewBox")
    return float(caja.group(1)), float(caja.group(2))


def dibujar(navegador: Path, svg: Path, escala: float, carpeta: Path) -> None:
    ancho_svg, alto_svg = tamano_svg(svg)
    ancho, alto = round(ancho_svg * escala), round(alto_svg * escala)
    pagina = carpeta / "pagina.html"
    pagina.write_text(
        '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:transparent}'
        f'</style></head><body><img src="{svg.as_uri()}" style="display:block;width:{ancho}px;height:{alto}px">'
        "</body></html>",
        encoding="utf-8",
    )
    captura = carpeta / "captura.png"
    subprocess.run(
        [
            str(navegador), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1", "--default-background-color=00000000",
            f"--user-data-dir={carpeta / 'perfil'}", "--allow-file-access-from-files",
            f"--window-size={max(ancho, 200)},{max(alto, 200)}", f"--screenshot={captura}", pagina.as_uri(),
        ],
        check=True, capture_output=True, timeout=120,
    )
    _w, _h, filas = leer_png(captura.read_bytes())
    recorte = [bytes(filas[y][: ancho * 4]) for y in range(alto)]
    nombre_png(svg, escala).write_bytes(escribir_png(recorte, ancho, alto))


def main() -> None:
    svgs = sorted(CARPETA.glob("*.svg"))
    if not svgs:
        sys.exit(f"No hay SVG en {CARPETA}")
    navegador = buscar_navegador()
    with tempfile.TemporaryDirectory(prefix="ayuda_") as tmp:
        for svg in svgs:
            for escala in ESCALAS:
                dibujar(navegador, svg, escala, Path(tmp))
            print(f"{svg.name}: {', '.join(f'{int(e * 100)} %' for e in ESCALAS)}")


if __name__ == "__main__":
    main()
