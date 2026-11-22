"""Pruebas de impacto del HDU (hoja "4. Flujo de proceso") que no requieren archivos."""

from dataclasses import replace
from decimal import Decimal

import pytest

from servicios.errores import ErrorNegocio, PermisoDenegado, ValidacionError
from tests.conftest import FACTORES_HDU, calificacion_ejemplo


def _crear_bolsa(entorno, **cambios):
    return entorno.calificaciones.crear(entorno.admin, calificacion_ejemplo(**cambios), corredor=None)


# Prueba 1: ingresar o modificar por monto.
def test_ingresar_por_monto_queda_en_el_mantenedor(entorno):
    creada = entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    assert creada.origen == "MANUAL" and creada.corredor_id == entorno.corredor_a
    lista = entorno.calificaciones.buscar(entorno.usuario_a, ejercicio=2023)
    assert [c.id for c in lista] == [creada.id]
    guardada = entorno.calificaciones.obtener(entorno.usuario_a, creada.id)
    assert {c: guardada.factores[c] for c in FACTORES_HDU} == FACTORES_HDU
    assert guardada.montos[8] == 192_770_580


def test_modificar_por_monto(entorno):
    creada = entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    nueva = replace(creada, montos={8: 1, 9: 1}, factores={})
    modificada = entorno.calificaciones.modificar(entorno.usuario_a, creada.id, nueva)
    guardada = entorno.calificaciones.obtener(entorno.usuario_a, modificada.id)
    assert guardada.factores == {8: Decimal("0.5"), 9: Decimal("0.5")}
    assert guardada.creado_en == creada.creado_en
    assert guardada.modificado_en > creada.modificado_en


# Prueba 2: ingresar o modificar por factor.
def test_ingresar_y_modificar_por_factor(entorno):
    creada = entorno.calificaciones.crear(
        entorno.usuario_a, calificacion_ejemplo(montos={}, factores=dict(FACTORES_HDU)))
    nueva = replace(creada, factores={8: Decimal("0.6"), 9: Decimal("0.4")})
    entorno.calificaciones.modificar(entorno.usuario_a, creada.id, nueva)
    guardada = entorno.calificaciones.obtener(entorno.usuario_a, creada.id)
    assert guardada.factores == {8: Decimal("0.6"), 9: Decimal("0.4")}


# Prueba 3: instrumento no inscrito (texto libre).
def test_instrumento_no_inscrito(entorno):
    creada = entorno.calificaciones.crear(entorno.usuario_a,
                                          calificacion_ejemplo(instrumento="Instrumento Nuevo SpA"))
    assert creada.instrumento == "INSTRUMENTO NUEVO SPA"
    assert entorno.calificaciones.buscar(entorno.usuario_a)[0].id == creada.id


# Prueba 6: la información queda local para ese corredor.
def test_aislamiento_entre_corredores(entorno):
    creada = entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    assert entorno.calificaciones.buscar(entorno.usuario_b) == []
    with pytest.raises(PermisoDenegado):
        entorno.calificaciones.obtener(entorno.usuario_b, creada.id)
    with pytest.raises(PermisoDenegado):
        entorno.calificaciones.modificar(entorno.usuario_b, creada.id, creada)
    with pytest.raises(PermisoDenegado):
        entorno.calificaciones.eliminar(entorno.usuario_b, creada.id)
    # El mismo instrumento en otro corredor es una calificación distinta.
    otra = entorno.calificaciones.crear(entorno.usuario_b, calificacion_ejemplo())
    assert otra.id != creada.id


# Prueba 7: suma de factores 8 a 19 ≤ 1.
def test_suma_de_factores_mayor_que_uno_se_rechaza(entorno):
    with pytest.raises(ValidacionError, match="no puede ser mayor que 1"):
        entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo(
            montos={}, factores={8: Decimal("0.50000001"), 9: Decimal("0.5")}))
    assert entorno.calificaciones.buscar(entorno.usuario_a) == []


# Prueba 8: no se altera la información de bolsa.
def test_corredor_modifica_bolsa_crea_su_copia(entorno):
    bolsa = _crear_bolsa(entorno)
    assert bolsa.origen == "BOLSA" and bolsa.corredor_id is None
    antes = dict(entorno.con.execute("SELECT * FROM calificacion WHERE id = ?", (bolsa.id,)).fetchone())
    detalle_antes = entorno.repo_calificaciones.obtener_detalle(bolsa.id)

    vista = entorno.calificaciones.obtener(entorno.usuario_a, bolsa.id)
    copia = entorno.calificaciones.modificar(entorno.usuario_a, bolsa.id,
                                             replace(vista, descripcion="ajuste del corredor"))

    assert copia.id != bolsa.id and copia.origen == "MANUAL" and copia.corredor_id == entorno.corredor_a
    despues = dict(entorno.con.execute("SELECT * FROM calificacion WHERE id = ?", (bolsa.id,)).fetchone())
    assert despues == antes
    assert entorno.repo_calificaciones.obtener_detalle(bolsa.id) == detalle_antes
    # Copia completa: incluye el detalle de columnas.
    assert entorno.repo_calificaciones.obtener_detalle(copia.id) == detalle_antes

    vista_a = entorno.calificaciones.buscar(entorno.usuario_a)
    assert [(c.id, c.descripcion) for c in vista_a] == [(copia.id, "ajuste del corredor")]
    assert [c.id for c in entorno.calificaciones.buscar(entorno.usuario_b)] == [bolsa.id]
    insercion = entorno.acciones("INSERT")[-1]
    assert insercion["detalle"]["copia_de_bolsa"] == bolsa.id


