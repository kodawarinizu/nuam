"""Pruebas de impacto 4, 5 y 8 del HDU (hoja "4. Flujo de proceso") para la carga masiva."""

from decimal import Decimal

import pytest

from servicios.errores import ErrorNegocio, PermisoDenegado
from tests.conftest import fila_archivo


def _cargar(entorno, usuario, filas, corredor_id, tipo="ARCHIVO"):
    resultado = entorno.carga.previsualizar(filas, corredor_id, tipo)
    return resultado, entorno.carga.confirmar(usuario, resultado, tipo)


# Prueba 4: carga masiva de factores (si existe se actualiza; si no, se agrega).
def test_filas_nuevas_y_actualizadas(entorno):
    a = entorno.corredor_a
    _, resumen = _cargar(entorno, entorno.usuario_a, [fila_archivo()], a)
    assert resumen["insertadas"] == 1 and resumen["actualizadas"] == 0

    filas = [fila_archivo(descripcion="actualizada"), fila_archivo(secuencia="20000")]
    resultado = entorno.carga.previsualizar(filas, a)
    assert [f.estado for f in resultado.validas] == ["actualiza", "nueva"]
    resumen = entorno.carga.confirmar(entorno.usuario_a, resultado, "ARCHIVO")
    assert resumen["insertadas"] == 1 and resumen["actualizadas"] == 1

    lista = entorno.calificaciones.buscar(entorno.usuario_a)
    assert len(lista) == 2
    assert {c.descripcion for c in lista} == {"actualizada", None}
    auditoria = entorno.acciones("CARGA_MASIVA")[-1]["detalle"]
    assert auditoria["insertadas"] == 1 and auditoria["actualizadas"] == 1


# Prueba 5: carga masiva de montos.
def test_carga_de_montos_con_factores_34_a_37(entorno):
    # Montos de la hoja "3.2 Homologacion columnas" del HDU.
    fila = fila_archivo(factor_8=None, factor_9=None, factor_10=None, factor_11=None,
                        monto_8="192.770.580", monto_9="64.161.878", monto_10="0",
                        monto_11="111.812.860", factor_34="0,1")
    resultado, resumen = _cargar(entorno, entorno.usuario_a, [fila], entorno.corredor_a)
    assert resumen["insertadas"] == 1
    c = entorno.calificaciones.obtener(entorno.usuario_a, entorno.calificaciones.buscar(entorno.usuario_a)[0].id)
    assert c.factores[8] == Decimal("0.52277431") and c.factores[34] == Decimal("0.1")
    assert c.montos[8] == 192_770_580


def test_filas_invalidas_con_numero_y_motivo(entorno):
    filas = [
        fila_archivo(),
        fila_archivo(secuencia="9999", _fila=3),
        fila_archivo(tipo_sociedad="B", secuencia="20000", _fila=4),
        fila_archivo(monto_8="100", secuencia="30000", _fila=5),         # monto y factor en col. 8
        fila_archivo(secuencia="40000", factor_8="abc", _fila=6),
        fila_archivo(_fila=7),                                            # llave repetida
    ]
    resultado = entorno.carga.previsualizar(filas, entorno.corredor_a)
    assert len(resultado.validas) == 1
    motivos = {f.numero_fila: f.motivo for f in resultado.invalidas}
    assert "Secuencia" in motivos[3]
    assert "Tipo de sociedad" in motivos[4]
    assert "monto y factor" in motivos[5]
    assert "Factor 8" in motivos[6]
    assert "repetida" in motivos[7] and "fila 2" in motivos[7]


def test_ejemplo_3_1_del_hdu_se_rechaza(entorno):
    # HDU, hoja "3.1 Archivo de carga": las 30 columnas Factor 8 a 37 con 0,92345321.
    fila = fila_archivo(**{f"factor_{c}": "0,92345321" for c in range(8, 38)})
    resultado = entorno.carga.previsualizar([fila], entorno.corredor_a)
    assert resultado.validas == []
    assert "11,08143852" in resultado.invalidas[0].motivo


# Prueba 8: no se altera la información de bolsa.
def test_carga_de_corredor_con_llave_de_bolsa_no_altera_bolsa(entorno):
    _cargar(entorno, entorno.admin, [fila_archivo(descripcion="bolsa")], None)
    bolsa = entorno.calificaciones.buscar(entorno.admin, corredor=None)[0]
    assert bolsa.origen == "BOLSA"

    resultado, resumen = _cargar(entorno, entorno.usuario_a, [fila_archivo(descripcion="corredor")],
                                 entorno.corredor_a)
    assert resultado.validas[0].estado == "nueva" and resumen["insertadas"] == 1
    assert entorno.repo_calificaciones.obtener_por_id(bolsa.id)["descripcion"] == "bolsa"
    vista = entorno.calificaciones.buscar(entorno.usuario_a)
    assert [(c.descripcion, c.origen) for c in vista] == [("corredor", "ARCHIVO")]


def test_carga_de_bolsa_no_altera_copia_del_corredor(entorno):
    _cargar(entorno, entorno.usuario_a, [fila_archivo(descripcion="corredor")], entorno.corredor_a)
    _cargar(entorno, entorno.admin, [fila_archivo(descripcion="bolsa v1")], None)
    _, resumen = _cargar(entorno, entorno.admin, [fila_archivo(descripcion="bolsa v2")], None)
    assert resumen["actualizadas"] == 1
    assert [c.descripcion for c in entorno.calificaciones.buscar(entorno.usuario_a)] == ["corredor"]
    assert [c.descripcion for c in entorno.calificaciones.buscar(entorno.usuario_b)] == ["bolsa v2"]


def test_origen_deducido(entorno):
    _cargar(entorno, entorno.admin, [fila_archivo()], None)
    _cargar(entorno, entorno.usuario_a, [fila_archivo()], entorno.corredor_a)
    _cargar(entorno, entorno.usuario_b, [fila_archivo()], entorno.corredor_b, tipo="PDF")
    origenes = {c.corredor_id: c.origen for c in entorno.calificaciones.buscar(entorno.admin)}
    assert origenes == {None: "BOLSA", entorno.corredor_a: "ARCHIVO", entorno.corredor_b: "PDF"}


def test_corredor_no_puede_cargar_en_bolsa_ni_consulta_cargar(entorno):
    resultado = entorno.carga.previsualizar([fila_archivo()], None)
    with pytest.raises(PermisoDenegado):
        entorno.carga.confirmar(entorno.usuario_a, resultado, "ARCHIVO")
    resultado = entorno.carga.previsualizar([fila_archivo()], entorno.corredor_a)
    with pytest.raises(PermisoDenegado):
        entorno.carga.confirmar(entorno.consulta_a, resultado, "ARCHIVO")


def test_sin_filas_validas_falla(entorno):
    resultado = entorno.carga.previsualizar([fila_archivo(secuencia="1")], entorno.corredor_a)
    with pytest.raises(ErrorNegocio):
        entorno.carga.confirmar(entorno.usuario_a, resultado, "ARCHIVO")


def test_inyeccion_sql_se_guarda_como_texto(entorno):
    _cargar(entorno, entorno.usuario_a, [fila_archivo(instrumento="' OR 1=1 --")], entorno.corredor_a)
    lista = entorno.calificaciones.buscar(entorno.usuario_a)
    assert [c.instrumento for c in lista] == ["' OR 1=1 --"]
    assert entorno.calificaciones.buscar(entorno.usuario_b) == []
    assert entorno.con.execute("SELECT COUNT(*) FROM calificacion").fetchone()[0] == 1
