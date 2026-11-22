"""Cálculo y validación de factores (funciones puras, sin base de datos)."""

from decimal import ROUND_HALF_UP, Decimal

import config
from infraestructura.numeros import decimal_a_texto
from servicios.errores import ValidacionError

_PASO = Decimal(1).scaleb(-config.DECIMALES_FACTOR)  # 0.00000001


def _rango_texto(rango: range) -> str:
    return f"{rango.start} a {rango.stop - 1}"


def redondear(valor: Decimal) -> Decimal:
    """Redondea a DECIMALES_FACTOR decimales con ROUND_HALF_UP."""
    return valor.quantize(_PASO, rounding=ROUND_HALF_UP)


def calcular_factores(montos: dict[int, int]) -> dict[int, Decimal]:
    """factor = monto / suma de montos de RANGO_SUMA_FACTORES (columnas con fórmula)."""
    suma = sum(montos.get(c) or 0 for c in config.RANGO_SUMA_FACTORES)
    if suma <= 0:
        raise ValidacionError(
            f"La suma de los montos de las columnas {_rango_texto(config.RANGO_SUMA_FACTORES)} "
            "debe ser mayor que 0 para calcular los factores.",
            campo=f"monto_{config.RANGO_SUMA_FACTORES.start}",
        )
    divisor = Decimal(suma)
    return {
        columna: redondear(Decimal(monto) / divisor)
        for columna, monto in sorted(montos.items())
        if columna in config.COLUMNAS_CALCULADAS and monto is not None
    }


def validar_factores(factores: dict[int, Decimal], calculados: bool) -> None:
    """Cada factor entre 0 y 1; si no son calculados, suma del rango ≤ 1 (estricta).

    Si los factores vienen de montos, la suma ya es 1 por construcción y no se
    vuelve a validar: el redondeo podría dar 1,00000001 sin que haya error.
    """
    for columna, factor in sorted(factores.items()):
        if columna not in config.COLUMNAS:
            raise ValidacionError(f"La columna {columna} no existe (válidas: 8 a 37).")
        if factor < 0 or factor > 1:
            raise ValidacionError(
                f"Columna {columna}: el factor {decimal_a_texto(factor)} debe estar entre 0 y 1.",
                campo=f"factor_{columna}",
            )
    if not calculados:
        suma = sum((f for c, f in factores.items() if c in config.RANGO_SUMA_FACTORES), Decimal(0))
        if suma > 1:
            raise ValidacionError(
                f"La suma de los factores de las columnas {_rango_texto(config.RANGO_SUMA_FACTORES)} "
                f"es {decimal_a_texto(suma)} y no puede ser mayor que 1.",
                campo=f"factor_{config.RANGO_SUMA_FACTORES.start}",
            )


def suma_factores(factores: dict[int, Decimal]) -> Decimal:
    """Suma de los factores de RANGO_SUMA_FACTORES (para mostrar en la interfaz)."""
    return sum((f for c, f in factores.items() if c in config.RANGO_SUMA_FACTORES), Decimal(0))


def preparar_factores(montos: dict[int, int], factores: dict[int, Decimal]) -> dict[int, Decimal]:
    """Obtiene los factores finales de una calificación y los valida.

    - Con montos: calcula 8–33 y toma los factores 34–37 que vengan.
    - Sin montos: usa los factores ingresados (redondeados a 8 decimales).
    """
    factores = {c: redondear(f) for c, f in factores.items()}
    if montos:
        for columna in sorted(montos):
            if columna not in config.COLUMNAS_CALCULADAS:
                raise ValidacionError(
                    f"Columna {columna}: no tiene fórmula en el HDU; ingrese su factor, no su monto.",
                    campo=f"monto_{columna}",
                )
            if columna in factores:
                raise ValidacionError(
                    f"Columna {columna}: trae monto y factor a la vez; deje solo uno.",
                    campo=f"monto_{columna}",
                )
        for columna in sorted(factores):
            if columna not in config.COLUMNAS_SOLO_INGRESO:
                raise ValidacionError(
                    f"Columna {columna}: cuando se ingresan montos, el factor se calcula "
                    "(solo las columnas 34 a 37 se ingresan como factor).",
                    campo=f"factor_{columna}",
                )
        resultado = calcular_factores(montos) | factores
        validar_factores(resultado, calculados=True)
        return resultado
    if not factores:
        raise ValidacionError("Debe ingresar montos o factores.")
    validar_factores(factores, calculados=False)
    return factores
