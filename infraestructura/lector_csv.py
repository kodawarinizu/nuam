"""Lectura y escritura de CSV con el módulo csv (no requiere Excel)."""

import csv
import io

from infraestructura.formato_carga import mapear
from servicios.errores import ArchivoInvalido


def _leer_texto(ruta: str) -> str:
    try:
        with open(ruta, "rb") as archivo:
            datos = archivo.read()
    except OSError as error:
        raise ArchivoInvalido(f"No se pudo abrir el archivo: {error}") from error
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("cp1252")  # CSV guardado por Excel en Windows


def leer(ruta: str) -> list[dict]:
    """Lee un CSV con encabezados; separador ';' o ',' (detectado en la primera línea)."""
    texto = _leer_texto(ruta)
    primera = next((linea for linea in texto.splitlines() if linea.strip()), None)
    if primera is None:
        raise ArchivoInvalido("El archivo está vacío.")
    separador = ";" if primera.count(";") >= primera.count(",") else ","
    filas = list(csv.reader(io.StringIO(texto), delimiter=separador))
    while filas and not any(c.strip() for c in filas[0]):
        filas.pop(0)
    return mapear(filas[0], filas[1:])


def escribir(ruta: str, encabezados: list[str], filas: list[list]) -> None:
    """Escribe con separador ';' y BOM UTF-8, para que Excel lo abra bien en español."""
    try:
        with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.writer(archivo, delimiter=";")
            escritor.writerow(encabezados)
            escritor.writerows(filas)
    except OSError as error:
        raise ArchivoInvalido(f"No se pudo escribir el archivo: {error}") from error
