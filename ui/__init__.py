"""Interfaz PySide6.

Compatibilidad Python 3.15 + PySide6 6.12: los atributos de la biblioteca
estándar que se cargan de forma perezosa (PEP 810) y se usan por primera vez
después de importar PySide6 quedan como objetos 'lazy_import' no invocables.
xlwings falla al importarse ("'lazy_import' object is not callable" en
concurrent.futures.ThreadPoolExecutor). Por eso xlwings se importa aquí, antes
que PySide6: este paquete se ejecuta antes que cualquier módulo de la interfaz.
"""

try:
    import xlwings  # noqa: F401
except Exception:  # noqa: BLE001 — sin Excel/xlwings la app funciona igual con CSV y PDF
    pass
