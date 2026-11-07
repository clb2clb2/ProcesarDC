"""Punto de entrada de ProcesarDC (lo usa tambien ProcesarDC.spec para PyInstaller)."""

from procesardc.ventana import App


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
