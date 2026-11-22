import pytest

from servicios.errores import ValidacionError
from servicios.validaciones import validar_calificacion
from tests.conftest import calificacion_ejemplo


def _valida(**cambios):
    return validar_calificacion(calificacion_ejemplo(origen="MANUAL", **cambios))


def test_ejemplo_del_hdu_es_valido():
    assert _valida().instrumento == "COPEC"


def test_secuencia_limites():
    with pytest.raises(ValidacionError) as error:
        _valida(secuencia=10_000)
    assert error.value.campo == "secuencia"
    assert _valida(secuencia=10_001).secuencia == 10_001


def test_tipo_sociedad():
    assert _valida(tipo_sociedad="a").tipo_sociedad == "A"
    with pytest.raises(ValidacionError) as error:
        _valida(tipo_sociedad="B")
    assert error.value.campo == "tipo_sociedad"


def test_ejercicio():
    assert _valida(ejercicio=2023).ejercicio == 2023
    with pytest.raises(ValidacionError, match="Ejercicio"):
        _valida(ejercicio=23)


def test_mercado_invalido():
    with pytest.raises(ValidacionError, match="Mercado"):
        _valida(mercado="XXX")


def test_instrumento_normalizado():
    assert _valida(instrumento=" copec ").instrumento == "COPEC"
    with pytest.raises(ValidacionError, match="Instrumento"):
        _valida(instrumento="   ")
    with pytest.raises(ValidacionError, match="Instrumento"):
        _valida(instrumento="X" * 51)


def test_fecha_obligatoria():
    with pytest.raises(ValidacionError, match="Fecha"):
        _valida(fecha_pago=None)


def test_varios_errores_en_un_mensaje():
    with pytest.raises(ValidacionError) as error:
        _valida(ejercicio=23, secuencia=1)
    assert "Ejercicio" in str(error.value) and "Secuencia" in str(error.value)
    assert error.value.campo == "ejercicio"
