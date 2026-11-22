"""Componentes compartidos por las pantallas: errores, botones y formularios."""

import functools
import logging
from datetime import date

from PySide6.QtCore import QDate, QRegularExpression, Qt, Signal
from PySide6.QtGui import QColor, QPalette, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QWidget,
)

import config
from servicios.auth import NO_ELEGIDO
from servicios.calificaciones import entero_a_texto
from servicios.entidades import Calificacion, Usuario
from servicios.errores import ErrorNegocio, ValidacionError

log = logging.getLogger("ui")

MENSAJE_GENERICO = ("Ocurrió un error inesperado. Intente nuevamente; "
                    "si el problema persiste, el detalle quedó registrado en el log técnico.")
COLOR_ERROR = QColor(255, 214, 214)
COLOR_FALTANTE = QColor(255, 243, 205)
COLOR_TEXTO_ERROR = QColor(176, 0, 32)

# Valores del selector de ámbito del admin (en el combo no se puede guardar None sin ambigüedad).
_AMBITO_NO_ELEGIDO, _AMBITO_BOLSA = -1, 0


# ---------- errores y botones ----------

def mostrar_error(padre, error: Exception) -> None:
    """Errores de negocio: mensaje claro. Inesperados: al log técnico y mensaje genérico."""
    if isinstance(error, ErrorNegocio):
        QMessageBox.warning(padre, "No se pudo completar la acción", str(error))
    else:
        log.error("Error inesperado en la interfaz", exc_info=error)
        QMessageBox.critical(padre, "Error inesperado", MENSAJE_GENERICO)


def protegido(metodo):
    """Decora un slot: cualquier excepción se muestra con mostrar_error.

    Ignora los argumentos que agrega Qt (por ejemplo `checked` de clicked).
    """
    @functools.wraps(metodo)
    def envoltura(self, *_):
        try:
            return metodo(self)
        except Exception as error:  # noqa: BLE001 — límite de la interfaz
            mostrar_error(self, error)
    return envoltura


def fila_botones(cancelar: QPushButton, principal: QPushButton, *izquierda: QWidget) -> QHBoxLayout:
    """Orden consistente: extras a la izquierda, luego Cancelar y la acción principal a la derecha."""
    fila = QHBoxLayout()
    for widget in izquierda:
        fila.addWidget(widget)
    fila.addStretch()
    fila.addWidget(cancelar)
    fila.addWidget(principal)
    principal.setDefault(True)
    return fila


def marcar_etiqueta(etiqueta: QLabel, con_error: bool) -> None:
    if con_error:
        paleta = etiqueta.palette()
        paleta.setColor(QPalette.ColorRole.WindowText, COLOR_TEXTO_ERROR)
        etiqueta.setPalette(paleta)
    else:
        etiqueta.setPalette(QPalette())


def etiqueta_error() -> QLabel:
    """Etiqueta para el mensaje de validación en línea."""
    etiqueta = QLabel()
    etiqueta.setWordWrap(True)
    marcar_etiqueta(etiqueta, True)
    etiqueta.hide()
    return etiqueta


def combo_ambito(corredores: list[dict], incluir_todos: bool = False) -> QComboBox:
    """Selector del admin: "Todos" (opcional), "Bolsa" y cada corredor."""
    combo = QComboBox()
    if incluir_todos:
        combo.addItem("Todos", _AMBITO_NO_ELEGIDO)
    else:
        combo.addItem("Seleccione…", _AMBITO_NO_ELEGIDO)
    combo.addItem("Bolsa", _AMBITO_BOLSA)
    for corredor in corredores:
        combo.addItem(corredor["nombre"], corredor["id"])
    return combo


def ambito_de_combo(combo: QComboBox):
    """NO_ELEGIDO (o "Todos"), None (bolsa) o el id del corredor."""
    valor = combo.currentData()
    if valor == _AMBITO_NO_ELEGIDO:
        return NO_ELEGIDO
    if valor == _AMBITO_BOLSA:
        return None
    return valor


def seleccionar_ambito(combo: QComboBox, ambito) -> None:
    if ambito is NO_ELEGIDO:
        dato = _AMBITO_NO_ELEGIDO
    elif ambito is None:
        dato = _AMBITO_BOLSA
    else:
        dato = ambito
    indice = combo.findData(dato)
    combo.setCurrentIndex(max(indice, 0))


# ---------- formulario de datos básicos ----------

