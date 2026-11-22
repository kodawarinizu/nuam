import sys
from datetime import date
from pathlib import Path

import pytest

from infraestructura import lector_csv
from servicios.errores import PermisoDenegado, ValidacionError
from servicios.exportacion import ServicioExportacion, calificaciones_a_filas
from tests.conftest import calificacion_ejemplo


def excel_instalado() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Excel.Application"))
            return True
        except OSError:
            return False
    return sys.platform == "darwin" and Path("/Applications/Microsoft Excel.app").exists()


requiere_excel = pytest.mark.skipif(not excel_instalado(), reason="Requiere Microsoft Excel instalado")


@pytest.fixture
def exportacion(entorno):
    return ServicioExportacion(entorno.con, entorno.repo_calificaciones, entorno.repo_auditoria,
                               entorno.reloj)


def test_conversion_a_filas(entorno):
    creada = entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    c = entorno.calificaciones.obtener(entorno.usuario_a, creada.id)
    texto, = calificaciones_a_filas([c], para_excel=False)
    assert texto[:6] == [2023, "ACN", "COPEC", "12-12-2023", 123123, 123456]
    assert texto[10] == "0,52277431"  # Factor 8 (HDU, hoja "3.2 Homologacion columnas")
    excel, = calificaciones_a_filas([c], para_excel=True)
    assert excel[3] == date(2023, 12, 12) and excel[10] == 0.52277431


def test_exportar_csv_y_volver_a_cargar(entorno, exportacion, tmp_path):
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    lista = entorno.calificaciones.buscar(entorno.usuario_a)
    ruta = tmp_path / "salida.csv"
    assert exportacion.exportar(entorno.consulta_a, lista, str(ruta)) == 1  # consulta puede exportar

    filas = lector_csv.leer(str(ruta))
    resultado = entorno.carga.previsualizar(filas, entorno.corredor_a)
    assert resultado.invalidas == [] and resultado.validas[0].estado == "actualiza"
    auditoria, = entorno.acciones("EXPORTACION")
    assert auditoria["detalle"] == {"archivo": "salida.csv", "formato": ".csv", "cantidad": 1}


def test_no_exporta_calificaciones_de_otro_corredor(entorno, exportacion, tmp_path):
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    lista = entorno.calificaciones.buscar(entorno.usuario_a)
    with pytest.raises(PermisoDenegado):
        exportacion.exportar(entorno.usuario_b, lista, str(tmp_path / "x.csv"))


def test_extension_no_soportada(entorno, exportacion, tmp_path):
    with pytest.raises(ValidacionError):
        exportacion.exportar(entorno.usuario_a, [], str(tmp_path / "x.txt"))


@requiere_excel
@pytest.mark.parametrize("extension", [".xlsx", ".xls"])
def test_exportar_y_leer_excel(entorno, exportacion, tmp_path, extension):
    from infraestructura import lector_excel
    entorno.calificaciones.crear(entorno.usuario_a, calificacion_ejemplo())
    ruta = tmp_path / f"salida{extension}"
    exportacion.exportar(entorno.usuario_a, entorno.calificaciones.buscar(entorno.usuario_a), str(ruta))
    filas = lector_excel.leer(str(ruta))
    resultado = entorno.carga.previsualizar(filas, entorno.corredor_a)
    assert resultado.invalidas == [] and resultado.validas[0].estado == "actualiza"
    assert str(resultado.validas[0].calificacion.factores[8]) == "0.52277431"
