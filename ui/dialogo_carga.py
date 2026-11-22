"""Carga masiva (CSV/Excel) y carga de certificados PDF.

Solo la lectura del archivo corre en un QThread (no usa la base). La
previsualización y la confirmación usan la conexión SQLite, así que corren en
el hilo principal cuando el hilo termina.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

import config
from servicios.auth import NO_ELEGIDO, corredor_efectivo
from servicios.carga_masiva import ServicioCargaMasiva, leer_archivo, requiere_excel, tipo_de_archivo
from servicios.entidades import ResultadoCarga, Usuario
from servicios.errores import ValidacionError
from ui.comun import (
    COLOR_ERROR, COLOR_FALTANTE, FormularioDatosBasicos, TablaColumnas, ambito_de_combo,
    combo_ambito, etiqueta_error, fila_botones, marcar_etiqueta, mostrar_error,
    seleccionar_ambito,
)

_COLUMNAS_PREVIA = ["Fila", "Estado", "Ejercicio", "Mercado", "Instrumento", "Secuencia", "Motivo"]


class LectorArchivo(QObject):
    """Lee el archivo en segundo plano y avisa con señales (Observer)."""

    terminado = Signal(object)
    fallo = Signal(object)

    def __init__(self, ruta: str):
        super().__init__()
        self.ruta = ruta

    @Slot()
    def ejecutar(self) -> None:
        com_iniciado = False
        try:
            if sys.platform == "win32" and requiere_excel(self.ruta):
                import pythoncom  # xlwings vía COM exige inicializarlo en cada hilo
                pythoncom.CoInitialize()
                com_iniciado = True
            self.terminado.emit(leer_archivo(self.ruta))
        except Exception as error:  # noqa: BLE001 — se informa en el hilo principal
            self.fallo.emit(error)
        finally:
            if com_iniciado:
                import pythoncom
                pythoncom.CoUninitialize()


class DialogoCarga(QDialog):
    def __init__(self, usuario: Usuario, servicio: ServicioCargaMasiva, corredores: list[dict],
                 ruta: str, ambito_inicial=NO_ELEGIDO, padre=None):
        super().__init__(padre)
        self.usuario = usuario
        self.servicio = servicio
        self.corredores = corredores
        self.ruta = ruta
        self.tipo = tipo_de_archivo(ruta)
        self.filas: list[dict] = []
        self.resultado: ResultadoCarga | None = None
        self.resumen: dict | None = None
        self._cancelado = False

        es_pdf = self.tipo == "PDF"
        self.setWindowTitle("Cargar certificado PDF" if es_pdf else "Carga masiva desde archivo")
        self.resize(1100 if es_pdf else 950, 650)

        self.estado = QLabel(f"Leyendo {Path(ruta).name}…")
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)  # indeterminado mientras se lee

        # Selector de ámbito (solo admin). En PDF va dentro del formulario.
        self.ambito = None
        fila_ambito = QHBoxLayout()
        if usuario.rol == "admin" and not es_pdf:
            self.ambito = combo_ambito(corredores)
            seleccionar_ambito(self.ambito, ambito_inicial)
            self.ambito.currentIndexChanged.connect(self._previsualizar_archivo)
            fila_ambito.addWidget(QLabel("Cargar en (corredor o Bolsa):"))
            fila_ambito.addWidget(self.ambito)
            fila_ambito.addStretch()

        self.paginas = QStackedWidget()
        self.paginas.addWidget(self._pagina_archivo())
        self.paginas.addWidget(self._pagina_pdf(ambito_inicial))
        self.paginas.setCurrentIndex(1 if es_pdf else 0)
        self.paginas.setEnabled(False)

        self.cancelar = QPushButton("Cancelar")
        self.cancelar.clicked.connect(self.reject)
        self.confirmar = QPushButton("Confirmar carga")
        self.confirmar.setEnabled(False)
        self.confirmar.clicked.connect(self._confirmar)
        formato = QPushButton("Ver formato esperado")
        formato.clicked.connect(self._ver_formato)
        extras = [] if es_pdf else [formato]

        disposicion = QVBoxLayout(self)
        disposicion.addWidget(self.estado)
        disposicion.addWidget(self.progreso)
        disposicion.addLayout(fila_ambito)
        disposicion.addWidget(self.paginas, 1)
        disposicion.addLayout(fila_botones(self.cancelar, self.confirmar, *extras))

        self._iniciar_lectura()

    # ---------- páginas ----------

    def _pagina_archivo(self) -> QWidget:
        self.tabla_previa = QTableWidget(0, len(_COLUMNAS_PREVIA))
        self.tabla_previa.setHorizontalHeaderLabels(_COLUMNAS_PREVIA)
        self.tabla_previa.verticalHeader().hide()
        self.tabla_previa.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla_previa.horizontalHeader().setStretchLastSection(True)
        self.resumen_previa = QLabel()
        pagina = QWidget()
        disposicion = QVBoxLayout(pagina)
        disposicion.addWidget(self.tabla_previa)
        disposicion.addWidget(self.resumen_previa)
        return pagina

    def _pagina_pdf(self, ambito_inicial) -> QWidget:
        self.texto_pdf = QPlainTextEdit()
        self.texto_pdf.setReadOnly(True)
        izquierda = QGroupBox("Texto extraído del PDF")
        QVBoxLayout(izquierda).addWidget(self.texto_pdf)

        self.datos_pdf = FormularioDatosBasicos(self.usuario, self.corredores)
        self.datos_pdf.establecer_ambito(ambito_inicial)
        self.datos_pdf.cambiado.connect(self._datos_pdf_cambiados)
        self.montos_pdf = TablaColumnas(config.COLUMNAS_CALCULADAS, "Monto ($)")
        self.montos_pdf.setMinimumHeight(300)
        self.montos_pdf.cambiado.connect(self._datos_pdf_cambiados)
        self.factores_pdf = TablaColumnas(config.COLUMNAS_SOLO_INGRESO, "Factor")
        self.factores_pdf.setMinimumHeight(150)
        self.factores_pdf.cambiado.connect(self._datos_pdf_cambiados)
        self.aviso_pdf = QLabel()
        self.aviso_pdf.setWordWrap(True)
        self.error_pdf = etiqueta_error()
        self.resultado_pdf = QLabel()
        self.resultado_pdf.setWordWrap(True)
        self.previsualizar_pdf = QPushButton("Previsualizar")
        self.previsualizar_pdf.setEnabled(False)
        self.previsualizar_pdf.clicked.connect(self._previsualizar_pdf)

        grupo_datos = QGroupBox("Datos básicos (el certificado no los trae: complételos)")
        QVBoxLayout(grupo_datos).addWidget(self.datos_pdf)
        grupo_montos = QGroupBox("Montos extraídos")
        disposicion_montos = QVBoxLayout(grupo_montos)
        disposicion_montos.addWidget(self.aviso_pdf)
        disposicion_montos.addWidget(self.montos_pdf)
        grupo_factores = QGroupBox("Factores sin fórmula (34 a 37, opcionales)")
        QVBoxLayout(grupo_factores).addWidget(self.factores_pdf)

        contenido = QWidget()
        derecha = QVBoxLayout(contenido)
        derecha.addWidget(grupo_datos)
        derecha.addWidget(grupo_montos)
        derecha.addWidget(grupo_factores)
        derecha.addWidget(self.error_pdf)
        derecha.addWidget(self.resultado_pdf)
        fila = QHBoxLayout()
        fila.addStretch()
        fila.addWidget(self.previsualizar_pdf)
        derecha.addLayout(fila)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(contenido)

        division = QSplitter(Qt.Orientation.Horizontal)
        division.addWidget(izquierda)
        division.addWidget(desplazable)
        division.setSizes([450, 650])
        return division

    # ---------- lectura en segundo plano ----------

    def _iniciar_lectura(self) -> None:
        self.hilo = QThread(self)
        self.lector = LectorArchivo(self.ruta)
        self.lector.moveToThread(self.hilo)
        self.hilo.started.connect(self.lector.ejecutar)
        self.lector.terminado.connect(self._archivo_leido)
        self.lector.fallo.connect(self._lectura_fallida)
        self.lector.terminado.connect(self.hilo.quit)
        self.lector.fallo.connect(self.hilo.quit)
        self.hilo.finished.connect(self.lector.deleteLater)
        self.hilo.finished.connect(self._hilo_terminado)
        self.hilo.start()

    def _hilo_terminado(self) -> None:
        if self._cancelado:
            super().reject()

    def reject(self) -> None:
        # No se puede destruir el diálogo con el hilo corriendo: se espera a que termine,
        # sin bloquear la ventana.
        if self.hilo.isRunning():
            self._cancelado = True
            self.estado.setText("Cancelando: esperando que termine la lectura del archivo…")
            self.cancelar.setEnabled(False)
            self.confirmar.setEnabled(False)
            return
        super().reject()

    def _terminar_progreso(self) -> None:
        self.progreso.setRange(0, 1)
        self.progreso.setValue(1)
        self.progreso.hide()

    def _archivo_leido(self, filas: list[dict]) -> None:
        if self._cancelado:
            return
        self._terminar_progreso()
        self.filas = filas
        self.paginas.setEnabled(True)
        try:
            if self.tipo == "PDF":
                self._mostrar_pdf(filas[0])
            else:
                self.estado.setText(f"{Path(self.ruta).name}: {len(filas)} filas leídas.")
                self._previsualizar_archivo()
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, error)

    def _lectura_fallida(self, error: Exception) -> None:
        if self._cancelado:
            return
        self._terminar_progreso()
        self.estado.setText("No se pudo leer el archivo.")
        mostrar_error(self, error)

    # ---------- CSV / Excel ----------

    def _corredor_destino(self, ambito):
        """Ámbito de la carga; None si el admin aún no eligió."""
        try:
            return True, corredor_efectivo(self.usuario, ambito)
        except ValidacionError:
            return False, None

    def _previsualizar_archivo(self, *_):
        if not self.filas and self.tipo != "PDF":
            self.resumen_previa.setText("El archivo no tiene filas de datos.")
            self.confirmar.setEnabled(False)
            return
        ambito = ambito_de_combo(self.ambito) if self.ambito is not None else NO_ELEGIDO
        elegido, corredor_id = self._corredor_destino(ambito)
        if not elegido:
            self.tabla_previa.setRowCount(0)
            self.resumen_previa.setText("Seleccione un corredor o Bolsa para previsualizar la carga.")
            self.confirmar.setEnabled(False)
            return
        try:
            self.resultado = self.servicio.previsualizar(self.filas, corredor_id, self.tipo)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, error)
            return
        self._llenar_previa(self.resultado)

    def _llenar_previa(self, resultado: ResultadoCarga) -> None:
        crudas = {f.get("_fila"): f for f in self.filas}
        filas = []
        for valida in resultado.validas:
            c = valida.calificacion
            filas.append((valida.numero_fila, valida.estado, c.ejercicio, c.mercado, c.instrumento,
                          c.secuencia, "", None))
        for invalida in resultado.invalidas:
            cruda = crudas.get(invalida.numero_fila, {})
            filas.append((invalida.numero_fila, "inválida", cruda.get("ejercicio"),
                          cruda.get("mercado"), cruda.get("instrumento"), cruda.get("secuencia"),
                          invalida.motivo, COLOR_ERROR))
        filas.sort(key=lambda f: f[0])

        self.tabla_previa.setRowCount(len(filas))
        for i, (*valores, color) in enumerate(filas):
            for j, valor in enumerate(valores):
                item = QTableWidgetItem("" if valor is None else str(valor))
                if color is not None:
                    item.setData(Qt.ItemDataRole.BackgroundRole, color)
                if j == len(valores) - 1 and valor:
                    item.setToolTip(str(valor))
                self.tabla_previa.setItem(i, j, item)
        self.tabla_previa.resizeColumnsToContents()

        nuevas = sum(1 for v in resultado.validas if v.estado == "nueva")
        actualiza = len(resultado.validas) - nuevas
        self.resumen_previa.setText(
            f"{nuevas} nuevas, {actualiza} actualizan una existente, "
            f"{len(resultado.invalidas)} inválidas (no se cargarán; ver Motivo).")
        self.confirmar.setEnabled(bool(resultado.validas))

    # ---------- PDF ----------

    def _mostrar_pdf(self, fila: dict) -> None:
        self.texto_pdf.setPlainText(fila.get("_texto", ""))
        try:
            anio = int(fila.get("ejercicio") or 0)
        except ValueError:
            anio = 0
        if config.EJERCICIO_MIN <= anio <= config.EJERCICIO_MAX:
            self.datos_pdf.ejercicio.setValue(anio)  # supuesto: ejercicio = año comercial
        self.montos_pdf.establecer({c: fila.get(f"monto_{c}") or "" for c in config.COLUMNAS_CALCULADAS})
        no_encontradas = fila.get("_no_encontradas", [])
        self.montos_pdf.resaltar(no_encontradas, COLOR_FALTANTE)
        encontradas = len(config.COLUMNAS_CALCULADAS) - len(no_encontradas)
        self.aviso_pdf.setText(
            f"Se encontraron {encontradas} montos. Las filas resaltadas no se encontraron en el PDF: "
            "revíselas en el texto de la izquierda y complételas, o déjelas en blanco si no aplican.")
        self.estado.setText(f"{Path(self.ruta).name}: texto extraído. Complete los datos básicos.")
        self._datos_pdf_cambiados()

    def _datos_pdf_cambiados(self) -> None:
        """Cualquier cambio invalida la previsualización anterior."""
        self.resultado = None
        self.confirmar.setEnabled(False)
        self.resultado_pdf.clear()
        self.previsualizar_pdf.setEnabled(self.datos_pdf.completos())

    def _fila_pdf(self) -> dict:
        fila = {"_fila": 1, **self.datos_pdf.valores()}
        fila.update({f"monto_{c}": t for c, t in self.montos_pdf.valores().items() if t})
        fila.update({f"factor_{c}": t for c, t in self.factores_pdf.valores().items() if t})
        return fila

    def _previsualizar_pdf(self) -> None:
        self.error_pdf.hide()
        self.datos_pdf.limpiar_marcas()
        elegido, corredor_id = self._corredor_destino(self.datos_pdf.ambito_elegido())
        if not elegido:
            self.datos_pdf.marcar("corredor", "Seleccione un corredor o Bolsa.")
            return
        try:
            self.resultado = self.servicio.previsualizar([self._fila_pdf()], corredor_id, self.tipo)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, error)
            return
        if self.resultado.invalidas:
            motivo = self.resultado.invalidas[0].motivo
            self.error_pdf.setText(f"No se puede cargar: {motivo}")
            self.error_pdf.show()
            self.resultado = None
            return
        estado = self.resultado.validas[0].estado
        self.resultado_pdf.setText(
            "Válida: se agregará como una calificación nueva." if estado == "nueva"
            else "Válida: actualizará la calificación existente con la misma llave.")
        marcar_etiqueta(self.resultado_pdf, False)
        self.confirmar.setEnabled(True)

    # ---------- confirmación ----------

    def _ver_formato(self) -> None:
        QMessageBox.information(self, "Formato esperado del archivo", config.FORMATO_ARCHIVO)

    def _confirmar(self) -> None:
        if self.resultado is None or not self.resultado.validas:
            return
        nuevas = sum(1 for v in self.resultado.validas if v.estado == "nueva")
        actualiza = len(self.resultado.validas) - nuevas
        destino = "Bolsa" if self.resultado.corredor_id is None else "el corredor"
        respuesta = QMessageBox.question(
            self, "Confirmar carga",
            f"Se agregarán {nuevas} y se actualizarán {actualiza} calificaciones en {destino}."
            + (f"\n{len(self.resultado.invalidas)} filas inválidas no se cargarán."
               if self.resultado.invalidas else "")
            + "\n\n¿Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            self.resumen = self.servicio.confirmar(self.usuario, self.resultado, self.tipo)
        except Exception as error:  # noqa: BLE001 — mostrar_error distingue negocio de inesperado
            mostrar_error(self, error)
            return
        self.accept()