class FormularioDatosBasicos(QWidget):
    """Datos básicos de una calificación (diálogo de ingreso y carga de PDF)."""

    cambiado = Signal()

    def __init__(self, usuario: Usuario, corredores: list[dict], mostrar_ambito: bool = True,
                 padre=None):
        super().__init__(padre)
        self._etiquetas: dict[str, QLabel] = {}
        self._widgets: dict[str, QWidget] = {}
        self._formulario = QFormLayout(self)

        self.ambito = None
        if usuario.rol == "admin" and mostrar_ambito:
            self.ambito = combo_ambito(corredores)
            self.ambito.currentIndexChanged.connect(self.cambiado)
            self._agregar("corredor", "Corredor o Bolsa:", self.ambito)

        self.ejercicio = QSpinBox()
        self.ejercicio.setRange(config.EJERCICIO_MIN, config.EJERCICIO_MAX)
        self.ejercicio.setValue(date.today().year)
        self.ejercicio.valueChanged.connect(self.cambiado)
        self._agregar("ejercicio", "Ejercicio:", self.ejercicio)

        self.mercado = QComboBox()
        for codigo, nombre in config.MERCADOS.items():
            self.mercado.addItem(f"{codigo} - {nombre}", codigo)
        self.mercado.currentIndexChanged.connect(self.cambiado)
        self._agregar("mercado", "Mercado:", self.mercado)

        self.instrumento = QLineEdit()
        self.instrumento.setMaxLength(config.LARGO_MAX_INSTRUMENTO)
        self.instrumento.setPlaceholderText("Ej.: COPEC")
        self._agregar("instrumento", "Instrumento:", self.instrumento)

        self.fecha = QDateEdit(QDate.currentDate())
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd-MM-yyyy")
        self.fecha.dateChanged.connect(self.cambiado)
        self._agregar("fecha_pago", "Fecha de pago:", self.fecha)

        solo_digitos = QRegularExpressionValidator(QRegularExpression(r"\d{0,10}"), self)
        self.secuencia = QLineEdit()
        self.secuencia.setValidator(solo_digitos)
        self.secuencia.setPlaceholderText(
            f"Mayor que {entero_a_texto(config.SECUENCIA_MINIMA)}")
        self._agregar("secuencia", "Secuencia:", self.secuencia)

        self.dividendo = QLineEdit("0")
        self.dividendo.setValidator(solo_digitos)
        self._agregar("numero_dividendo", "Número de dividendo:", self.dividendo)

        self.tipo = QComboBox()
        self.tipo.addItem("(sin informar)", "")
        self.tipo.addItem("A - Abierta", "A")
        self.tipo.addItem("C - Cerrada", "C")
        self.tipo.currentIndexChanged.connect(self.cambiado)
        self._agregar("tipo_sociedad", "Tipo de sociedad:", self.tipo)

        self.valor_historico = QLineEdit()
        self.valor_historico.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"[\d.]{0,14}"), self))
        self._agregar("valor_historico", "Valor histórico:", self.valor_historico)

        self.descripcion = QLineEdit()
        self._agregar("descripcion", "Descripción:", self.descripcion)

        for campo in (self.instrumento, self.secuencia, self.dividendo, self.valor_historico,
                      self.descripcion):
            campo.textChanged.connect(self.cambiado)

    def _agregar(self, clave: str, texto: str, widget: QWidget) -> None:
        etiqueta = QLabel(texto)
        etiqueta.setBuddy(widget)
        self._formulario.addRow(etiqueta, widget)
        self._etiquetas[clave] = etiqueta
        self._widgets[clave] = widget

    def ambito_elegido(self):
        """Para el admin, lo elegido; para los demás no aplica (el servicio usa su corredor)."""
        return ambito_de_combo(self.ambito) if self.ambito is not None else NO_ELEGIDO

    def establecer_ambito(self, ambito) -> None:
        if self.ambito is not None:
            seleccionar_ambito(self.ambito, ambito)

    def establecer_mercado(self, codigo: str | None) -> None:
        indice = self.mercado.findData(codigo)
        if indice >= 0:
            self.mercado.setCurrentIndex(indice)

    def completos(self) -> bool:
        """Datos mínimos para intentar grabar o previsualizar."""
        ambito_ok = self.ambito is None or self.ambito_elegido() is not NO_ELEGIDO
        return ambito_ok and bool(self.instrumento.text().strip()) and bool(self.secuencia.text())

    def valores(self) -> dict:
        """Valores crudos con las claves canónicas (los convierte el servicio)."""
        return {
            "ejercicio": self.ejercicio.value(),
            "mercado": self.mercado.currentData(),
            "instrumento": self.instrumento.text(),
            "fecha_pago": self.fecha.date().toString("dd-MM-yyyy"),
            "secuencia": self.secuencia.text(),
            "numero_dividendo": self.dividendo.text() or "0",
            "tipo_sociedad": self.tipo.currentData(),
            "valor_historico": self.valor_historico.text(),
            "descripcion": self.descripcion.text(),
        }

    def cargar(self, c: Calificacion) -> None:
        self.establecer_ambito(c.corredor_id)
        self.ejercicio.setValue(c.ejercicio)
        self.establecer_mercado(c.mercado)
        self.instrumento.setText(c.instrumento)
        self.fecha.setDate(QDate.fromString(c.fecha_pago, "yyyy-MM-dd"))
        self.secuencia.setText(str(c.secuencia))
        self.dividendo.setText(str(c.numero_dividendo))
        self.tipo.setCurrentIndex(max(self.tipo.findData(c.tipo_sociedad or ""), 0))
        self.valor_historico.setText(entero_a_texto(c.valor_historico))
        self.descripcion.setText(c.descripcion or "")

    def bloquear_llave(self) -> None:
        """En modificar, la llave y el ámbito son de solo lectura."""
        for clave in ("corredor", "ejercicio", "mercado", "instrumento", "secuencia"):
            if clave in self._widgets:
                self._widgets[clave].setEnabled(False)
                self._widgets[clave].setToolTip(
                    "No se puede cambiar: para cambiarlo, elimine la calificación y créela de nuevo.")

    def marcar(self, campo: str | None, mensaje: str) -> bool:
        """Marca la etiqueta del campo con error. Devuelve False si el campo no es de este formulario."""
        if campo not in self._etiquetas:
            return False
        marcar_etiqueta(self._etiquetas[campo], True)
        widget = self._widgets[campo]
        widget.setToolTip(mensaje)
        widget.setFocus()
        return True

    def limpiar_marcas(self) -> None:
        for clave, etiqueta in self._etiquetas.items():
            marcar_etiqueta(etiqueta, False)
            if self._widgets[clave].isEnabled():
                self._widgets[clave].setToolTip("")


