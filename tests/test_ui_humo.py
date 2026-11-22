"""Prueba de humo de la interfaz sin pantalla (QT_QPA_PLATFORM=offscreen).

Recorre los flujos principales con los datos del HDU: no reemplaza la prueba
manual, pero detecta errores de cableado entre la interfaz y los servicios.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import ui  # noqa: E402,F401  — antes de PySide6 (ver ui/__init__.py)

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from servicios.exportacion import ServicioExportacion  # noqa: E402
from tests.conftest import CLAVE  # noqa: E402
from tests.test_exportacion import requiere_excel  # noqa: E402
from ui.dialogo_calificacion import DialogoCalificacion  # noqa: E402
from ui.dialogo_carga import DialogoCarga  # noqa: E402
from ui.login import DialogoLogin  # noqa: E402
from ui.ventana_principal import VentanaPrincipal  # noqa: E402

DATOS = Path(__file__).parent / "datos"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def si_a_todo(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, texto, *a: avisos.append(texto))
    monkeypatch.setattr(QMessageBox, "critical", lambda _p, _t, texto, *a: avisos.append(texto))
    monkeypatch.setattr(QMessageBox, "information", lambda _p, _t, texto, *a: avisos.append(texto))
    return avisos


def _ventana(entorno, usuario):
    exportacion = ServicioExportacion(entorno.con, entorno.repo_calificaciones,
                                      entorno.repo_auditoria, entorno.reloj)
    return VentanaPrincipal(usuario, entorno.auth, entorno.calificaciones, entorno.carga, exportacion)


def _esperar_lectura(dialogo, segundos=30):
    bucle = QEventLoop()
    dialogo.hilo.finished.connect(bucle.quit)
    QTimer.singleShot(segundos * 1000, bucle.quit)
    if dialogo.hilo.isRunning():
        bucle.exec()
    QCoreApplication.processEvents()


def test_login(app, entorno):
    dialogo = DialogoLogin(entorno.auth)
    dialogo.nombre.setText("ana")
    dialogo.clave.setText("mala")
    dialogo.ingresar.click()
    assert dialogo.usuario is None and dialogo.error.text() == "Usuario o contraseña incorrectos."
    dialogo.clave.setText(CLAVE)
    dialogo.ingresar.click()
    assert dialogo.usuario.nombre == "ana"


def test_ingresar_por_montos_modificar_y_eliminar(app, entorno, si_a_todo):
    ventana = _ventana(entorno, entorno.usuario_a)
    dialogo = DialogoCalificacion(entorno.usuario_a, entorno.calificaciones, ventana.corredores)
    # Fila de ejemplo de la hoja "3.1" y montos de la hoja "3.2 Homologacion columnas" del HDU.
    dialogo.datos.ejercicio.setValue(2023)
    dialogo.datos.instrumento.setText("Copec")
    dialogo.datos.secuencia.setText("123123")
    dialogo.tabla_montos.establecer({8: "192.770.580", 9: "64.161.878", 10: "0", 11: "111.812.860"})
    dialogo._calcular()
    assert dialogo.tabla_factores.valores()[8] == "0,52277431"
    assert "1,00000000" in dialogo.suma.text()
    dialogo._grabar()
    assert dialogo.result() == DialogoCalificacion.DialogCode.Accepted, dialogo.error.text()

    ventana.buscar()
    assert ventana.modelo.rowCount() == 1
    ventana.tabla.selectRow(0)
    completa = entorno.calificaciones.obtener(entorno.usuario_a, ventana._seleccionada().id)
    edicion = DialogoCalificacion(entorno.usuario_a, entorno.calificaciones, ventana.corredores,
                                  calificacion=completa)
    assert not edicion.datos.instrumento.isEnabled()  # llave de solo lectura
    edicion.datos.descripcion.setText("Dividendo definitivo")
    edicion._grabar()
    assert edicion.result() == DialogoCalificacion.DialogCode.Accepted, edicion.error.text()
    ventana.buscar()
    assert ventana.modelo.calificacion(0).descripcion == "Dividendo definitivo"

    ventana.tabla.selectRow(0)
    ventana.eliminar()
    assert ventana.modelo.rowCount() == 0
    assert si_a_todo == []


def test_validacion_en_linea(app, entorno):
    dialogo = DialogoCalificacion(entorno.usuario_a, entorno.calificaciones, [])
    dialogo.datos.instrumento.setText("Copec")
    dialogo.datos.secuencia.setText("9999")
    dialogo.tabla_factores.establecer({8: "0,5"})
    dialogo._grabar()
    assert "Secuencia" in dialogo.error.text()
    assert "Secuencia" in dialogo.datos.secuencia.toolTip()


def test_consulta_tiene_botones_deshabilitados(app, entorno):
    ventana = _ventana(entorno, entorno.consulta_a)
    assert not ventana.boton_ingresar.isEnabled() and not ventana.boton_cargar.isEnabled()
    assert ventana.boton_exportar.isEnabled()


def test_carga_csv_en_segundo_plano(app, entorno, si_a_todo):
    dialogo = DialogoCarga(entorno.usuario_a, entorno.carga, [], str(DATOS / "carga_factores.csv"))
    _esperar_lectura(dialogo)
    assert dialogo.tabla_previa.rowCount() == 2
    assert "1 nuevas" in dialogo.resumen_previa.text() and "1 inválidas" in dialogo.resumen_previa.text()
    dialogo.confirmar.click()
    assert dialogo.resumen["insertadas"] == 1


def test_admin_debe_elegir_ambito_en_carga(app, entorno):
    corredores = entorno.auth.listar_corredores(entorno.admin)
    dialogo = DialogoCarga(entorno.admin, entorno.carga, corredores, str(DATOS / "carga_factores.csv"))
    _esperar_lectura(dialogo)
    assert not dialogo.confirmar.isEnabled() and "Seleccione" in dialogo.resumen_previa.text()
    dialogo.ambito.setCurrentIndex(dialogo.ambito.findText("Bolsa"))
    assert dialogo.confirmar.isEnabled() and dialogo.resultado.corredor_id is None


def test_carga_pdf_vista_dividida(app, entorno, si_a_todo):
    dialogo = DialogoCarga(entorno.usuario_a, entorno.carga, [],
                           str(DATOS / "certificado70_orden_distinto.pdf"))
    _esperar_lectura(dialogo)
    assert "Documento de prueba" in dialogo.texto_pdf.toPlainText()
    assert dialogo.montos_pdf.valores()[8] == "192.770.580"
    assert dialogo.datos_pdf.ejercicio.value() == 2023
    assert not dialogo.previsualizar_pdf.isEnabled()  # faltan datos básicos
    dialogo.datos_pdf.instrumento.setText("Copec")
    dialogo.datos_pdf.secuencia.setText("123123")
    assert dialogo.previsualizar_pdf.isEnabled()
    dialogo.previsualizar_pdf.click()
    assert dialogo.confirmar.isEnabled(), dialogo.error_pdf.text()
    dialogo.confirmar.click()
    assert dialogo.resumen["origen"] == "PDF" and si_a_todo == []


@requiere_excel
def test_carga_excel_desde_el_hilo(app, entorno, si_a_todo, tmp_path):
    """xlwings dentro del QThread (CoInitialize en Windows)."""
    from tests.conftest import calificacion_ejemplo
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    ruta = tmp_path / "carga.xlsx"
    exportacion = ServicioExportacion(entorno.con, entorno.repo_calificaciones,
                                      entorno.repo_auditoria, entorno.reloj)
    exportacion.exportar(entorno.usuario_a, entorno.calificaciones.buscar(entorno.usuario_a), str(ruta))
    dialogo = DialogoCarga(entorno.usuario_b, entorno.carga, [], str(ruta))
    _esperar_lectura(dialogo, segundos=60)
    assert si_a_todo == []
    assert "1 nuevas" in dialogo.resumen_previa.text()


def test_exportar_csv(app, entorno, si_a_todo, tmp_path, monkeypatch):
    ventana = _ventana(entorno, entorno.usuario_a)
    from tests.conftest import calificacion_ejemplo
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    ventana.buscar()
    destino = tmp_path / "salida"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(destino), "CSV (*.csv)"))
    ventana.exportar()
    assert (tmp_path / "salida.csv").exists()
    assert "1 calificaciones exportadas" in ventana.statusBar().currentMessage()
