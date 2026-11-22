"""Punto de entrada: python main.py"""

import logging
import sys

import ui  # noqa: F401  — debe ir antes de PySide6 (ver ui/__init__.py)
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import config
from datos.conexion import crear_conexion
from datos.repositorios import RepositorioAuditoria, RepositorioCalificaciones, RepositorioUsuarios
from infraestructura.logs import configurar_logging
from servicios.auth import ServicioAuth
from servicios.calificaciones import ServicioCalificaciones
from servicios.carga_masiva import ServicioCargaMasiva
from servicios.exportacion import ServicioExportacion
from ui.comun import MENSAJE_GENERICO
from ui.login import DialogoLogin
from ui.ventana_principal import VentanaPrincipal

log = logging.getLogger("main")


def _manejar_excepcion(tipo, valor, traza) -> None:
    """Errores no capturados: al log técnico y mensaje genérico (sin cerrar la aplicación)."""
    log.critical("Error no capturado", exc_info=(tipo, valor, traza))
    if QApplication.instance() is not None:
        QMessageBox.critical(None, "Error inesperado", MENSAJE_GENERICO)


def main() -> int:
    configurar_logging()
    sys.excepthook = _manejar_excepcion
    app = QApplication(sys.argv)
    app.setApplicationName("NUAM Calificaciones")

    try:
        conexion = crear_conexion(config.RUTA_BD)
    except RuntimeError as error:  # versión de SQLite insuficiente
        log.critical("No se pudo abrir la base: %s", error)
        QMessageBox.critical(None, "NUAM", str(error))
        return 1

    repo_usuarios = RepositorioUsuarios(conexion)
    repo_calificaciones = RepositorioCalificaciones(conexion)
    repo_auditoria = RepositorioAuditoria(conexion)
    auth = ServicioAuth(conexion, repo_usuarios, repo_auditoria)
    calificaciones = ServicioCalificaciones(conexion, repo_calificaciones, repo_auditoria)
    carga = ServicioCargaMasiva(conexion, repo_calificaciones, repo_auditoria)
    exportacion = ServicioExportacion(conexion, repo_calificaciones, repo_auditoria)

    if not auth.hay_usuarios():
        QMessageBox.information(None, "NUAM", "La base no tiene usuarios. Ejecute primero:\n\n"
                                              "python scripts/inicializar_bd.py init")
        return 1

    login = DialogoLogin(auth)
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0

    ventana = VentanaPrincipal(login.usuario, auth, calificaciones, carga, exportacion)
    ventana.show()
    log.info("Aplicación iniciada")
    codigo = app.exec()
    conexion.close()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