# ---------- tabla de columnas 8 a 37 ----------

class TablaColumnas(QTableWidget):
    """Tabla editable: número de columna, nombre del HDU y un valor (monto o factor)."""

    cambiado = Signal()

    def __init__(self, columnas: range, titulo_valor: str, padre=None):
        super().__init__(len(columnas), 3, padre)
        self.columnas = list(columnas)
        self._fila_de = {col: i for i, col in enumerate(self.columnas)}
        self.setHorizontalHeaderLabels(["Col.", "Nombre (HDU)", titulo_valor])
        self.verticalHeader().hide()
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                             | QAbstractItemView.EditTrigger.EditKeyPressed
                             | QAbstractItemView.EditTrigger.AnyKeyPressed
                             | QAbstractItemView.EditTrigger.SelectedClicked)
        solo_lectura = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        for fila, columna in enumerate(self.columnas):
            numero = QTableWidgetItem(str(columna))
            numero.setFlags(solo_lectura)
            nombre = QTableWidgetItem(config.NOMBRES_COLUMNAS[columna])
            nombre.setFlags(solo_lectura)
            nombre.setToolTip(config.NOMBRES_COLUMNAS[columna])
            valor = QTableWidgetItem("")
            valor.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(fila, 0, numero)
            self.setItem(fila, 1, nombre)
            self.setItem(fila, 2, valor)
        cabecera = self.horizontalHeader()
        cabecera.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cabecera.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cabecera.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(2, 140)
        self.itemChanged.connect(lambda item: item.column() == 2 and self.cambiado.emit())

    def valores(self) -> dict[int, str]:
        return {col: self.item(self._fila_de[col], 2).text().strip() for col in self.columnas}

    def establecer(self, valores: dict[int, str]) -> None:
        """Reemplaza todos los valores (las columnas sin valor quedan vacías)."""
        self.blockSignals(True)
        for col in self.columnas:
            self.item(self._fila_de[col], 2).setText(valores.get(col, ""))
        self.blockSignals(False)
        self.cambiado.emit()

    def resaltar(self, columnas: set[int] | list[int], color: QColor | None) -> None:
        """Pinta el fondo de las filas indicadas (None restaura el fondo normal)."""
        for col in columnas:
            if col in self._fila_de:
                for c in range(3):
                    self.item(self._fila_de[col], c).setData(
                        Qt.ItemDataRole.BackgroundRole, color)

    def limpiar_resaltado(self) -> None:
        self.resaltar(self.columnas, None)

    def ir_a(self, columna: int) -> None:
        if columna in self._fila_de:
            self.setCurrentCell(self._fila_de[columna], 2)
            self.setFocus()


def campo_de_error(error: ValidacionError) -> tuple[str | None, int | None]:
    """("monto", 8), ("factor", 34) o (campo, None)."""
    campo = error.campo or ""
    for prefijo in ("monto", "factor"):
        if campo.startswith(prefijo + "_"):
            return prefijo, int(campo.split("_")[1])
    return campo or None, None

