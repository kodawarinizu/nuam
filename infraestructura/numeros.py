"""Conversión de valores crudos (Excel, CSV, PDF, formularios) y formato chileno."""

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from servicios.errores import ValidacionError

_ENTERO = re.compile(r"^-?\d+$")
_FORMATOS_FECHA = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d")


def _es_vacio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and valor.strip() == "")


def a_entero(valor) -> int | None:
    """int, float de Excel o texto chileno ("192.770.580") → int."""
    if _es_vacio(valor):
        return None
    if isinstance(valor, bool):
        raise ValidacionError(f"Valor no numérico: {valor!r}")
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(round(valor))
    if isinstance(valor, Decimal):
        return int(valor.to_integral_value(rounding=ROUND_HALF_UP))
    texto = str(valor).strip().replace("$", "").replace(" ", "").replace(".", "")
    if "," in texto:
        try:
            return int(Decimal(texto.replace(",", ".")).to_integral_value(rounding=ROUND_HALF_UP))
        except InvalidOperation:
            raise ValidacionError(f"Valor no numérico: {valor!r}") from None
    if not _ENTERO.match(texto):
        raise ValidacionError(f"Valor no numérico: {valor!r}")
    return int(texto)


def a_decimal(valor) -> Decimal | None:
    """float de Excel (vía str), Decimal o texto chileno ("0,52277431") → Decimal."""
    if _es_vacio(valor):
        return None
    if isinstance(valor, bool):
        raise ValidacionError(f"Valor no numérico: {valor!r}")
    if isinstance(valor, Decimal):
        resultado = valor
    elif isinstance(valor, int):
        resultado = Decimal(valor)
    elif isinstance(valor, float):
        resultado = Decimal(str(valor))  # nunca Decimal(float): arrastra el error binario
    else:
        texto = str(valor).strip().replace(" ", "")
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            resultado = Decimal(texto)
        except InvalidOperation:
            raise ValidacionError(f"Valor no numérico: {valor!r}") from None
    if not resultado.is_finite():
        raise ValidacionError(f"Valor no numérico: {valor!r}")
    return resultado


def a_texto(valor) -> str | None:
    """Texto sin espacios extremos. Un número entero de Excel (123.0) queda como "123"."""
    if _es_vacio(valor):
        return None
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def a_fecha(valor) -> str | None:
    """datetime/date o texto DD-MM-AAAA (también DD/MM/AAAA o ISO) → ISO AAAA-MM-DD."""
    if _es_vacio(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    for formato in _FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    raise ValidacionError(f"Fecha inválida: {valor!r} (use DD-MM-AAAA)")


def fecha_a_texto(iso: str | None) -> str:
    """ISO → DD-MM-AAAA para mostrar."""
    if not iso:
        return ""
    return date.fromisoformat(iso[:10]).strftime("%d-%m-%Y")


def fecha_hora_a_texto(iso: str | None) -> str:
    """Marca de tiempo ISO → DD-MM-AAAA HH:MM para mostrar."""
    if not iso:
        return ""
    return datetime.fromisoformat(iso).strftime("%d-%m-%Y %H:%M")


def entero_a_texto(valor: int | None) -> str:
    """192770580 → "192.770.580"."""
    if valor is None:
        return ""
    return f"{valor:,}".replace(",", ".")


def decimal_a_texto(valor: Decimal | None, decimales: int = 8) -> str:
    """Decimal("0.52277431") → "0,52277431"."""
    if valor is None:
        return ""
    return f"{valor:.{decimales}f}".replace(".", ",")
