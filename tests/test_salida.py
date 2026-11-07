"""procesardc.salida: plan de ficheros y escritura sin dejar salidas a medias."""

from __future__ import annotations

import pytest
from pypdf import PdfReader

from conftest import EJ, FIXTURES
from procesardc import salida
from procesardc.secciones import escanear_origen


def _plan(destino, *origenes, dc=1234, cj=5678):
    escaneo = escanear_origen(list(origenes))
    return salida.planificar(destino / "2026000001234 (REMESA INV)", escaneo.secciones, dc, cj)


def _sin_temporales(carpeta):
    return not [p for p in carpeta.iterdir() if p.name.startswith(salida.PREFIJO_TEMPORAL)]


def _texto(ruta, pagina):
    return PdfReader(str(ruta)).pages[pagina].extract_text()


def test_nombre_carpeta():
    assert salida.nombre_carpeta("2026", 1234, " Remesa INV ") == "2026000001234 (REMESA INV)"


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [('A/B:C*D?"E<F>G|H', "A_B_C_D__E_F_G_H"), ("ANEXO. ", "ANEXO"), ("...", "SECCION"), ("", "SECCION")],
)
def test_nombre_seguro(titulo, esperado):
    assert salida.nombre_seguro(titulo) == esperado


def test_plan_no_toca_el_disco(tmp_path):
    plan = _plan(tmp_path, FIXTURES / "origen_contenedor_ok.pdf", FIXTURES / "ANEXO.pdf")
    assert not plan.carpeta.exists()
    # ANEXO por marcador y ANEXO.pdf directo acaban con el mismo nombre.
    assert [p.name for p in plan.duplicados()] == ["ANEXO.pdf"]
    assert plan.existentes() == []


def test_duplicados_sin_distinguir_mayusculas(tmp_path):
    plan = salida.PlanSalida(tmp_path, copias=[(EJ / "PARAM.pdf", tmp_path / "Param.pdf"), (EJ / "PARAM.pdf", tmp_path / "PARAM.pdf")])
    assert [p.name for p in plan.duplicados()] == ["PARAM.pdf"]


def test_genera_carpeta_nueva_y_anade_paginas_jp(tmp_path):
    plan = _plan(tmp_path, FIXTURES / "origen_contenedor_ok.pdf")
    salida.generar(plan, EJ / "JP536.pdf", {"5270": [3, 1], "5283": [2]})

    jg5270 = plan.carpeta / "JG5270.pdf"
    assert len(PdfReader(str(jg5270)).pages) == 3
    # Las paginas JP van en el orden indicado, detras de las del JG.
    assert _texto(jg5270, 1) == _texto(EJ / "JP536.pdf", 2)
    assert _texto(jg5270, 2) == _texto(EJ / "JP536.pdf", 0)
    assert _texto(plan.carpeta / "JG5283.pdf", 1) == _texto(EJ / "JP536.pdf", 1)
    assert _sin_temporales(tmp_path)


def test_carpeta_existente_se_completa_sin_borrar_lo_demas(tmp_path):
    plan = _plan(tmp_path, FIXTURES / "origen_contenedor_ok.pdf")
    plan.carpeta.mkdir(parents=True)
    (plan.carpeta / "DC1234.pdf").write_bytes(b"version antigua")
    (plan.carpeta / "notas.txt").write_text("no tocar", encoding="utf-8")
    assert [p.name for p in plan.existentes()] == ["DC1234.pdf"]

    salida.generar(plan)

    assert (plan.carpeta / "notas.txt").read_text(encoding="utf-8") == "no tocar"
    assert len(PdfReader(str(plan.carpeta / "DC1234.pdf")).pages) == 1
    assert len(list(plan.carpeta.iterdir())) == 7
    assert _sin_temporales(tmp_path)


@pytest.mark.parametrize(
    ("paginas", "error"),
    [
        ({"9999": [1]}, "No existe archivo JG para el identificador 9999"),
        ({"5270": [26]}, "Pagina JP fuera de rango: 26"),
        ({"5270": [0]}, "Pagina JP fuera de rango: 0"),
    ],
)
def test_asignaciones_invalidas_no_escriben_nada(tmp_path, paginas, error):
    plan = _plan(tmp_path, FIXTURES / "origen_contenedor_ok.pdf")
    with pytest.raises(ValueError, match=error):
        salida.generar(plan, EJ / "JP536.pdf", paginas)
    assert list(tmp_path.iterdir()) == []


def test_sin_pdf_jp_con_asignaciones(tmp_path):
    plan = _plan(tmp_path, FIXTURES / "origen_contenedor_ok.pdf")
    with pytest.raises(ValueError, match="Falta el PDF"):
        salida.generar(plan, None, {"5270": [1]})


@pytest.mark.parametrize("carpeta_previa", [False, True], ids=["carpeta-nueva", "carpeta-existente"])
def test_fallo_a_mitad_no_deja_salida_parcial(tmp_path, monkeypatch, carpeta_previa):
    destino = tmp_path / "salida"
    plan = _plan(destino, FIXTURES / "origen_contenedor_ok.pdf", EJ / "PARAM.pdf")
    if carpeta_previa:
        plan.carpeta.mkdir(parents=True)
        (plan.carpeta / "DC1234.pdf").write_bytes(b"version antigua")

    # El tercer PDF falla al escribirse, cuando ya se han escrito otros dos.
    escritos = []

    class WriterQueFalla(salida.PdfWriter):
        def write(self, stream):
            escritos.append(stream.name)
            if len(escritos) == 3:
                raise OSError("disco lleno")
            return super().write(stream)

    monkeypatch.setattr(salida, "PdfWriter", WriterQueFalla)

    with pytest.raises(OSError, match="disco lleno"):
        salida.generar(plan)
    assert len(escritos) == 3

    if carpeta_previa:
        assert [p.name for p in plan.carpeta.iterdir()] == ["DC1234.pdf"]
        assert (plan.carpeta / "DC1234.pdf").read_bytes() == b"version antigua"
    else:
        assert not plan.carpeta.exists()
    assert _sin_temporales(destino)
