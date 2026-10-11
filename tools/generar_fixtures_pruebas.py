from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter


base = Path(r"c:/Proyectos-Github/ProcesarDC/ej")
fixtures = base / "fixtures"
fixtures.mkdir(parents=True, exist_ok=True)

src_dc = PdfReader(str(base / "DC3391.pdf"))
src_cj = PdfReader(str(base / "CJ0238.pdf"))
src_rt = PdfReader(str(base / "RT536.pdf"))
src_jg = PdfReader(str(base / "JG 5270-7063(25+1).pdf"))
src_param = PdfReader(str(base / "PARAM.pdf"))

# Caso OK: mezcla de no numericos y numericos en un unico contenedor.
writer = PdfWriter()
for page in [src_dc.pages[0], src_cj.pages[0], src_rt.pages[0], src_param.pages[0], src_jg.pages[0], src_jg.pages[1]]:
    writer.add_page(page)
for title, page_idx in [
    ("DC1234", 0),
    ("CJ5678", 1),
    ("RT9001", 2),
    ("ANEXO", 3),
    ("5270", 4),
    ("5283", 5),
]:
    writer.add_outline_item(title, page_idx)
with open(fixtures / "origen_contenedor_ok.pdf", "wb") as fh:
    writer.write(fh)

# Conflicto texto duplicado.
writer = PdfWriter()
for page in [src_dc.pages[0], src_cj.pages[0], src_param.pages[0], src_rt.pages[0]]:
    writer.add_page(page)
for title, page_idx in [
    ("DC1234", 0),
    ("CJ5678", 1),
    ("ANEXO", 2),
    ("ANEXO", 3),
]:
    writer.add_outline_item(title, page_idx)
with open(fixtures / "origen_conflicto_texto_duplicado.pdf", "wb") as fh:
    writer.write(fh)

# Conflicto JG numerico duplicado.
writer = PdfWriter()
for page in [src_dc.pages[0], src_cj.pages[0], src_jg.pages[0], src_jg.pages[1]]:
    writer.add_page(page)
for title, page_idx in [
    ("DC1234", 0),
    ("CJ5678", 1),
    ("5270", 2),
    ("5270", 3),
]:
    writer.add_outline_item(title, page_idx)
with open(fixtures / "origen_conflicto_jg_duplicado.pdf", "wb") as fh:
    writer.write(fh)

# Archivo directo para conflicto marcador vs archivo.
writer = PdfWriter()
writer.add_page(src_param.pages[1])
with open(fixtures / "ANEXO.pdf", "wb") as fh:
    writer.write(fh)

print("Fixtures creados:")
for pdf_path in sorted(fixtures.glob("*.pdf")):
    print(f"- {pdf_path.name}")
