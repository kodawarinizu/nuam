"""Creación de la conexión SQLite."""

import sqlite3
from pathlib import Path

RUTA_SCHEMA = Path(__file__).resolve().parent / "schema.sql"

# RETURNING y el upsert con índice parcial requieren SQLite 3.35.
VERSION_MINIMA_SQLITE = (3, 35, 0)


def _version_como_tupla(texto: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in texto.split("."))


def verificar_version_sqlite(version: str | None = None) -> None:
    """Lanza RuntimeError si la versión de SQLite es menor que la mínima."""
    version = version or sqlite3.sqlite_version
    if _version_como_tupla(version) < VERSION_MINIMA_SQLITE:
        minima = ".".join(str(p) for p in VERSION_MINIMA_SQLITE)
        raise RuntimeError(
            f"Se requiere SQLite {minima} o superior (se encontró {version}). "
            "Actualice Python a una versión que incluya un SQLite más reciente."
        )


def crear_conexion(ruta: str) -> sqlite3.Connection:
    """Abre la base, activa las llaves foráneas y crea el esquema si no existe.

    La conexión debe usarse solo desde el hilo principal.
    """
    verificar_version_sqlite()
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(RUTA_SCHEMA.read_text(encoding="utf-8"))
    return conexion
