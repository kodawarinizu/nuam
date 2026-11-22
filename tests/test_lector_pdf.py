from decimal import Decimal
from pathlib import Path

import pytest

from infraestructura import lector_pdf
from servicios.errores import ArchivoInvalido

DATOS = Path(__file__).parent / "datos"
# PDFs generados por tests/datos/generar_certificados.py con los montos del HDU,
# hoja "3.2 Homologacion columnas".
MONTOS_HDU = {8: "192.770.580", 9: "64.161.878", 10: "0", 11: "111.812.860",
              25: "71.298.705", 30: "15.837.333"}


def _montos(fila):
    return {int(k.split("_")[1]): v for k, v in fila.items() if k.startswith("monto_") and v is not None}


def test_lee_montos_del_certificado():
    fila, = lector_pdf.leer(str(DATOS / "certificado70_prueba.pdf"))
    assert _montos(fila) == MONTOS_HDU
    assert fila["ejercicio"] == "2023"
    assert "Documento de prueba" in fila["_texto"]


def test_orden_distinto_entrega_los_mismos_montos():
    normal, = lector_pdf.leer(str(DATOS / "certificado70_prueba.pdf"))
    otro, = lector_pdf.leer(str(DATOS / "certificado70_orden_distinto.pdf"))
    assert _montos(otro) == _montos(normal) == MONTOS_HDU
    assert otro["_no_encontradas"] == normal["_no_encontradas"]


def test_campos_no_encontrados_quedan_none():
    fila, = lector_pdf.leer(str(DATOS / "certificado70_prueba.pdf"))
    assert fila["monto_12"] is None
    assert 12 in fila["_no_encontradas"] and 8 not in fila["_no_encontradas"]
    assert all(f"monto_{c}" not in fila for c in range(34, 38))  # 34–37 no se leen


def test_columna_18_no_se_confunde_con_8():
    fila = lector_pdf.interpretar("(18) $ 5\n(8) $ 7")
    assert fila["monto_8"] == "7" and fila["monto_18"] == "5"


def test_pdf_danado(tmp_path):
    ruta = tmp_path / "danado.pdf"
    ruta.write_bytes(b"esto no es un pdf")
    with pytest.raises(ArchivoInvalido):
        lector_pdf.leer(str(ruta))


def test_carga_pdf_completa(entorno):
    fila, = lector_pdf.leer(str(DATOS / "certificado70_prueba.pdf"))
    # Datos básicos que el certificado no trae: los ingresa el usuario
    # (fila de ejemplo de la hoja "3.1 Archivo de carga" del HDU).
    fila.update(mercado="ACN", instrumento="Copec", fecha_pago="12-12-2023", secuencia="123123")
    resultado = entorno.carga.previsualizar([fila], entorno.corredor_a, "PDF")
    assert resultado.invalidas == []
    c = resultado.validas[0].calificacion
    assert c.factores[8] == Decimal("0.52277431") and c.factores[30] == Decimal("0.04294924")
    resumen = entorno.carga.confirmar(entorno.usuario_a, resultado, "PDF")
    assert resumen["origen"] == "PDF" and resumen["insertadas"] == 1