def test_corredor_no_elimina_bolsa_y_al_borrar_su_copia_ve_bolsa(entorno):
    bolsa = _crear_bolsa(entorno)
    with pytest.raises(PermisoDenegado):
        entorno.calificaciones.eliminar(entorno.usuario_a, bolsa.id)
    copia = entorno.calificaciones.modificar(entorno.usuario_a, bolsa.id,
                                             entorno.calificaciones.obtener(entorno.usuario_a, bolsa.id))
    entorno.calificaciones.eliminar(entorno.usuario_a, copia.id)
    assert [c.id for c in entorno.calificaciones.buscar(entorno.usuario_a)] == [bolsa.id]


def test_corredor_crea_sobre_llave_de_bolsa_sin_alterarla(entorno):
    bolsa = _crear_bolsa(entorno)
    propia = entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo(descripcion="propia"))
    assert propia.id != bolsa.id
    assert entorno.repo_calificaciones.obtener_por_id(bolsa.id)["descripcion"] is None


def test_origen_deducido_en_crear(entorno):
    assert entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo()).origen == "MANUAL"
    assert _crear_bolsa(entorno).origen == "BOLSA"
    admin_en_corredor = entorno.calificaciones.crear(
        entorno.admin, calificacion_ejemplo(secuencia=20_000), corredor=entorno.corredor_b)
    assert admin_en_corredor.origen == "MANUAL" and admin_en_corredor.corredor_id == entorno.corredor_b
    # El origen que traiga la entidad se ignora.
    forzada = entorno.calificaciones.crear(entorno.usuario_a,
                                           calificacion_ejemplo(secuencia=30_000, origen="BOLSA"))
    assert forzada.origen == "MANUAL"


def test_admin_debe_elegir_ambito(entorno):
    with pytest.raises(ValidacionError):
        entorno.calificaciones.crear(entorno.admin, calificacion_ejemplo())


def test_consulta_no_puede_crear(entorno):
    with pytest.raises(PermisoDenegado):
        entorno.calificaciones.crear(entorno.consulta_a, calificacion_ejemplo())


def test_crear_llave_duplicada_falla(entorno):
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    with pytest.raises(ErrorNegocio, match="Modificar"):
        entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo(instrumento="COPEC "))


def test_cambiar_la_llave_en_modificar_falla(entorno):
    creada = entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    for cambio in ({"ejercicio": 2022}, {"mercado": "CFI"}, {"instrumento": "Otro"},
                   {"secuencia": 99_999}):
        with pytest.raises(ValidacionError, match="elimine"):
            entorno.calificaciones.modificar(entorno.usuario_a, creada.id, replace(creada, **cambio))


def test_auditoria_de_cada_operacion(entorno):
    creada = entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    entorno.calificaciones.modificar(entorno.usuario_a, creada.id, replace(creada, descripcion="nueva"))
    entorno.calificaciones.eliminar(entorno.usuario_a, creada.id)

    insercion, = entorno.acciones("INSERT")[-1:]
    assert insercion["registro_id"] == creada.id and insercion["usuario_id"] == entorno.usuario_a.id
    assert insercion["detalle"]["nuevo"]["factores"]["8"] == "0.52277431"
    actualizacion, = entorno.acciones("UPDATE")
    assert actualizacion["detalle"]["cambios"] == {"descripcion": [None, "nueva"]}
    eliminacion, = entorno.acciones("DELETE")
    assert eliminacion["detalle"]["llave"]["instrumento"] == "COPEC"
    # El registro sobrevive a la calificación eliminada.
    assert entorno.repo_calificaciones.obtener_por_id(creada.id) is None


def test_busqueda_de_ejercicio_anterior(entorno):
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo(ejercicio=2021))
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo(ejercicio=2023))
    anteriores = entorno.calificaciones.buscar(entorno.usuario_a, ejercicio=2021)
    assert [c.ejercicio for c in anteriores] == [2021]
    assert len(entorno.calificaciones.buscar(entorno.usuario_a)) == 2


def test_filtros_del_admin(entorno):
    _crear_bolsa(entorno)
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    assert len(entorno.calificaciones.buscar(entorno.admin)) == 2
    assert len(entorno.calificaciones.buscar(entorno.admin, corredor=None)) == 1
    assert len(entorno.calificaciones.buscar(entorno.admin, corredor=entorno.corredor_b)) == 0
    assert len(entorno.calificaciones.buscar(entorno.admin, origen="BOLSA")) == 1


def test_operacion_fallida_no_deja_registro_ni_auditoria(entorno):
    antes = len(entorno.acciones())
    with pytest.raises(ValidacionError):
        entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo(secuencia=9_999))
    assert len(entorno.acciones()) == antes
