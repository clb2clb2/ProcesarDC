"""Sugerencias para corregir los marcadores de JG del PDF a partir del Excel (que es el fiable).

Cada numero marcado en el PDF que no esta en el Excel se intenta emparejar con un JG del Excel
que no tiene marcador:
- por parecido: un digito distinto, uno de mas o de menos, o dos contiguos intercambiados;
- por orden: el unico JG que falta entre los marcadores correctos anterior y siguiente.
Solo se propone el cambio cuando la pareja no es ambigua; lo demas se lista tal cual.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .modelos import OriginSection

MAX_LINEAS = 15

# Puntuacion de una pareja (marcador erroneo, JG que falta): cuanto mas, mas segura.
PARECIDO_Y_ORDEN = 3
PARECIDO = 2
ORDEN = 1


class Tipo(Enum):
    CAMBIAR = "cambiar"  # marcador con errata: se sabe cual es el bueno
    SOBRA = "sobra"  # marcador que no es de ningun JG del Excel
    FALTA = "falta"  # JG del Excel sin marcador
    RENOMBRAR = "renombrar"  # JG deducido del nombre del archivo, con errata
    ARCHIVO_SOBRA = "archivo_sobra"  # JG deducido del nombre del archivo, que no esta en el Excel


@dataclass
class Sugerencia:
    """Una correccion que hay que hacer en el PDF de justificantes de gasto."""

    tipo: Tipo
    archivo: Path | None = None  # PDF donde esta el marcador (o el que hay que renombrar)
    pagina: int = 0  # pagina del marcador, 1 = primera (0 si no aplica)
    marcador: str = ""  # texto actual del marcador (o numero del JG del nombre del archivo)
    numero: str = ""  # JG correcto (CAMBIAR, RENOMBRAR) o JG que falta (FALTA)
    # FALTA: JG correcto anterior por orden, para orientar donde va el marcador.
    anterior: str = ""
    anterior_pagina: int = 0
    anterior_archivo: Path | None = None

    @property
    def texto(self) -> str:
        nombre = self.archivo.name if self.archivo else ""
        if self.tipo is Tipo.CAMBIAR:
            return f"En «{nombre}», página {self.pagina}: cambie el marcador «{self.marcador}» por «{self.numero}»."
        if self.tipo is Tipo.SOBRA:
            return f"En «{nombre}», página {self.pagina}: el marcador «{self.marcador}» no corresponde a ningún JG del Excel."
        if self.tipo is Tipo.RENOMBRAR:
            return f"Cambie el nombre del archivo «{nombre}» para que sea del JG {self.numero}."
        if self.tipo is Tipo.ARCHIVO_SOBRA:
            return f"El archivo «{nombre}» es del JG {self.marcador}, que no está en el Excel."
        return f"Falta el marcador del JG {self.numero}{self.pista}."

    @property
    def pista(self) -> str:
        """FALTA: " (por el orden, despues del JG ...)" o ""."""
        if not self.anterior:
            return ""
        return (
            f" (por el orden, después del JG {self.anterior}, que empieza en la página "
            f"{self.anterior_pagina} de «{self.anterior_archivo.name}»)"
        )


@dataclass(frozen=True, eq=False)  # se compara por identidad (sirve de clave)
class _Marcador:
    seccion: OriginSection
    indice: int  # posicion entre los JG de su archivo, por pagina

    @property
    def numero(self) -> str:
        return self.seccion.numeric_id

    @property
    def archivo(self) -> str:
        return self.seccion.source_path.name

    @property
    def pagina(self) -> int:
        return (self.seccion.start_page or 0) + 1


def distancia(a: str, b: str) -> int:
    """Distancia de edicion con trasposicion de contiguos (Damerau, version OSA)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            coste = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + coste)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def _por_archivo(secciones: list[OriginSection]) -> list[list[_Marcador]]:
    grupos: dict[str, list[OriginSection]] = {}
    for s in secciones:
        if s.is_numeric and s.numeric_id:
            grupos.setdefault(str(s.source_path), []).append(s)
    return [
        [_Marcador(s, i) for i, s in enumerate(sorted(grupo, key=lambda s: s.start_page or 0))]
        for grupo in grupos.values()
    ]


def _hueco(marcadores: list[_Marcador], indice: int, ids_excel: set[str]) -> tuple[int | None, int | None]:
    """Numeros de los marcadores correctos anterior y siguiente (None si no hay)."""
    anterior = next((int(m.numero) for m in reversed(marcadores[:indice]) if m.numero in ids_excel), None)
    siguiente = next((int(m.numero) for m in marcadores[indice + 1:] if m.numero in ids_excel), None)
    return anterior, siguiente


