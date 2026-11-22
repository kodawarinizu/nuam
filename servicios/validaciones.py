"""Reglas de validación de los datos básicos de una calificación."""

from datetime import date

import config
from servicios.entidades import Calificacion
from servicios.errores import ValidacionError


def normalizar_instrumento(instrumento: str | None) -> str:
    """"Copec", "COPEC" y " Copec " son el mismo instrumento."""
    return (instrumento or "").strip().upper()


def validar_calificacion(c: Calificacion) -> Calificacion:
    """Normaliza (instrumento, mercado, tipo) y valida. Lanza ValidacionError con todos los errores."""
    c.instrumento = normalizar_instrumento(c.instrumento)
    c.mercado = (c.mercado or "").strip().upper()
    c.tipo_sociedad = (c.tipo_sociedad or "").strip().upper() or None
    c.descripcion = (c.descripcion or "").strip() or None
    if c.numero_dividendo is None:
        c.numero_dividendo = 0

    errores: list[tuple[str, str]] = []
    if c.ejercicio is None or not (config.EJERCICIO_MIN <= c.ejercicio <= config.EJERCICIO_MAX):
        errores.append(("ejercicio", f"Ejercicio: debe estar entre {config.EJERCICIO_MIN} y "
                                     f"{config.EJERCICIO_MAX} (se recibió {c.ejercicio})."))
    if c.mercado not in config.MERCADOS:
        validos = ", ".join(config.MERCADOS)
        errores.append(("mercado", f"Mercado: '{c.mercado}' no es válido (válidos: {validos})."))
    if not c.instrumento:
        errores.append(("instrumento", "Instrumento: es obligatorio."))
    elif len(c.instrumento) > config.LARGO_MAX_INSTRUMENTO:
        errores.append(("instrumento", f"Instrumento: máximo {config.LARGO_MAX_INSTRUMENTO} caracteres."))
    try:
        date.fromisoformat(c.fecha_pago or "")
    except ValueError:
        errores.append(("fecha_pago", "Fecha de pago: es obligatoria (DD-MM-AAAA)."))
    if c.secuencia is None or c.secuencia <= config.SECUENCIA_MINIMA:
        errores.append(("secuencia", f"Secuencia: debe ser mayor que "
                                     f"{config.SECUENCIA_MINIMA:,}".replace(",", ".")
                                     + f" (se recibió {c.secuencia})."))
    if c.numero_dividendo < 0:
        errores.append(("numero_dividendo", "Número de dividendo: no puede ser negativo."))
    if c.tipo_sociedad is not None and c.tipo_sociedad not in ("A", "C"):
        errores.append(("tipo_sociedad", f"Tipo de sociedad: debe ser A (abierta) o C (cerrada) "
                                         f"(se recibió '{c.tipo_sociedad}')."))
    if c.valor_historico is not None and c.valor_historico < 0:
        errores.append(("valor_historico", "Valor histórico: no puede ser negativo."))
    if c.origen not in config.ORIGENES:
        errores.append(("origen", f"Origen: '{c.origen}' no es válido."))

    if errores:
        raise ValidacionError(" ".join(m for _, m in errores), campo=errores[0][0])
    return c
