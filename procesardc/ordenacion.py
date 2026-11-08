"""Ordenacion de las tablas por columna (independiente de Tk).

Cada columna tiene un tipo que decide como se compara su texto:
- "numero": enteros ("7" antes que "25").
- "importe": decimales en formato espanol ("9,50" antes que "131,00").
- "fecha": dd-mm-aaaa o dd/mm/aaaa, por fecha real.
- "texto": sin mayusculas ni acentos y con orden natural ("JG 5270-26" antes que "JG 10012-26").

Las celdas vacias, o que no se pueden interpretar segun el tipo, van siempre al final.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Sequence, TypeVar

from .normalizacion import normalizar_texto, parse_decimal

T = TypeVar("T")

NUMERO = "numero"
IMPORTE = "importe"
FECHA = "fecha"
TEXTO = "texto"

_FORMATOS_FECHA = ("%d-%m-%Y", "%d/%m/%Y")


def clave(valor: object, tipo: str = TEXTO):
    """Clave de ordenacion del valor, o None si va al final (vacio o no interpretable)."""
    texto = str(valor if valor is not None else "").strip()
    if not texto:
        return None

    if tipo == NUMERO:
        return int(texto) if texto.lstrip("-").isdigit() else None

    if tipo == IMPORTE:
        try:
            return parse_decimal(texto)
        except Exception:
            return None

    if tipo == FECHA:
        for formato in _FORMATOS_FECHA:
            try:
                return datetime.strptime(texto, formato)
            except ValueError:
                continue
        return None

    # Orden natural: los trozos alternan texto y numero, asi que se comparan siempre del mismo tipo.
    partes = re.split(r"(\d+)", normalizar_texto(texto))
    return [int(p) if i % 2 else p for i, p in enumerate(partes)]


def ordenar(filas: Sequence[T], valores: Iterable[object], tipo: str, descendente: bool = False) -> list[T]:
    """Ordena `filas` segun `valores` (uno por fila). Estable; los valores sin clave quedan al final."""
    con_clave: list[tuple[object, T]] = []
    sin_clave: list[T] = []
    for fila, valor in zip(filas, valores):
        k = clave(valor, tipo)
        if k is None:
            sin_clave.append(fila)
        else:
            con_clave.append((k, fila))

    con_clave.sort(key=lambda par: par[0], reverse=descendente)
    return [fila for _k, fila in con_clave] + sin_clave
