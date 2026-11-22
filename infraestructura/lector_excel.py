"""Lectura y escritura de Excel (.xlsx, .xls, .xlsm) con xlwings.

Requiere Microsoft Excel instalado. Si se usa desde un QThread en Windows,
el hilo debe llamar antes a pythoncom.CoInitialize() (lo hace la interfaz).
"""

import sys
from pathlib import Path

from infraestructura.formato_carga import mapear
from servicios.errores import ArchivoInvalido

XLS_FILE_FORMAT = 56  # xlExcel8: formato .xls de Excel 97-2003


def _abrir_excel():
    import xlwings as xw
    try:
        app = xw.App(visible=False, add_book=False)
    except Exception as error:
        raise ArchivoInvalido(f"No se pudo iniciar Excel (¿está instalado?): {error}") from error
    app.display_alerts = False
    app.screen_updating = False
    return app


# El trabajo con el libro va en funciones aparte: así sus referencias COM se
# liberan al retornar, antes de app.quit() (si no, Windows informa
# RPC_E_DISCONNECTED al liberarlas con Excel ya cerrado).

def _leer_valores(app, ruta_absoluta: Path) -> list[list]:
    libro = app.books.open(str(ruta_absoluta), read_only=True, update_links=False)
    valores = libro.sheets[0].used_range.options(ndim=2).value
    libro.close()
    return valores


def _escribir_libro(app, ruta_absoluta: Path, encabezados, filas, formatos) -> None:
    libro = app.books.add()
    hoja = libro.sheets[0]
    hoja.range("A1").value = [encabezados, *filas]
    if filas:
        for indice, formato in (formatos or {}).items():
            hoja.range((2, indice + 1), (len(filas) + 1, indice + 1)).number_format = formato
    if ruta_absoluta.suffix.lower() == ".xls" and sys.platform == "win32":
        libro.api.SaveAs(str(ruta_absoluta), FileFormat=XLS_FILE_FORMAT)
    else:
        libro.save(str(ruta_absoluta))
    libro.close()


def leer(ruta: str) -> list[dict]:
    """Lee el rango usado de la primera hoja. Excel se cierra siempre (finally)."""
    ruta_absoluta = Path(ruta).resolve()
    if not ruta_absoluta.exists():
        raise ArchivoInvalido(f"No existe el archivo: {ruta}")
    app = _abrir_excel()
    try:
        valores = _leer_valores(app, ruta_absoluta)
    except Exception as error:
        raise ArchivoInvalido(f"No se pudo leer el archivo con Excel: {error}") from error
    finally:
        app.quit()
    if not valores or not any(v is not None for v in valores[0]):
        raise ArchivoInvalido("La primera hoja está vacía.")
    return mapear(valores[0], valores[1:])


def escribir(ruta: str, encabezados: list[str], filas: list[list],
             formatos: dict[int, str] | None = None) -> None:
    """Crea un libro con una hoja. `formatos` = {índice de columna: formato de número}."""
    ruta_absoluta = Path(ruta).resolve()
    app = _abrir_excel()
    try:
        _escribir_libro(app, ruta_absoluta, encabezados, filas, formatos)
    except Exception as error:
        raise ArchivoInvalido(f"No se pudo exportar con Excel: {error}") from error
    finally:
        app.quit()
