"""Pantalla de inicio de sesión."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QLineEdit, QPushButton, QVBoxLayout

from servicios.auth import ServicioAuth
from servicios.errores import CredencialesInvalidas
from ui.comun import etiqueta_error, fila_botones, mostrar_error


class DialogoLogin(QDialog):
    def __init__(self, servicio_auth: ServicioAuth, padre=None):
        super().__init__(padre)
        self.servicio_auth = servicio_auth
        self.usuario = None
        self.setWindowTitle("NUAM - Iniciar sesión")
        self.setMinimumWidth(340)

        self.nombre = QLineEdit()
        self.clave = QLineEdit()
        self.clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.error = etiqueta_error()

        formulario = QFormLayout()
        formulario.addRow("Usuario:", self.nombre)
        formulario.addRow("Contraseña:", self.clave)

        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.ingresar = QPushButton("Ingresar")
        self.ingresar.clicked.connect(self._ingresar)

        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addWidget(self.error)
        diseno.addLayout(fila_botones(cancelar, self.ingresar))

    def _ingresar(self) -> None:
        if not self.nombre.text().strip() or not self.clave.text():
            self._mostrar_error("Ingrese usuario y contraseña.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.usuario = self.servicio_auth.iniciar_sesion(self.nombre.text(), self.clave.text())
        except CredencialesInvalidas as error:
            self._mostrar_error(str(error))
            self.clave.clear()
            self.clave.setFocus()
            return
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, error)
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.accept()

    def _mostrar_error(self, mensaje: str) -> None:
        self.error.setText(mensaje)
        self.error.show()