def _en_hueco(numero: str, hueco: tuple[int | None, int | None]) -> bool:
    anterior, siguiente = hueco
    if anterior is None and siguiente is None:
        return False  # sin vecinos correctos el orden no dice nada
    n = int(numero)
    return (anterior is None or anterior < n) and (siguiente is None or n < siguiente)


def _emparejar(erroneos: list[_Marcador], faltan: set[str], grupos, ids_excel) -> dict[_Marcador, str]:
    """Parejas no ambiguas, empezando por las mas seguras."""
    puntos: dict[tuple[_Marcador, str], int] = {}
    for m in erroneos:
        hueco = _hueco(grupos[m.seccion.source_path], m.indice, ids_excel)
        for f in faltan:
            parecido = distancia(m.numero, f) <= 1
            orden = _en_hueco(f, hueco)
            if parecido or orden:
                puntos[(m, f)] = PARECIDO_Y_ORDEN if parecido and orden else PARECIDO if parecido else ORDEN

    parejas: dict[_Marcador, str] = {}
    for nivel in (PARECIDO_Y_ORDEN, PARECIDO, ORDEN):
        cambios = True
        while cambios:
            cambios = False
            libres = {k: p for k, p in puntos.items() if k[0] not in parejas and k[1] not in parejas.values()}
            for (m, f), p in libres.items():
                if p != nivel:
                    continue
                # Ambigua si el marcador o el JG tienen otra opcion igual de buena (o mejor).
                otras_de_m = [k for k, q in libres.items() if k[0] == m and k[1] != f and q >= p]
                otras_de_f = [k for k, q in libres.items() if k[1] == f and k[0] != m and q >= p]
                if not otras_de_m and not otras_de_f:
                    parejas[m] = f
                    cambios = True
                    break
    return parejas


def _orden_creciente(marcadores: list[_Marcador], ids_excel: set[str]) -> bool:
    numeros = [int(m.numero) for m in marcadores if m.numero in ids_excel]
    return numeros == sorted(numeros)


def _anterior(f: str, grupos: dict, ids_excel: set[str]) -> _Marcador | None:
    """Marcador correcto inmediatamente anterior por numero al JG f (si los marcadores van en orden)."""
    mejor: _Marcador | None = None
    for marcadores in grupos.values():
        if not _orden_creciente(marcadores, ids_excel):
            continue
        for m in marcadores:
            if m.numero in ids_excel and int(m.numero) < int(f) and (mejor is None or int(m.numero) > int(mejor.numero)):
                mejor = m
    return mejor


def sugerencias(secciones: list[OriginSection], ids_excel: set[str]) -> list[Sugerencia]:
    """Lo que hay que corregir en el PDF para que sus JG sean los del Excel."""
    lista = _por_archivo(secciones)
    grupos = {m[0].seccion.source_path: m for m in lista if m}
    marcadores = [m for grupo in lista for m in grupo]
    erroneos = [m for m in marcadores if m.numero not in ids_excel]
    faltan = ids_excel - {m.numero for m in marcadores}
    parejas = _emparejar(erroneos, faltan, grupos, ids_excel)

    resultado: list[Sugerencia] = []
    for m in sorted(erroneos, key=lambda m: (m.archivo.lower(), m.pagina)):
        nuevo = parejas.get(m, "")
        ruta = m.seccion.source_path
        if not m.seccion.from_marker:  # JG deducido del nombre del archivo
            tipo = Tipo.RENOMBRAR if nuevo else Tipo.ARCHIVO_SOBRA
            resultado.append(Sugerencia(tipo, ruta, m.pagina, m.numero, nuevo))
        else:
            tipo = Tipo.CAMBIAR if nuevo else Tipo.SOBRA
            resultado.append(Sugerencia(tipo, ruta, m.pagina, m.seccion.title, nuevo))

    for f in sorted(faltan - set(parejas.values()), key=int):
        anterior = _anterior(f, grupos, ids_excel)
        if anterior is None:
            resultado.append(Sugerencia(Tipo.FALTA, numero=f))
        else:
            resultado.append(
                Sugerencia(
                    Tipo.FALTA, numero=f, anterior=anterior.numero, anterior_pagina=anterior.pagina,
                    anterior_archivo=anterior.seccion.source_path,
                )
            )
    return resultado


def textos(lista: list[Sugerencia]) -> list[str]:
    """Las sugerencias como lineas de texto (como mucho MAX_LINEAS y "... y N mas")."""
    lineas = [s.texto for s in lista]
    if len(lineas) > MAX_LINEAS:
        resto = len(lineas) - MAX_LINEAS
        lineas = lineas[:MAX_LINEAS] + [f"… y {resto} más."]
    return lineas
