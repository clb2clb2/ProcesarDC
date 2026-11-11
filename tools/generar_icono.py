"""Genera assets/procesardc.ico a partir de assets/ProcesarDC_icono.svg.

Dibuja el SVG a cada tamano que usa Windows (directamente desde el vector, con fondo
transparente) con Edge o Chrome sin ventana, y junta las imagenes en un .ico.
Solo usa la biblioteca estandar.

    python tools/generar_icono.py
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SVG = RAIZ / "assets" / "ProcesarDC_icono.svg"
ICO = RAIZ / "assets" / "procesardc.ico"
PNG_GRANDE = RAIZ / "assets" / "procesardc_256.png"

# Tamanos que usa Windows: barra de titulo (16-24), barra de tareas y Alt+Tab (24-48),
# Explorador y escritorio (32-256).
TAMANOS = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
SEPARACION = 8  # pixeles entre imagenes en la pagina que se captura

NAVEGADORES = (
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
)


def buscar_navegador() -> Path:
    for ruta in NAVEGADORES:
        if ruta.exists():
            return ruta
    for nombre in ("msedge", "chrome"):
        encontrado = shutil.which(nombre)
        if encontrado:
            return Path(encontrado)
    sys.exit("No se encuentra Edge ni Chrome para dibujar el SVG.")


# --- PNG ------------------------------------------------------------------------------------
def leer_png(datos: bytes) -> tuple[int, int, list[bytearray]]:
    """PNG RGBA o RGB de 8 bits sin entrelazar -> (ancho, alto, filas RGBA)."""
    assert datos[:8] == b"\x89PNG\r\n\x1a\n", "No es un PNG"
    pos, idat = 8, bytearray()
    while pos < len(datos):
        largo = struct.unpack(">I", datos[pos:pos + 4])[0]
        tipo, cuerpo = datos[pos + 4:pos + 8], datos[pos + 8:pos + 8 + largo]
        if tipo == b"IHDR":
            ancho, alto, bits, color, _c, _f, entrelazado = struct.unpack(">IIBBBBB", cuerpo)
            assert bits == 8 and color in (2, 6) and not entrelazado, "Formato de PNG no previsto"
        elif tipo == b"IDAT":
            idat += cuerpo
        pos += 12 + largo
    canales = 4 if color == 6 else 3
    crudo = zlib.decompress(bytes(idat))
    paso = ancho * canales
    filas: list[bytearray] = []
    anterior = bytearray(paso)
    for y in range(alto):
        filtro = crudo[y * (paso + 1)]
        fila = bytearray(crudo[y * (paso + 1) + 1:(y + 1) * (paso + 1)])
        for i in range(paso):
            a = fila[i - canales] if i >= canales else 0
            b = anterior[i]
            c = anterior[i - canales] if i >= canales else 0
            if filtro == 1:
                fila[i] = (fila[i] + a) & 0xFF
            elif filtro == 2:
                fila[i] = (fila[i] + b) & 0xFF
            elif filtro == 3:
                fila[i] = (fila[i] + (a + b) // 2) & 0xFF
            elif filtro == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                fila[i] = (fila[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        anterior = fila
        if canales == 3:
            fila = bytearray(b for j in range(0, paso, 3) for b in (*fila[j:j + 3], 255))
        filas.append(fila)
    return ancho, alto, filas


def escribir_png(filas: list[bytes], ancho: int, alto: int) -> bytes:
    crudo = b"".join(b"\x00" + bytes(f) for f in filas)

    def trozo(tipo: bytes, cuerpo: bytes) -> bytes:
        return struct.pack(">I", len(cuerpo)) + tipo + cuerpo + struct.pack(">I", zlib.crc32(tipo + cuerpo) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(crudo, 9)) + trozo(b"IEND", b""))


# --- ICO ------------------------------------------------------------------------------------
def escribir_ico(imagenes: dict[int, bytes]) -> bytes:
    """ICO con cada tamano guardado como PNG (admitido desde Windows Vista)."""
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    entradas, datos = b"", b""
    desplazamiento = 6 + 16 * len(imagenes)
    for tam, png in sorted(imagenes.items()):
        lado = 0 if tam >= 256 else tam  # 0 significa 256
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), desplazamiento + len(datos))
        datos += png
    return cabecera + entradas + datos


# --- Dibujo con el navegador ----------------------------------------------------------------
def capturar(navegador: Path, carpeta: Path) -> tuple[int, int, list[bytearray]]:
    """Una pagina con el SVG a todos los tamanos, en fila; devuelve la captura."""
    imgs = []
    x = 0
    for tam in TAMANOS:
        imgs.append(f'<img src="{SVG.as_uri()}" style="position:absolute;left:{x}px;top:0;width:{tam}px;height:{tam}px">')
        x += tam + SEPARACION
    pagina = carpeta / "icono.html"
    pagina.write_text(
        '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:transparent}'
        "</style></head><body>" + "".join(imgs) + "</body></html>",
        encoding="utf-8",
    )
    captura = carpeta / "captura.png"
    subprocess.run(
        [
            str(navegador), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=1", "--default-background-color=00000000",
            f"--user-data-dir={carpeta / 'perfil'}", "--allow-file-access-from-files",
            f"--window-size={x},{max(TAMANOS)}", f"--screenshot={captura}", pagina.as_uri(),
        ],
        check=True, capture_output=True, timeout=120,
    )
    return leer_png(captura.read_bytes())


def main() -> None:
    if not SVG.exists():
        sys.exit(f"No existe {SVG}")
    navegador = buscar_navegador()
    with tempfile.TemporaryDirectory(prefix="icono_") as tmp:
        ancho, _alto, filas = capturar(navegador, Path(tmp))

    imagenes: dict[int, bytes] = {}
    x = 0
    for tam in TAMANOS:
        recorte = [bytes(filas[y][x * 4:(x + tam) * 4]) for y in range(tam)]
        if not any(recorte[y][i] for y in range(tam) for i in range(3, tam * 4, 4)):
            sys.exit(f"La imagen de {tam} px ha salido vacia: revisa el SVG.")
        imagenes[tam] = escribir_png(recorte, tam, tam)
        x += tam + SEPARACION

    ICO.write_bytes(escribir_ico(imagenes))
    PNG_GRANDE.write_bytes(imagenes[256])
    print(f"Icono generado con {navegador.name}: {ICO} ({', '.join(map(str, TAMANOS))} px)")


if __name__ == "__main__":
    main()
