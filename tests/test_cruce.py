"""Cruce JP vs Excel: resultado de referencia y reglas de asignacion manual/validacion.

El fichero tests/datos/cruce_esperado.json fija el resultado actual del analisis para
los JP y Excel de ej/. Si un cambio de reglas lo altera a proposito, regeneralo con:

    ACTUALIZAR_ESPERADOS=1 python -m pytest tests/test_cruce.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conftest import EJ, FIXTURES, analizar, cargar_origen
from procesardc.modelos import Estado
from procesardc.normalizacion import normalizar_jg_manual

ESPERADOS = Path(__file__).resolve().parent / "datos" / "cruce_esperado.json"
COMBINACIONES = [
    (jp, excel)
    for jp in ("JP536.pdf", "JP576.pdf")
    for excel in ("DATOS JG.xlsx", "DATOS JG2.xlsx", "DATOS JG3.xlsx")
]


def resumen(inst) -> dict:
    return {
        "paginas": [
            {
                "pagina": r.pagina.page_number,
                "estado": r.estado.value,
                "jg": r.jg_efectivo,
                "candidatos": " | ".join(r.candidatos),
                "color": r.resaltado.value,
                "probable": r.jg_probable,
                "origen_probable": r.origen_probable,
                "discrepancias": [d.campo for d in r.discrepancias],
            }
            for r in inst.main_results
        ],
        "excel_no_asignadas": [r["jg"] for r in inst.excel_unassigned_results],
    }


@pytest.fixture(scope="module")
def esperados() -> dict:
    if os.environ.get("ACTUALIZAR_ESPERADOS") == "1":
        return {}
    return json.loads(ESPERADOS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def guardar_esperados_si_se_pide():
    acumulado: dict = {}
    yield acumulado
    if os.environ.get("ACTUALIZAR_ESPERADOS") == "1":
        ESPERADOS.parent.mkdir(parents=True, exist_ok=True)
        ESPERADOS.write_text(json.dumps(acumulado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


@pytest.mark.parametrize(("jp", "excel"), COMBINACIONES)
def test_cruce_coincide_con_referencia(app_sin_ui, esperados, guardar_esperados_si_se_pide, jp, excel):
    analizar(app_sin_ui, EJ / jp, EJ / excel)
    clave = f"{jp} | {excel}"
    obtenido = resumen(app_sin_ui)
    if os.environ.get("ACTUALIZAR_ESPERADOS") == "1":
        guardar_esperados_si_se_pide[clave] = obtenido
        return
    assert obtenido == esperados[clave]


def test_jp536_cuadra_entero_con_datos_jg(app_sin_ui):
    analizar(app_sin_ui, EJ / "JP536.pdf", EJ / "DATOS JG.xlsx")
    assert len(app_sin_ui.main_results) == 25
    assert all(r.estado is Estado.ENCONTRADO for r in app_sin_ui.main_results)
    # 26 filas en el Excel y 25 pagos: queda exactamente una sin asignar.
    assert len(app_sin_ui.excel_unassigned_results) == 1


def _validar_modo_normal(inst) -> str:
    cargar_origen(inst, FIXTURES / "origen_contenedor_ok.pdf")
    return inst._validate_before_processing()


def test_procesar_exige_analisis_previo(app_sin_ui):
    assert _validar_modo_normal(app_sin_ui) == "Debe ejecutar el análisis antes de procesar"


def test_jg_asignado_que_no_esta_en_el_pdf_de_jg(app_sin_ui):
    analizar(app_sin_ui, EJ / "JP536.pdf", EJ / "DATOS JG.xlsx")
    # El contenedor pequeño solo trae los JG 5270 y 5283.
    assert _validar_modo_normal(app_sin_ui) == (
        "Hay Justificantes de Pago con JG asignado que no existe en el archivo JG"
    )


def test_paginas_sin_jg_bloquean(app_sin_ui):
    analizar(app_sin_ui, EJ / "JP536.pdf", EJ / "DATOS JG2.xlsx")
    assert any(not r.jg_efectivo for r in app_sin_ui.main_results)
    assert _validar_modo_normal(app_sin_ui) == (
        "Hay Justificantes de Pago a los que no se ha asignado un número de JG"
    )


def _marcar(inst) -> None:
    """Lo que hacen los manejadores de la tabla tras cambiar una asignacion manual."""
    inst._rebuild_excel_unassigned_results()


@pytest.mark.parametrize("escrito", ["2026/00000{jg}", "{jg}-26", "0{jg}", "{jg}"])
def test_asignacion_manual_duplicada_se_detecta_en_cualquier_formato(app_sin_ui, escrito):
    analizar(app_sin_ui, EJ / "JP536.pdf", EJ / "DATOS JG.xlsx")
    primera, segunda = app_sin_ui.main_results[:2]
    jg = primera.jg_efectivo

    # Asignar a la pagina 2 el JG de la pagina 1 (como en el dialogo de doble clic).
    segunda.jg_manual = normalizar_jg_manual(escrito.format(jg=jg))
    _marcar(app_sin_ui)

    assert segunda.jg_efectivo == jg
    # Antes, "2026/..." quedaba como "5270-26" y la tabla no lo resaltaba.
    assert app_sin_ui._get_duplicated_assigned_jg_set() == {jg}
    assert _validar_modo_normal(app_sin_ui) == "Hay varias páginas de JP asignadas al mismo JG"


def test_limpiar_asignacion_manual_devuelve_el_jg_automatico(app_sin_ui):
    analizar(app_sin_ui, EJ / "JP536.pdf", EJ / "DATOS JG.xlsx")
    fila = app_sin_ui.main_results[1]
    automatico = fila.jg_automatico
    no_asignadas_antes = len(app_sin_ui.excel_unassigned_results)

    fila.jg_manual = normalizar_jg_manual("99999")
    _marcar(app_sin_ui)
    assert fila.jg_efectivo == "99999"
    # Su JG automatico pasa a la lista de filas Excel no asignadas.
    assert len(app_sin_ui.excel_unassigned_results) == no_asignadas_antes + 1

    fila.jg_manual = normalizar_jg_manual("   ")
    _marcar(app_sin_ui)
    assert fila.jg_efectivo == automatico
    assert len(app_sin_ui.excel_unassigned_results) == no_asignadas_antes
