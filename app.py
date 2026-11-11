"""Punto de entrada de ProcesarDC (lo usa tambien ProcesarDC.spec para PyInstaller)."""

import sys

from procesardc.ventana import App

# Identidad propia para Windows: la barra de tareas agrupa la app con su icono en lugar
# del de Python cuando se ejecuta desde el codigo.
ID_APLICACION = "UEx.SGTRI.ProcesarDC"


def _identidad_windows() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ID_APLICACION)
    except Exception:
        pass


def main() -> None:
    _identidad_windows()
    App().mainloop()


if __name__ == "__main__":
    main()
