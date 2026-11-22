"""Genera los certificados PDF de prueba (requiere reportlab, dependencia de desarrollo).

    python tests/datos/generar_certificados.py

Estructura: Certificado N°70 del SII (Res. Ex. N°98 de 2020, Anexo 3; vigente
Res. Ex. N°85 de 2024, Anexo 7): encabezado del emisor, destinatario, año
comercial, columnas numeradas y pie con N° de certificado, ciudad y fecha y
firma del representante legal.

Montos: SOLO los del HDU de NUAM, hoja "3.2 Homologacion columnas". Las demás
columnas quedan en blanco (no se inventan valores). Año comercial 2023: ejercicio
de la fila de ejemplo de la hoja "3.1 Archivo de carga" del HDU.

Los PDFs generados se guardan en el repositorio, así las pruebas no requieren reportlab.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

import config  # noqa: E402

CARPETA = Path(__file__).resolve().parent
LEYENDA = "Documento de prueba: formato SII, montos del HDU de NUAM"
MONTOS_HDU = {8: "192.770.580", 9: "64.161.878", 10: "0", 11: "111.812.860",
              25: "71.298.705", 30: "15.837.333"}
LARGO_NOMBRE = 95


def generar(ruta: Path, columnas: list[int]) -> None:
    pdf = canvas.Canvas(str(ruta), pagesize=A4)
    pdf.setTitle("Certificado N°70 de prueba")
    _, alto = A4
    y = alto - 50

    def linea(texto, x=40, fuente="Helvetica", tamano=9, salto=14):
        nonlocal y
        pdf.setFont(fuente, tamano)
        pdf.drawString(x, y, texto)
        y -= salto

    linea("CERTIFICADO N° 70", fuente="Helvetica-Bold", tamano=13, salto=18)
    linea(LEYENDA, fuente="Helvetica-Bold", tamano=10, salto=20)
    linea("Nombre o Razón Social: (emisor de prueba)")
    linea("RUT: (de prueba)")
    linea("Dirección: (de prueba)")
    linea("Giro o Actividad: (de prueba)", salto=20)
    linea("Señor(a): (destinatario de prueba)")
    linea("Año comercial: 2023", salto=20)
    linea("Columna      Monto        Concepto", fuente="Helvetica-Bold", salto=14)

    for columna in columnas:
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(40, y, f"({columna})")
        monto = MONTOS_HDU.get(columna)
        pdf.drawRightString(150, y, f"$ {monto}" if monto is not None else "$")
        pdf.drawString(160, y, config.NOMBRES_COLUMNAS[columna][:LARGO_NOMBRE])
        y -= 12

    y -= 14
    linea("CERTIFICADO N°: (de prueba)")
    linea("Ciudad y Fecha: (de prueba)")
    linea("Firma del representante legal: ______________________")
    pdf.showPage()
    pdf.save()


def main() -> None:
    columnas = list(config.COLUMNAS_CALCULADAS)
    generar(CARPETA / "certificado70_prueba.pdf", columnas)
    # Mismas columnas en otro orden (NUAM: los certificados llegan con los campos en distinto orden).
    otro_orden = columnas[1::2] + columnas[::2][::-1]
    generar(CARPETA / "certificado70_orden_distinto.pdf", otro_orden)
    print(f"PDFs generados en {CARPETA}")


if __name__ == "__main__":
    main()
