from decimal import Decimal
from pathlib import Path

import pytest

from infraestructura import lector_csv
from servicios.errores import ArchivoInvalido

DATOS = Path(__file__).parent / "datos"


def test_lee_csv_con_encabezados_en_otro_orden(entorno):
    # tests/datos/carga_factores.csv: fila de ejemplo de la hoja "3.1 Archivo de carga" del HDU
    # con los factores de la hoja "3.2 Homologacion columnas"; la 2.ª fila tiene secuencia 9999.
    filas = lector_csv.leer(str(DATOS / "carga_factores.csv"))
    assert len(filas) == 2
    assert filas[0]["instrumento"] == "Copec" and filas[0]["factor_8"] == "0,52277431"
    assert filas[0]["_fila"] == 2

    resultado = entorno.carga.previsualizar(filas, entorno.corredor_a)
    assert len(resultado.validas) == 1 and resultado.invalidas[0].numero_fila == 3
    c = resultado.validas[0].calificacion
    assert c.instrumento == "COPEC" and c.fecha_pago == "2023-12-12"
    assert c.factores[8] == Decimal("0.52277431")


def test_separador_coma_y_montos(tmp_path):
    ruta = tmp_path / "montos.csv"
    ruta.write_text("Ejercicio,Mercado,Instrumento,Fecha,Secuencia,Monto 8,Monto 9\n"
                    "2023,ACN,Copec,12-12-2023,123123,192770580,64161878\n", encoding="utf-8")
    filas = lector_csv.leer(str(ruta))
    assert filas[0]["monto_8"] == "192770580"


def test_csv_en_cp1252(tmp_path):
    ruta = tmp_path / "ansi.csv"
    ruta.write_bytes("Ejercicio;Mercado;Instrumento;Fecha;Secuencia;Descripción;Factor 8\n"
                     "2023;ACN;Copec;12-12-2023;123123;Año;0,5\n".encode("cp1252"))
    assert lector_csv.leer(str(ruta))[0]["descripcion"] == "Año"


def test_falta_columna_obligatoria(tmp_path):
    ruta = tmp_path / "incompleto.csv"
    ruta.write_text("Ejercicio;Mercado;Instrumento;Fecha;Factor 8\n2023;ACN;Copec;12-12-2023;0,5\n",
                    encoding="utf-8")
    with pytest.raises(ArchivoInvalido, match="Secuencia"):
        lector_csv.leer(str(ruta))


def test_sin_columnas_de_factores_ni_montos(tmp_path):
    ruta = tmp_path / "sin_factores.csv"
    ruta.write_text("Ejercicio;Mercado;Instrumento;Fecha;Secuencia\n", encoding="utf-8")
    with pytest.raises(ArchivoInvalido, match="Factor"):
        lector_csv.leer(str(ruta))


def test_archivo_vacio_o_inexistente(tmp_path):
    vacio = tmp_path / "vacio.csv"
    vacio.write_text("", encoding="utf-8")
    with pytest.raises(ArchivoInvalido):
        lector_csv.leer(str(vacio))
    with pytest.raises(ArchivoInvalido):
        lector_csv.leer(str(tmp_path / "no_existe.csv"))
