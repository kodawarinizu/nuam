"""Fixtures comunes: base en memoria, servicios y usuarios de cada rol."""

from decimal import Decimal
from itertools import count

import pytest

from datos.conexion import crear_conexion
from datos.repositorios import RepositorioAuditoria, RepositorioCalificaciones, RepositorioUsuarios
from servicios.auth import ServicioAuth
from servicios.calificaciones import ServicioCalificaciones
from servicios.carga_masiva import ServicioCargaMasiva
from servicios.entidades import Calificacion

ITERACIONES_PRUEBA = 1_000  # rápido en pruebas; producción usa config.PBKDF2_ITERACIONES
CLAVE = "clave-segura-1"


class Reloj:
    """Reloj falso que avanza un segundo por llamada (para distinguir creado/modificado)."""

    def __init__(self):
        self._segundos = count()

    def __call__(self):
        s = next(self._segundos)
        return f"2024-01-01T10:{s // 60:02d}:{s % 60:02d}"


class Entorno:
    def __init__(self):
        self.con = crear_conexion(":memory:")
        self.reloj = Reloj()
        self.repo_usuarios = RepositorioUsuarios(self.con)
        self.repo_calificaciones = RepositorioCalificaciones(self.con)
        self.repo_auditoria = RepositorioAuditoria(self.con)
        self.auth = ServicioAuth(self.con, self.repo_usuarios, self.repo_auditoria,
                                 ITERACIONES_PRUEBA, self.reloj)
        self.calificaciones = ServicioCalificaciones(self.con, self.repo_calificaciones,
                                                     self.repo_auditoria, self.reloj)
        self.carga = ServicioCargaMasiva(self.con, self.repo_calificaciones,
                                         self.repo_auditoria, self.reloj)
        self.corredor_a = self.auth.obtener_o_crear_corredor("Corredor A")
        self.corredor_b = self.auth.obtener_o_crear_corredor("Corredor B")
        self.admin = self.auth.crear_usuario("admin", CLAVE, "admin", None)
        self.usuario_a = self.auth.crear_usuario("ana", CLAVE, "corredor", self.corredor_a)
        self.usuario_b = self.auth.crear_usuario("beto", CLAVE, "corredor", self.corredor_b)
        self.consulta_a = self.auth.crear_usuario("carla", CLAVE, "consulta", self.corredor_a)

    def acciones(self, accion: str | None = None) -> list[dict]:
        registros = self.repo_auditoria.listar()
        return [r for r in registros if accion is None or r["accion"] == accion]


@pytest.fixture
def entorno():
    e = Entorno()
    yield e
    e.con.close()


# HDU, hoja "3.2 Homologacion columnas": montos y factores esperados.
MONTOS_HDU = {8: 192_770_580, 9: 64_161_878, 10: 0, 11: 111_812_860, 25: 71_298_705, 30: 15_837_333}
FACTORES_HDU = {
    8: Decimal("0.52277431"), 9: Decimal("0.17400052"), 10: Decimal("0.00000000"),
    11: Decimal("0.30322517"), 25: Decimal("0.19335488"), 30: Decimal("0.04294924"),
}


def calificacion_ejemplo(**cambios) -> Calificacion:
    """Datos básicos de la fila de ejemplo del HDU, hoja "3.1 Archivo de carga"
    (2023; ACN; Copec; 12-12-2023; secuencia 123123; dividendo 123456; tipo A),
    con los montos de la hoja "3.2 Homologacion columnas"."""
    datos = dict(ejercicio=2023, mercado="ACN", instrumento="Copec", fecha_pago="2023-12-12",
                 secuencia=123123, numero_dividendo=123456, tipo_sociedad="A",
                 montos=dict(MONTOS_HDU))
    datos.update(cambios)
    return Calificacion(**datos)


def fila_archivo(**cambios) -> dict:
    """Fila cruda como la entrega un lector (hoja "3.1 Archivo de carga" del HDU),
    con los factores de la hoja "3.2 Homologacion columnas" en formato chileno."""
    fila = {"ejercicio": "2023", "mercado": "ACN", "instrumento": "Copec",
            "fecha_pago": "12-12-2023", "secuencia": "123123", "numero_dividendo": "123456",
            "tipo_sociedad": "A",
            "factor_8": "0,52277431", "factor_9": "0,17400052", "factor_10": "0,00000000",
            "factor_11": "0,30322517"}
    fila.update(cambios)
    return fila
