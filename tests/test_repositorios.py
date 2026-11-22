import sqlite3

import pytest

from datos import conexion as modulo_conexion
from datos.conexion import crear_conexion, verificar_version_sqlite
from datos.repositorios import RepositorioAuditoria, RepositorioCalificaciones, RepositorioUsuarios


@pytest.fixture
def con():
    conexion = crear_conexion(":memory:")
    yield conexion
    conexion.close()


@pytest.fixture
def corredores(con):
    repo = RepositorioUsuarios(con)
    with con:
        return repo.crear_corredor("Corredor A"), repo.crear_corredor("Corredor B")


def _datos(corredor_id, origen="MANUAL", instrumento="COPEC", secuencia=123123,
           creado="2024-01-01T10:00:00", modificado="2024-01-01T10:00:00", descripcion=None):
    # Fila de ejemplo de la hoja "3.1 Archivo de carga" del HDU.
    return {
        "corredor_id": corredor_id, "ejercicio": 2023, "mercado": "ACN",
        "instrumento": instrumento, "fecha_pago": "2023-12-12", "secuencia": secuencia,
        "numero_dividendo": 123456, "tipo_sociedad": "A", "valor_historico": None,
        "descripcion": descripcion, "origen": origen, "creado_en": creado,
        "modificado_en": modificado,
    }


DETALLE = {8: (192770580, "0.52277431")}  # HDU, hoja "3.2 Homologacion columnas"


def test_version_sqlite_minima(monkeypatch):
    verificar_version_sqlite("3.35.0")
    with pytest.raises(RuntimeError, match="3.35.0"):
        verificar_version_sqlite("3.34.1")
    monkeypatch.setattr(modulo_conexion.sqlite3, "sqlite_version", "3.30.0")
    with pytest.raises(RuntimeError, match="3.30.0"):
        crear_conexion(":memory:")


def test_upsert_actualiza_sin_duplicar_ni_cambiar_creado_en(con, corredores):
    repo = RepositorioCalificaciones(con)
    a, _ = corredores
    with con:
        id1 = repo.guardar(_datos(a), DETALLE)
        id2 = repo.guardar(
            _datos(a, creado="2025-05-05T00:00:00", modificado="2025-05-05T00:00:00",
                   descripcion="cambio"),
            {9: (64161878, "0.17400052")},
        )
    assert id1 == id2
    fila = repo.obtener_por_id(id1)
    assert fila["creado_en"] == "2024-01-01T10:00:00"
    assert fila["modificado_en"] == "2025-05-05T00:00:00"
    assert fila["descripcion"] == "cambio"
    assert repo.obtener_detalle(id1) == {9: (64161878, "0.17400052")}
    assert len(repo.buscar_todas()) == 1


def test_aislamiento_entre_corredores(con, corredores):
    repo = RepositorioCalificaciones(con)
    a, b = corredores
    with con:
        repo.guardar(_datos(a), DETALLE)
    assert len(repo.buscar_por_ambito(a)) == 1
    assert repo.buscar_por_ambito(b) == []
    assert repo.buscar_vista_corredor(b) == []
    assert repo.obtener_por_llave(b, 2023, "ACN", "COPEC", 123123) is None


def test_bolsa_y_corredor_con_misma_llave_conviven(con, corredores):
    repo = RepositorioCalificaciones(con)
    a, _ = corredores
    with con:
        id_bolsa = repo.guardar(_datos(None, origen="BOLSA"), DETALLE)
        id_corredor = repo.guardar(_datos(a), DETALLE)
    assert id_bolsa != id_corredor
    assert repo.obtener_por_llave(None, 2023, "ACN", "COPEC", 123123)["id"] == id_bolsa
    assert repo.obtener_por_llave(a, 2023, "ACN", "COPEC", 123123)["id"] == id_corredor


def test_dos_de_bolsa_con_misma_llave_hacen_upsert(con):
    repo = RepositorioCalificaciones(con)
    with con:
        id1 = repo.guardar(_datos(None, origen="BOLSA"), DETALLE)
        id2 = repo.guardar(_datos(None, origen="BOLSA", descripcion="x"), DETALLE)
    assert id1 == id2
    assert len(repo.buscar_por_ambito(None)) == 1


def test_vista_corredor_muestra_su_copia_en_vez_de_bolsa(con, corredores):
    repo = RepositorioCalificaciones(con)
    a, b = corredores
    with con:
        id_bolsa = repo.guardar(_datos(None, origen="BOLSA"), DETALLE)
        repo.guardar(_datos(None, origen="BOLSA", secuencia=20000), DETALLE)
        id_copia = repo.guardar(_datos(a), DETALLE)
    vista_a = {f["id"] for f in repo.buscar_vista_corredor(a)}
    vista_b = {f["id"] for f in repo.buscar_vista_corredor(b)}
    assert id_copia in vista_a and id_bolsa not in vista_a and len(vista_a) == 2
    assert id_bolsa in vista_b and len(vista_b) == 2


def test_filtros_de_busqueda(con, corredores):
    repo = RepositorioCalificaciones(con)
    a, _ = corredores
    with con:
        repo.guardar(_datos(a), DETALLE)
    assert len(repo.buscar_vista_corredor(a, {"ejercicio": 2023, "mercado": "ACN"})) == 1
    assert repo.buscar_vista_corredor(a, {"ejercicio": 2022}) == []
    assert repo.buscar_vista_corredor(a, {"origen": "BOLSA"}) == []


def test_check_origen_bolsa_corresponde_a_corredor_nulo(con, corredores):
    repo = RepositorioCalificaciones(con)
    a, _ = corredores
    with pytest.raises(sqlite3.IntegrityError):
        with con:
            repo.guardar(_datos(None, origen="MANUAL"), DETALLE)
    with pytest.raises(sqlite3.IntegrityError):
        with con:
            repo.guardar(_datos(a, origen="BOLSA"), DETALLE)


def test_log_auditoria_es_inmutable(con):
    repo = RepositorioAuditoria(con)
    with con:
        repo.registrar("2024-01-01T00:00:00", None, "LOGIN_OK")
    with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
        with con:
            con.execute("UPDATE log_auditoria SET accion = 'X'")
    with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
        with con:
            con.execute("DELETE FROM log_auditoria")
    assert len(repo.listar()) == 1


def test_eliminar_calificacion_elimina_detalle(con, corredores):
    repo = RepositorioCalificaciones(con)
    a, _ = corredores
    with con:
        calificacion_id = repo.guardar(_datos(a), DETALLE)
        repo.eliminar(calificacion_id)
    restantes = con.execute(
        "SELECT COUNT(*) FROM calificacion_detalle WHERE calificacion_id = ?", (calificacion_id,)
    ).fetchone()[0]
    assert restantes == 0


def test_usuario_no_admin_requiere_corredor(con):
    repo = RepositorioUsuarios(con)
    with pytest.raises(sqlite3.IntegrityError):
        with con:
            repo.crear("pepe", "h", "s", "corredor", None)
