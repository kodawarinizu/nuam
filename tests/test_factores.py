from decimal import Decimal

import pytest

from servicios.factores import calcular_factores, preparar_factores, suma_factores, validar_factores
from servicios.errores import ValidacionError
from tests.conftest import FACTORES_HDU, MONTOS_HDU


def test_ejemplo_hdu():
    # HDU, hoja "3.2 Homologacion columnas".
    factores = calcular_factores(MONTOS_HDU)
    assert factores == FACTORES_HDU
    assert suma_factores(factores) == Decimal("1.00000000")
    validar_factores(factores, calculados=True)


def test_factores_ingresados_que_suman_uno_pasan():
    validar_factores({8: Decimal("0.5"), 19: Decimal("0.5")}, calculados=False)


def test_factores_ingresados_que_suman_mas_de_uno_fallan():
    with pytest.raises(ValidacionError, match="1,00000001"):
        validar_factores({8: Decimal("0.50000001"), 9: Decimal("0.5")}, calculados=False)


def test_ejemplo_3_1_del_hdu_se_rechaza():
    # HDU, hoja "3.1 Archivo de carga": las 30 columnas con 0,92345321.
    factores = {c: Decimal("0.92345321") for c in range(8, 38)}
    with pytest.raises(ValidacionError, match="11,08143852"):
        preparar_factores({}, factores)


def test_suma_de_montos_cero_falla():
    with pytest.raises(ValidacionError, match="mayor que 0"):
        calcular_factores({8: 0, 9: 0, 25: 100})


def test_factor_columna_34_mayor_que_uno_falla():
    with pytest.raises(ValidacionError, match="Columna 34"):
        validar_factores({34: Decimal("1.00000001")}, calculados=False)


def test_monto_columna_20_a_33_mayor_que_la_suma_falla():
    # Hoja 3 del HDU: ningún factor puede ser mayor que 1, aunque venga de montos.
    with pytest.raises(ValidacionError, match="Columna 25"):
        preparar_factores({8: 100, 25: 101}, {})


def test_montos_con_factores_34_a_37():
    factores = preparar_factores(dict(MONTOS_HDU), {34: Decimal("0.1")})
    assert factores[34] == Decimal("0.10000000")
    assert factores[8] == Decimal("0.52277431")


def test_monto_y_factor_en_la_misma_columna_falla():
    with pytest.raises(ValidacionError, match="monto y factor"):
        preparar_factores({8: 100}, {8: Decimal("1")})


def test_monto_en_columna_sin_formula_falla():
    with pytest.raises(ValidacionError, match="Columna 34"):
        preparar_factores({8: 100, 34: 5}, {})


def test_sin_montos_ni_factores_falla():
    with pytest.raises(ValidacionError):
        preparar_factores({}, {})
