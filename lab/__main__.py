"""Permite ejecutar ``python -m lab`` con el mismo comportamiento que ``lab``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
