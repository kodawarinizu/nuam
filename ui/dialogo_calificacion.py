"""Ingreso y modificación de una calificación (por montos o por factores)."""

from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog, QGroupBox, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

import config
from servicios.auth import NO_ELEGIDO
from servicios.calificaciones import (
    ServicioCalificaciones, calcular_desde_textos, calificacion_desde_fila, decimal_a_texto,
    entero_a_texto, sumar_factores_textos,
)
from servicios.entidades import Calificacion, Usuario
from servicios.errores import ValidacionError
from ui.comun import (
    COLOR_ERROR, FormularioDatosBasicos, TablaColumnas, campo_de_error, etiqueta_error,
    fila_botones, marcar_etiqueta, mostrar_error,
)

_RANGO = f"{config.RANGO_SUMA_FACTORES.start} a {config.RANGO_SUMA_FACTORES.stop - 1}"


class DialogoCalificacion(QDialog):
    def __init__(self, usuario: Usuario, servicio: ServicioCalificaciones, corredores: list[dict],
                 calificacion: Calificacion | None = None, mercado_inicial: str | None = None,
                 ambito_inicial=NO_ELEGIDO, padre=None):
        super().__init__(padre)
        self.usuario = usuario
        self.servicio = servicio
        self.original = calificacion
        self.resultado: Calificacion | None = None
        modificando = calificacion is not None
        self.setWindowTitle("Modificar calificación" if modificando else "Ingresar calificación")
        self.resize(820, 640)

        self.datos = FormularioDatosBasicos(usuario, corredores)
        grupo = QGroupBox("Datos básicos")
        QVBoxLayout(grupo).addWidget(self.datos)

        # Pestaña Montos (8–33: las columnas con fórmula).
        self.tabla_montos = TablaColumnas(config.COLUMNAS_CALCULADAS, "Monto ($)")
        calcular = QPushButton("Calcular factores")
        calcular.setToolTip(f"factor = monto / suma de montos de las columnas {_RANGO}")
        calcular.clicked.connect(self._calcular)
        pagina_montos = QWidget()
        disposicion_montos = QVBoxLayout(pagina_montos)
        disposicion_montos.addWidget(QLabel(
            "Ingrese los montos en pesos. Los factores de las columnas 34 a 37 no tienen "
            "fórmula: ingréselos en la pestaña Factores."))
        disposicion_montos.addWidget(self.tabla_montos)
        fila_calcular = QHBoxLayout()
        fila_calcular.addStretch()
        fila_calcular.addWidget(calcular)
        disposicion_montos.addLayout(fila_calcular)

        # Pestaña Factores (8–37), con la suma del rango visible.
        self.tabla_factores = TablaColumnas(config.COLUMNAS, "Factor")
        self.tabla_factores.cambiado.connect(self._actualizar_suma)
        self.suma = QLabel()
        pagina_factores = QWidget()
        disposicion_factores = QVBoxLayout(pagina_factores)
        disposicion_factores.addWidget(QLabel(
            "Factores con hasta 8 decimales (ej.: 0,52277431). Si hay montos ingresados, "
            "los factores 8 a 33 se recalculan al grabar."))
        disposicion_factores.addWidget(self.tabla_factores)
        disposicion_factores.addWidget(self.suma)

        self.pestanas = QTabWidget()
        self.pestanas.addTab(pagina_montos, "Montos")
        self.pestanas.addTab(pagina_factores, "Factores")

        self.error = etiqueta_error()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        grabar = QPushButton("Grabar")
        grabar.clicked.connect(self._grabar)

        disposicion = QVBoxLayout(self)
        disposicion.addWidget(grupo)
        disposicion.addWidget(self.pestanas, 1)
        disposicion.addWidget(self.error)
        disposicion.addLayout(fila_botones(cancelar, grabar))

        if modificando:
            self._cargar(calificacion)
            self.datos.bloquear_llave()
        else:
            self.datos.establecer_mercado(mercado_inicial)
            self.datos.establecer_ambito(ambito_inicial)
        self._actualizar_suma()

    def _cargar(self, c: Calificacion) -> None:
        self.datos.cargar(c)
        self.tabla_montos.establecer({col: entero_a_texto(m) for col, m in c.montos.items()})
        self.tabla_factores.establecer({col: decimal_a_texto(f) for col, f in c.factores.items()})
        if c.montos:
            self.pestanas.setCurrentIndex(0)
        else:
            self.pestanas.setCurrentIndex(1)

    def _actualizar_suma(self) -> None:
        suma = sumar_factores_textos(self.tabla_factores.valores())
        if suma is None:
            self.suma.setText(f"Suma de las columnas {_RANGO}: (hay factores no numéricos)")
            marcar_etiqueta(self.suma, True)
            return
        self.suma.setText(f"Suma de las columnas {_RANGO}: {decimal_a_texto(suma)} (máximo 1)")
        marcar_etiqueta(self.suma, suma > Decimal(1))

    def _limpiar_errores(self) -> None:
        self.error.hide()
        self.datos.limpiar_marcas()
        self.tabla_montos.limpiar_resaltado()
        self.tabla_factores.limpiar_resaltado()

    def _mostrar_validacion(self, error: ValidacionError) -> None:
        """Validación en línea: marca el campo o la celda y muestra qué corregir."""
        self.error.setText(str(error))
        self.error.show()
        tipo, columna = campo_de_error(error)
        if columna is not None:
            tabla = self.tabla_montos if tipo == "monto" else self.tabla_factores
            self.pestanas.setCurrentIndex(0 if tipo == "monto" else 1)
            tabla.resaltar([columna], COLOR_ERROR)
            tabla.ir_a(columna)
        else:
            self.datos.marcar(tipo, str(error))

    def _calcular(self) -> None:
        self._limpiar_errores()
        try:
            factores = calcular_desde_textos(self.tabla_montos.valores())
        except ValidacionError as error:
            self._mostrar_validacion(error)
            return
        valores = self.tabla_factores.valores()
        for col in config.COLUMNAS_CALCULADAS:
            valores[col] = decimal_a_texto(factores[col]) if col in factores else ""
        self.tabla_factores.establecer(valores)
        self.pestanas.setCurrentIndex(1)

    def _fila_formulario(self) -> dict:
        """Con montos: montos 8–33 y factores 34–37. Sin montos: factores 8–37."""
        fila = self.datos.valores()
        montos = {c: t for c, t in self.tabla_montos.valores().items() if t}
        factores = {c: t for c, t in self.tabla_factores.valores().items() if t}
        if montos:
            factores = {c: t for c, t in factores.items() if c in config.COLUMNAS_SOLO_INGRESO}
        fila.update({f"monto_{c}": t for c, t in montos.items()})
        fila.update({f"factor_{c}": t for c, t in factores.items()})
        return fila

    def _grabar(self) -> None:
        self._limpiar_errores()
        try:
            calificacion = calificacion_desde_fila(self._fila_formulario())
            if self.original is None:
                self.resultado = self.servicio.crear(self.usuario, calificacion,
                                                     corredor=self.datos.ambito_elegido())
            else:
                self.resultado = self.servicio.modificar(self.usuario, self.original.id, calificacion)
        except ValidacionError as error:
            self._mostrar_validacion(error)
            return
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, error)
            return
        self.accept()
