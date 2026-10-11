from __future__ import annotations

import sys
from pathlib import Path


EXPECTED_FILES = {
    "DC1234.pdf",
    "CJ5678.pdf",
    "RT9001.pdf",
    "ANEXO.pdf",
    "JG5270.pdf",
    "JG5283.pdf",
}

FORBIDDEN_FILES = {
    "origen_contenedor_ok.pdf",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python verificar_escenario_a.py <carpeta_salida>")
        return 2

    output_dir = Path(sys.argv[1]).expanduser().resolve()
    if not output_dir.exists() or not output_dir.is_dir():
        print(f"ERROR: no existe la carpeta de salida: {output_dir}")
        return 2

    existing_files = {p.name for p in output_dir.iterdir() if p.is_file()}

    missing = sorted(EXPECTED_FILES - existing_files)
    forbidden_present = sorted(name for name in FORBIDDEN_FILES if name in existing_files)

    generated_jg = sorted(
        p.name for p in output_dir.iterdir() if p.is_file() and p.name.upper().startswith("JG") and p.suffix.lower() == ".pdf"
    )

    print(f"Carpeta analizada: {output_dir}")
    print(f"Total PDFs detectados: {len([p for p in output_dir.iterdir() if p.is_file() and p.suffix.lower() == '.pdf'])}")

    if missing:
        print("FALTAN archivos esperados:")
        for name in missing:
            print(f"- {name}")
    else:
        print("OK: estan todos los archivos esperados del Escenario A.")

    if forbidden_present:
        print("ERROR: aparecen archivos que NO deberian copiarse:")
        for name in forbidden_present:
            print(f"- {name}")
    else:
        print("OK: no aparece el contenedor original.")

    print("JG detectados:")
    for name in generated_jg:
        print(f"- {name}")

    if missing or forbidden_present:
        return 1

    print("VALIDACION FINAL: ESCENARIO A CORRECTO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
