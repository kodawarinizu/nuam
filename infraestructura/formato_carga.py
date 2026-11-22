"""Formato del archivo de carga (hoja "3.1 Archivo de carga" del HDU).

Lo comparten lector_csv y lector_excel: mapea columnas por nombre de
encabezado, sin importar orden, mayúsculas ni tildes.
"""

import re
import unicodedata

import config
from servicios.errores import ArchivoInvalido

ENCABEZADOS = {
    "ejercicio": "ejercicio",
    "mercado": "mercado",
    "instrumento": "instrumento",
    "fecha": "fecha_pago",
    "fecha de pago": "fecha_pago",
    "fecha pago": "fecha_pago",
    "secuencia": "secuencia",
    "numero de dividendo": "numero_dividendo",
    "numero dividendo": "numero_dividendo",
    "dividendo": "numero_dividendo",
    "tipo sociedad": "tipo_sociedad",
    "tipo de sociedad": "tipo_sociedad",
    "valor historico": "valor_historico",
    "descripcion": "descripcion",
}
OBLIGATORIAS = {
    "ejercicio": "Ejercicio", "mercado": "Mercado", "instrumento": "Instrumento",
    "fecha_pago": "Fecha", "secuencia": "Secuencia",
}
_COLUMNA = re.compile(r"^(factor|monto)\s*(\d+)$")

# Encabezados que escribe la exportación (se pueden volver a cargar).
ENCABEZADOS_EXPORTACION = [
    "Ejercicio", "Mercado", "Instrumento", "Fecha", "Secuencia", "Numero de dividendo",
    "Tipo sociedad", "Valor Historico", "Descripcion", "Origen",
    *[f"Factor {c}" for c in config.COLUMNAS],
]


def normalizar_encabezado(texto) -> str:
    """" Número de Dividendo " → "numero de dividendo"."""
    if texto is None:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().replace("_", " ").split())


def _clave(encabezado) -> str | None:
    normalizado = normalizar_encabezado(encabezado)
    if normalizado in ENCABEZADOS:
        return ENCABEZADOS[normalizado]
    coincidencia = _COLUMNA.match(normalizado)
    if coincidencia and int(coincidencia[2]) in config.COLUMNAS:
        return f"{coincidencia[1]}_{int(coincidencia[2])}"
    return None  # columnas desconocidas se ignoran


def mapear(encabezados: list, filas: list[list], primera_fila: int = 2) -> list[dict]:
    """Convierte filas de valores crudos en dicts con claves canónicas y `_fila`."""
    claves = [_clave(e) for e in encabezados]
    presentes = [c for c in claves if c]
    repetidas = sorted({c for c in presentes if presentes.count(c) > 1})
    if repetidas:
        raise ArchivoInvalido(f"Columnas repetidas: {', '.join(repetidas)}.")
    faltantes = [nombre for clave, nombre in OBLIGATORIAS.items() if clave not in presentes]
    if faltantes:
        raise ArchivoInvalido(f"Falta la columna obligatoria: {', '.join(faltantes)}.")
    if not any(c.startswith(("factor_", "monto_")) for c in presentes):
        raise ArchivoInvalido("El archivo no trae columnas 'Factor N' ni 'Monto N'.")

    resultado = []
    for indice, valores in enumerate(filas):
        if all(v is None or str(v).strip() == "" for v in valores):
            continue  # fila vacía
        fila = {"_fila": primera_fila + indice}
        for clave, valor in zip(claves, valores):
            if clave:
                fila[clave] = valor
        resultado.append(fila)
    return resultado
