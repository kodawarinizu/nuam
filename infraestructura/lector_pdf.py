"""Lectura de certificados PDF (Certificado N°70 del SII) con pdfplumber.

Los patrones están ajustados a la estructura del Certificado N°70 descrita en
la Res. Ex. SII N°98 de 2020 (Anexo 3), con columnas numeradas "(8)", "(9)"...
y montos en pesos ("$ 192.770.580"). DEBEN REVISARSE con un certificado real:
cada emisor puede diagramarlo distinto.

Nunca se inventan valores: un monto no encontrado queda None y se informa en
"_no_encontradas" para que el usuario lo corrija a mano.
"""

import re

import config
from servicios.errores import ArchivoInvalido

# Monto de una columna: "(N)", luego cualquier texto en la misma línea sin "$",
# y luego "$ 1.234.567". Se busca por número de columna, sin importar el orden.
PATRON_MONTO = r"\({columna}\)[^\n$]*\$\s*(-?\d[\d.]*)"
PATRON_ANIO_COMERCIAL = re.compile(r"A[ñn]o\s+comercial\s*:?\s*(\d{4})", re.IGNORECASE)

# Columna del certificado → columna del HDU. Supuesto: la numeración coincide.
# Pendiente de verificar con el formato oficial (anotado en README > Decisiones).
MAPEO_CERTIFICADO_A_HDU: dict[int, int] = {n: n for n in config.COLUMNAS}

# Del certificado solo se leen montos; las columnas 34–37 no tienen fórmula
# y se ingresan a mano como factor.
COLUMNAS_LEIDAS = config.COLUMNAS_CALCULADAS


def extraer_texto(ruta: str) -> str:
    import pdfplumber
    try:
        with pdfplumber.open(ruta) as pdf:
            texto = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
    except Exception as error:
        raise ArchivoInvalido(f"No se pudo leer el PDF (¿está dañado?): {error}") from error
    if not texto.strip():
        raise ArchivoInvalido("El PDF no contiene texto (¿es una imagen escaneada?).")
    return texto


def interpretar(texto: str) -> dict:
    """Busca el año comercial y cada monto en el texto extraído."""
    fila: dict = {"_fila": 1, "_texto": texto, "_no_encontradas": []}
    anio = PATRON_ANIO_COMERCIAL.search(texto)
    fila["ejercicio"] = anio[1] if anio else None
    for columna_certificado, columna_hdu in sorted(MAPEO_CERTIFICADO_A_HDU.items()):
        if columna_hdu not in COLUMNAS_LEIDAS:
            continue
        coincidencia = re.search(PATRON_MONTO.format(columna=columna_certificado), texto)
        if coincidencia:
            fila[f"monto_{columna_hdu}"] = coincidencia[1].rstrip(".")
        else:
            fila[f"monto_{columna_hdu}"] = None
            fila["_no_encontradas"].append(columna_hdu)
    return fila


def leer(ruta: str) -> list[dict]:
    """Mismo formato que los otros lectores: una lista con una fila (más el texto extraído)."""
    return [interpretar(extraer_texto(ruta))]
