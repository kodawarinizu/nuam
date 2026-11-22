"""Constantes de configuración del sistema (sin archivos .env)."""

from pathlib import Path

# Las rutas se resuelven respecto de la carpeta del proyecto, para que
# main.py y scripts/inicializar_bd.py usen la misma base sin importar
# desde qué carpeta se ejecuten.
CARPETA_PROYECTO = Path(__file__).resolve().parent
RUTA_BD = str(CARPETA_PROYECTO / "nuam.db")
RUTA_LOGS = str(CARPETA_PROYECTO / "logs" / "app.log")

# Decisión abierta: un escenario del HDU dice 8–16; la hoja de flujo y la de
# tipos de datos dicen 8–19. Se deja configurable.
RANGO_SUMA_FACTORES = range(8, 20)
COLUMNAS = range(8, 38)
COLUMNAS_CALCULADAS = range(8, 34)      # con fórmula en el HDU
COLUMNAS_SOLO_INGRESO = range(34, 38)   # sin fórmula: se ingresan como factor

DECIMALES_FACTOR = 8
SECUENCIA_MINIMA = 10_000  # HDU: "superior a los 10.000" (10.000 no es válida)
EJERCICIO_MIN, EJERCICIO_MAX = 1990, 2100
LARGO_MAX_INSTRUMENTO = 50

# "ACN" viene del HDU; "CFI" y "FMU" son supuestos.
MERCADOS = {"ACN": "Acciones", "CFI": "CFI", "FMU": "Fondos mutuos"}
ORIGENES = ("MANUAL", "ARCHIVO", "PDF", "BOLSA")
ROLES = ("admin", "corredor", "consulta")

PBKDF2_ITERACIONES = 600_000
LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 5

# Hojas "3. Tipos de datos" y "3.2 Homologacion columnas" del HDU.
NOMBRES_COLUMNAS = {
    8: "Con crédito por IDPC generados a contar del 01.01.2017",
    9: "Con crédito por IDPC acumulados hasta el 31.12.2016",
    10: "Con derecho a crédito por pago de IDPC voluntario",
    11: "Sin derecho a crédito",
    12: "Rentas provenientes del registro RAP y Diferencia Inicial de sociedad acogida al ex Art. 14 TER A) LIR",
    13: "Otras rentas percibidas Sin Prioridad en su orden de imputación",
    14: "Exceso Distribuciones Desproporcionadas (N°9 Art.14 A)",
    15: "Utilidades afectadas con impuesto sustitutivo al FUT (ISFUT) Ley N°20.780",
    16: "Rentas generadas hasta el 31.12.1983 y/o utilidades afectadas con impuesto sustitutivo al FUT (ISFUT) Ley N°21.210",
    17: "Rentas Exentas de Impuesto Global Complementario (IGC) (Artículo 11, Ley 18.401), Afectas a Impuesto Adicional",
    18: "Rentas Exentas de Impuesto Global Complementario (IGC) y/o Impuesto Adicional (IA)",
    19: "Ingresos No Constitutivos de Renta",
    20: "No Sujetos a Restitución generados hasta el 31.12.2019 – Sin derecho a devolución",
    21: "No Sujetos a Restitución generados hasta el 31.12.2019 – Con derecho a devolución",
    22: "No Sujetos a Restitución generados a contar del 01.01.2020 – Sin derecho a devolución",
    23: "No Sujetos a Restitución generados a contar del 01.01.2020 – Con derecho a devolución",
    24: "Sujetos a Restitución (rentas afectas) – Sin derecho a devolución",
    25: "Sujetos a Restitución (rentas afectas) – Con derecho a devolución",
    26: "Sujetos a Restitución (rentas exentas) – Sin derecho a devolución",
    27: "Sujetos a Restitución (rentas exentas) – Con derecho a devolución",
    28: "Crédito por IPE (a contar del 01.01.2017)",
    29: "Acumulados hasta el 31.12.2016, asociados a rentas afectas – Sin derecho a devolución",
    30: "Acumulados hasta el 31.12.2016, asociados a rentas afectas – Con derecho a devolución",
    31: "Acumulados hasta el 31.12.2016, asociados a rentas exentas (Art. 11, Ley 18.401) – Sin derecho a devolución",
    32: "Acumulados hasta el 31.12.2016, asociados a rentas exentas (Art. 11, Ley 18.401) – Con derecho a devolución",
    33: "Crédito por IPE (acumulados hasta el 31.12.2016)",
    34: "Crédito por impuesto tasa adicional, Ex. Art. 21 LIR",
    35: "Tasa Efectiva del Crédito del FUT (TEF)",
    36: "Tasa Efectiva del Crédito del FUNT (TEX)",
    37: "Devolución de capital Art. 17 N° 7 LIR",
}

# Descripción del archivo de carga (hoja "3.1 Archivo de carga"), para la interfaz.
FORMATO_ARCHIVO = """Primera fila: encabezados (sin importar orden ni mayúsculas).

Obligatorias: Ejercicio (2023), Mercado (ACN), Instrumento (texto, máx. 50),
Fecha (DD-MM-AAAA), Secuencia (mayor que 10.000).
Opcionales: Numero de dividendo (0 por defecto), Tipo sociedad (A o C),
Valor Historico, Descripcion.

Archivo de factores: Factor 8 … Factor 37 (1 entero y 8 decimales, ej. 0,92345321).
Archivo de montos: Monto 8 … Monto 33 (enteros) y, opcionalmente, Factor 34 … Factor 37.
Una columna no puede traer monto y factor a la vez.

CSV: separador ";" o ",". Números en formato chileno (192.770.580 y 0,52277431)."""
