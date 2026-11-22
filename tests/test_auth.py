import pytest

from servicios.auth import (
    NO_ELEGIDO, corredor_efectivo, generar_hash, puede, requiere_permiso, requiere_rol,
    verificar_ambito, verificar_clave,
)
from servicios.errores import CredencialesInvalidas, PermisoDenegado, ValidacionError
from tests.conftest import CLAVE


def test_hash_y_verificacion():
    hash_clave, sal = generar_hash("secreta123", 1000)
    assert hash_clave.startswith("1000$") and "secreta123" not in hash_clave
    assert verificar_clave("secreta123", hash_clave, sal)
    assert not verificar_clave("otra", hash_clave, sal)
    otro_hash, otra_sal = generar_hash("secreta123", 1000)
    assert otra_sal != sal and otro_hash != hash_clave  # sal aleatoria


def test_inicio_de_sesion_correcto_registra_login_ok(entorno):
    usuario = entorno.auth.iniciar_sesion("ana", CLAVE)
    assert usuario.rol == "corredor" and usuario.corredor_id == entorno.corredor_a
    assert len(entorno.acciones("LOGIN_OK")) == 1


def test_clave_incorrecta_y_usuario_inexistente_mismo_mensaje(entorno):
    with pytest.raises(CredencialesInvalidas) as e1:
        entorno.auth.iniciar_sesion("ana", "incorrecta")
    with pytest.raises(CredencialesInvalidas) as e2:
        entorno.auth.iniciar_sesion("nadie", "incorrecta")
    assert str(e1.value) == str(e2.value)
    fallidos = entorno.acciones("LOGIN_FALLIDO")
    assert len(fallidos) == 2
    # La clave nunca se guarda en la auditoría.
    assert all("incorrecta" != v for r in fallidos for v in r["detalle"].values())


def test_usuario_inactivo_falla_y_registra(entorno):
    entorno.con.execute("UPDATE usuario SET activo = 0 WHERE nombre = 'ana'")
    with pytest.raises(CredencialesInvalidas):
        entorno.auth.iniciar_sesion("ana", CLAVE)
    assert entorno.acciones("LOGIN_FALLIDO")[-1]["detalle"]["motivo"] == "usuario inactivo"


def test_permisos_por_rol(entorno):
    for accion in ("ver", "crear", "modificar", "eliminar", "cargar", "exportar"):
        assert puede(entorno.admin, accion)
        assert puede(entorno.usuario_a, accion)
    assert puede(entorno.consulta_a, "ver") and puede(entorno.consulta_a, "exportar")
    for accion in ("crear", "modificar", "eliminar", "cargar"):
        assert not puede(entorno.consulta_a, accion)
        with pytest.raises(PermisoDenegado):
            requiere_permiso(entorno.consulta_a, accion)
    requiere_rol(entorno.admin, "admin")
    with pytest.raises(PermisoDenegado):
        requiere_rol(entorno.usuario_a, "admin")


def test_admin_sin_corredor_elegido_falla(entorno):
    with pytest.raises(ValidacionError):
        corredor_efectivo(entorno.admin, NO_ELEGIDO)
    assert corredor_efectivo(entorno.admin, None) is None
    assert corredor_efectivo(entorno.admin, entorno.corredor_b) == entorno.corredor_b
    # Para corredor se ignora lo elegido.
    assert corredor_efectivo(entorno.usuario_a, entorno.corredor_b) == entorno.corredor_a


def test_corredor_no_opera_sobre_bolsa_ni_otro_corredor(entorno):
    with pytest.raises(PermisoDenegado):
        verificar_ambito(entorno.usuario_a, None)
    with pytest.raises(PermisoDenegado):
        verificar_ambito(entorno.usuario_a, entorno.corredor_b)
    verificar_ambito(entorno.usuario_a, entorno.corredor_a)
    verificar_ambito(entorno.admin, None)


def test_crear_usuario_valida_datos(entorno):
    with pytest.raises(ValidacionError):
        entorno.auth.crear_usuario("x", "corta", "corredor", entorno.corredor_a)
    with pytest.raises(ValidacionError):
        entorno.auth.crear_usuario("x", CLAVE, "corredor", None)
    with pytest.raises(ValidacionError):
        entorno.auth.crear_usuario("ana", CLAVE, "corredor", entorno.corredor_a)
