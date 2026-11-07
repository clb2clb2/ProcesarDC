"""Genera los PDFs de prueba de ej/fixtures a partir de los PDFs de ej.

El PDF de JG de origen (unos 75 MB) no esta en el repositorio. Si falta, se puede
recuperar del historial de git:

    git show "4fe4e5d:ej/JG 5270-7063(25+1).pdf" > "ej/JG 5270-7063(25+1).pdf"

(En PowerShell, usar `cmd /c` para que la redireccion no corrompa el binario.)
"""

import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


base = Path(__file__).resolve().parent.parent / "ej"
fixtures = base / "fixtures"

JG_SOURCE_NAME = "JG 5270-7063(25+1).pdf"
REQUIRED = ["DC3391.pdf", "CJ0238.pdf", "RT536.pdf", "PARAM.pdf", JG_SOURCE_NAME]

missing = [name for name in REQUIRED if not (base / name).exists()]
if missing:
    print("Faltan PDFs de origen en ej/:")
    for name in missing:
        print(f"- {name}")
    if JG_SOURCE_NAME in missing:
        print(f'\nRecuperalo con: git show "4fe4e5d:ej/{JG_SOURCE_NAME}" > "ej/{JG_SOURCE_NAME}"')
    sys.exit(1)

fixtures.mkdir(parents=True, exist_ok=True)

src_dc = PdfReader(str(base / "DC3391.pdf"))
src_cj = PdfReader(str(base / "CJ0238.pdf"))
src_rt = PdfReader(str(base / "RT536.pdf"))
src_jg = PdfReader(str(base / JG_SOURCE_NAME))
src_param = PdfReader(str(base / "PARAM.pdf"))


def write_fixture(name: str, pages, outline: list[tuple[str, int]]) -> None:
    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)
    for title, page_idx in outline:
        writer.add_outline_item(title, page_idx)
    with open(fixtures / name, "wb") as fh:
        writer.write(fh)


def jg_outline(reader: PdfReader, offset: int) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for item in reader.outline:
        if isinstance(item, list):
            continue
        entries.append((str(item.title), reader.get_destination_page_number(item) + offset))
    return entries


# Caso OK: mezcla de no numericos y numericos en un unico contenedor.
write_fixture(
    "origen_contenedor_ok.pdf",
    [src_dc.pages[0], src_cj.pages[0], src_rt.pages[0], src_param.pages[0], src_jg.pages[0], src_jg.pages[1]],
    [("DC1234", 0), ("CJ5678", 1), ("RT9001", 2), ("ANEXO", 3), ("5270", 4), ("5283", 5)],
)

# Modo normal completo: DC + CJ + todo el PDF de JG con sus marcadores (escenario E).
write_fixture(
    "origen_contenedor_normal_completo.pdf",
    [src_dc.pages[0], src_cj.pages[0], *src_jg.pages],
    [("DC1234", 0), ("CJ5678", 1), *jg_outline(src_jg, offset=2)],
)

# Conflicto texto duplicado.
write_fixture(
    "origen_conflicto_texto_duplicado.pdf",
    [src_dc.pages[0], src_cj.pages[0], src_param.pages[0], src_rt.pages[0]],
    [("DC1234", 0), ("CJ5678", 1), ("ANEXO", 2), ("ANEXO", 3)],
)

# Conflicto JG numerico duplicado.
write_fixture(
    "origen_conflicto_jg_duplicado.pdf",
    [src_dc.pages[0], src_cj.pages[0], src_jg.pages[0], src_jg.pages[1]],
    [("DC1234", 0), ("CJ5678", 1), ("5270", 2), ("5270", 3)],
)

# Archivo directo para conflicto marcador vs archivo.
write_fixture("ANEXO.pdf", [src_param.pages[1]], [])

print("Fixtures creados:")
for pdf_path in sorted(fixtures.glob("*.pdf")):
    print(f"- {pdf_path.name}")
