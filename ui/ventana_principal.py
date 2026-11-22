"""Ventana principal: filtros, tabla de calificaciones y acciones."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QTableView, QVBoxLayout, QWidget,
)

import config
from servicios.auth import NO_ELEGIDO, ServicioAuth, puede
from servicios.calificaciones import TODOS, ServicioCalificaciones
from servicios.carga_masiva import ServicioCargaMasiva
from servicios.entidades import Calificacion, Usuario
from servicios.exportacion import ServicioExportacion
from ui.comun import ambito_de_combo, combo_ambito, protegido
from ui.dialogo_calificacion import DialogoCalificacion
from ui.dialogo_carga import DialogoCarga
from ui.modelo_tabla import ModeloCalificaciones

_TODOS_EJERCICIOS = config.EJERCICIO_MIN - 1  # valor especial del QSpinBox: "Todos"


class VentanaPrincipal(QMainWindow):
    def __init__(self, usuario: Usuario, auth: ServicioAuth, calificaciones: ServicioCalificaciones,
                 carga: ServicioCargaMasiva, exportacion: ServicioExportacion):
        super().__init__()
        self.usuario = usuario
        self.auth = auth
        self.servicio = calificaciones
        self.carga = carga
        self.exportacion = exportacion
        self.corredores = auth.listar_corredores(usuario)
        es_admin = usuario.rol == "admin"
        self.setWindowTitle(f"NUAM - Mantenedor de calificaciones tributarias ({usuario.nombre}, {usuario.rol})")
        self.resize(1100, 650)

        # ---- filtros ----
        self.filtro_mercado = QComboBox()
        self.filtro_mercado.addItem("Todos", None)
        for codigo, nombre in config.MERCADOS.items():
            self.filtro_mercado.addItem(f"{codigo} - {nombre}", codigo)
        self.filtro_origen = QComboBox()
        self.filtro_origen.addItem("Todos", None)
        for origen in config.ORIGENES:
            self.filtro_origen.addItem(origen, origen)
        self.filtro_ejercicio = QSpinBox()
        self.filtro_ejercicio.setRange(_TODOS_EJERCICIOS, config.EJERCICIO_MAX)
        self.filtro_ejercicio.setSpecialValueText("Todos")
        self.filtro_ejercicio.setValue(_TODOS_EJERCICIOS)
        self.filtro_ambito = combo_ambito(self.corredores, incluir_todos=True) if es_admin else None

        self.boton_buscar = QPushButton("Buscar")
        self.boton_buscar.setShortcut(QKeySequence("Ctrl+F"))
        self.boton_buscar.setToolTip("Buscar (Ctrl+F)")
        self.boton_buscar.clicked.connect(self.buscar)

        fila_filtros = QHBoxLayout()
        for texto, widget in (("Mercado:", self.filtro_mercado), ("Origen:", self.filtro_origen),
                              ("Ejercicio:", self.filtro_ejercicio)):
            etiqueta = QLabel(texto)
            etiqueta.setBuddy(widget)
            fila_filtros.addWidget(etiqueta)
            fila_filtros.addWidget(widget)
        if self.filtro_ambito is not None:
            fila_filtros.addWidget(QLabel("Corredor:"))
            fila_filtros.addWidget(self.filtro_ambito)
        fila_filtros.addStretch()
        fila_filtros.addWidget(self.boton_buscar)
        grupo_filtros = QGroupBox("Filtros")
        grupo_filtros.setLayout(fila_filtros)

        # ---- tabla ----
        nombres = {c["id"]: c["nombre"] for c in self.corredores} if es_admin else None
        self.modelo = ModeloCalificaciones(nombres)
        self.tabla = QTableView()
        self.tabla.setModel(self.modelo)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.verticalHeader().hide()
        self.tabla.doubleClicked.connect(self.modificar)
        self.tabla.selectionModel().selectionChanged.connect(self._actualizar_botones)

        # ---- acciones ----
        self.boton_ingresar = self._boton("Ingresar", "Ctrl+N", self.ingresar)
        self.boton_modificar = self._boton("Modificar", "Ctrl+E", self.modificar)
        self.boton_eliminar = self._boton("Eliminar", "Del", self.eliminar)
        self.boton_cargar = self._boton("Cargar archivo", "Ctrl+O", self.cargar_archivo)
        self.boton_pdf = self._boton("Cargar PDF", None, self.cargar_pdf)
        self.boton_exportar = self._boton("Exportar", None, self.exportar)
        fila_acciones = QHBoxLayout()
        for boton in (self.boton_cargar, self.boton_pdf, self.boton_exportar):
            fila_acciones.addWidget(boton)
        fila_acciones.addStretch()
        for boton in (self.boton_eliminar, self.boton_modificar, self.boton_ingresar):
            fila_acciones.addWidget(boton)

        central = QWidget()
        disposicion = QVBoxLayout(central)
        disposicion.addWidget(grupo_filtros)
        disposicion.addWidget(self.tabla, 1)
        disposicion.addLayout(fila_acciones)
        self.setCentralWidget(central)

        self._actualizar_botones()
        self.buscar()

    def _boton(self, texto: str, atajo: str | None, accion) -> QPushButton:
        boton = QPushButton(texto)
        if atajo:
            boton.setShortcut(QKeySequence(atajo))
            boton.setToolTip(f"{texto} ({QKeySequence(atajo).toString(QKeySequence.SequenceFormat.NativeText)})")
        boton.clicked.connect(accion)
        return boton

    # ---------- estado ----------

    def _seleccionada(self) -> Calificacion | None:
        filas = self.tabla.selectionModel().selectedRows()
        return self.modelo.calificacion(filas[0].row()) if filas else None

    def _actualizar_botones(self, *_) -> None:
        """Habilita según el rol (los permisos se verifican igual en los servicios)."""
        seleccionada = self._seleccionada()
        u = self.usuario
        self.boton_ingresar.setEnabled(puede(u, "crear"))
        self.boton_modificar.setEnabled(puede(u, "modificar") and seleccionada is not None)
        propia = seleccionada is not None and (
            u.rol == "admin" or seleccionada.corredor_id == u.corredor_id)
        self.boton_eliminar.setEnabled(puede(u, "eliminar") and propia)
        if seleccionada is not None and seleccionada.corredor_id is None and u.rol != "admin":
            self.boton_eliminar.setToolTip("Las calificaciones de bolsa no se pueden eliminar.")
        else:
            self.boton_eliminar.setToolTip("Eliminar (Supr)")
        self.boton_cargar.setEnabled(puede(u, "cargar"))
        self.boton_pdf.setEnabled(puede(u, "cargar"))
        self.boton_exportar.setEnabled(puede(u, "exportar"))

    def _informar(self, mensaje: str) -> None:
        self.statusBar().showMessage(mensaje, 10_000)

    def _ambito_filtro(self):
        """Ámbito del filtro del admin para precargar los diálogos (NO_ELEGIDO si es "Todos")."""
        return ambito_de_combo(self.filtro_ambito) if self.filtro_ambito is not None else NO_ELEGIDO

    # ---------- acciones ----------

    @protegido
    def buscar(self) -> None:
        ejercicio = self.filtro_ejercicio.value()
        corredor = TODOS
        if self.filtro_ambito is not None:
            ambito = ambito_de_combo(self.filtro_ambito)
            corredor = TODOS if ambito is NO_ELEGIDO else ambito
        resultados = self.servicio.buscar(
            self.usuario,
            ejercicio=None if ejercicio == _TODOS_EJERCICIOS else ejercicio,
            mercado=self.filtro_mercado.currentData(),
            origen=self.filtro_origen.currentData(),
            corredor=corredor,
        )
        self.modelo.establecer(resultados)
        self.tabla.resizeColumnsToContents()
        self._actualizar_botones()
        self._informar(f"{len(resultados)} calificaciones encontradas.")

    @protegido
    def ingresar(self) -> None:
        if not self.boton_ingresar.isEnabled():
            return
        dialogo = DialogoCalificacion(self.usuario, self.servicio, self.corredores,
                                      mercado_inicial=self.filtro_mercado.currentData(),
                                      ambito_inicial=self._ambito_filtro(), padre=self)
        if dialogo.exec() == DialogoCalificacion.DialogCode.Accepted:
            self.buscar()
            self._informar(f"Calificación de {dialogo.resultado.instrumento} creada.")

    @protegido
    def modificar(self) -> None:
        seleccionada = self._seleccionada()
        if seleccionada is None or not self.boton_modificar.isEnabled():
            return
        completa = self.servicio.obtener(self.usuario, seleccionada.id)
        dialogo = DialogoCalificacion(self.usuario, self.servicio, self.corredores,
                                      calificacion=completa, padre=self)
        if dialogo.exec() == DialogoCalificacion.DialogCode.Accepted:
            self.buscar()
            if dialogo.resultado.id != seleccionada.id:
                self._informar("Se creó su copia local; la calificación de bolsa no se modificó.")
            else:
                self._informar(f"Calificación de {dialogo.resultado.instrumento} modificada.")

    @protegido
    def eliminar(self) -> None:
        seleccionada = self._seleccionada()
        if seleccionada is None or not self.boton_eliminar.isEnabled():
            return
        respuesta = QMessageBox.question(
            self, "Eliminar calificación",
            f"¿Eliminar la calificación de {seleccionada.instrumento} "
            f"(ejercicio {seleccionada.ejercicio}, secuencia {seleccionada.secuencia})?\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        self.servicio.eliminar(self.usuario, seleccionada.id)
        self.buscar()
        self._informar(f"Calificación de {seleccionada.instrumento} eliminada.")

    def _cargar(self, titulo: str, filtro: str) -> None:
        if not self.boton_cargar.isEnabled():
            return
        ruta, _ = QFileDialog.getOpenFileName(self, titulo, "", filtro)
        if not ruta:
            return
        dialogo = DialogoCarga(self.usuario, self.carga, self.corredores, ruta,
                               ambito_inicial=self._ambito_filtro(), padre=self)
        if dialogo.exec() == DialogoCarga.DialogCode.Accepted and dialogo.resumen:
            self.buscar()
            r = dialogo.resumen
            self._informar(f"Carga completada: {r['insertadas']} agregadas, "
                           f"{r['actualizadas']} actualizadas, {r['invalidas']} inválidas omitidas.")

    @protegido
    def cargar_archivo(self) -> None:
        self._cargar("Cargar archivo de calificaciones",
                     "Archivos de carga (*.csv *.xlsx *.xls *.xlsm);;Todos los archivos (*)")

    @protegido
    def cargar_pdf(self) -> None:
        self._cargar("Cargar certificado PDF", "Certificados PDF (*.pdf)")

    @protegido
    def exportar(self) -> None:
        calificaciones = self.modelo.calificaciones()
        if not calificaciones:
            QMessageBox.information(self, "Exportar", "No hay calificaciones para exportar: busque primero.")
            return
        filtros = {"Excel (*.xlsx)": ".xlsx", "Excel 97-2003 (*.xls)": ".xls", "CSV (*.csv)": ".csv"}
        ruta, filtro = QFileDialog.getSaveFileName(self, "Exportar calificaciones", "calificaciones.xlsx",
                                                   ";;".join(filtros))
        if not ruta:
            return
        if Path(ruta).suffix.lower() not in filtros.values():
            ruta += filtros.get(filtro, ".xlsx")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            cantidad = self.exportacion.exportar(self.usuario, calificaciones, ruta)
        finally:
            QApplication.restoreOverrideCursor()
        self._informar(f"{cantidad} calificaciones exportadas a {Path(ruta).name}.")
