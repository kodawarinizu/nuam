from datetime import date, datetime
from decimal import Decimal

import pytest

from infraestructura.numeros import (
    a_decimal, a_entero, a_fecha, a_texto, decimal_a_texto, entero_a_texto, fecha_a_texto,
)
from servicios.errores import ValidacionError


def test_a_entero():
    # Montos de la hoja "3.2 Homologacion columnas" del HDU.
    assert a_entero(192770580.0) == 192770580          # float de Excel
    assert a_entero("192.770.580") == 192770580        # texto chileno
    assert a_entero("$ 64.161.878") == 64161878        # como en un certificado
    assert a_entero(111812860) == 111812860
    assert a_entero("") is None and a_entero(None) is None
    with pytest.raises(ValidacionError):
        a_entero("abc")


def test_a_decimal():
    assert a_decimal(0.52277431) == Decimal("0.52277431")   # float de Excel vía str
    assert a_decimal("0,52277431") == Decimal("0.52277431")  # texto chileno
    assert a_decimal("0.17400052") == Decimal("0.17400052")
    assert a_decimal("  ") is None
    with pytest.raises(ValidacionError):
        a_decimal("uno")
    with pytest.raises(ValidacionError):
        a_decimal("NaN")


def test_a_fecha():
    # Fecha de la fila de ejemplo de la hoja "3.1 Archivo de carga" del HDU.
    assert a_fecha("12-12-2023") == "2023-12-12"
    assert a_fecha("12/12/2023") == "2023-12-12"
    assert a_fecha(datetime(2023, 12, 12, 0, 0)) == "2023-12-12"
    assert a_fecha(date(2023, 12, 12)) == "2023-12-12"
    with pytest.raises(ValidacionError):
        a_fecha("31-02-2023")


def test_texto_y_formato():
    assert a_texto(123123.0) == "123123"
    assert a_texto(" Copec ") == "Copec"
    assert fecha_a_texto("2023-12-12") == "12-12-2023"
    assert entero_a_texto(192770580) == "192.770.580"
    assert decimal_a_texto(Decimal("0.52277431")) == "0,52277431"
