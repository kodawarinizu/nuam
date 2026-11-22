"""Exportación de calificaciones a CSV (módulo csv) o Excel (xlwings)."""

import logging
from datetime import date
from pathlib import Path

import config
from datos.repositorios import RepositorioAuditoria, RepositorioCalificaciones
from infraestructura.formato_carga import ENCABEZADOS_EXPORTACION
from infraestructura.numeros import decimal_a_texto, fecha_a_texto
from servicios.auth import ahora, requiere_permiso
from servicios.calificaciones import desde_bd
from servicios.entidades import Calificacion, Usuario
from servicios.errores import ErrorNegocio, PermisoDenegado, ValidacionError

log = logging.getLogger(__name__)

EXTENSIONES = (".csv", ".xlsx", ".xls")
_INDICE_FECHA = ENCABEZADOS_EXPORTACION.index("Fecha")
_PRIMER_FACTOR = ENCABEZADOS_EXPORTACION.index(f"Factor {config.COLUMNAS.start}")


def calificaciones_a_filas(calificaciones: list[Calificacion], para_excel: bool) -> list[list]:
    """CSV: texto en formato chileno. Excel: valores tipados (fecha y número).

    En Excel el factor se escribe como número (float) solo en el borde de salida,
    con formato de 8 decimales; los cálculos siempre usan Decimal.
    """
    filas = []
    for c in calificaciones:
        if para_excel:
            fecha = date.fromisoformat(c.fecha_pago)
            factores = [float(c.factores[col]) if col in c.factores else None for col in config.COLUMNAS]
        else:
            fecha = fecha_a_texto(c.fecha_pago)
            factores = [decimal_a_texto(c.factores.get(col)) for col in config.COLUMNAS]
        filas.append([
            c.ejercicio, c.mercado, c.instrumento, fecha, c.secuencia, c.numero_dividendo,
            c.tipo_sociedad or "", c.valor_historico if c.valor_historico is not None else "",
            c.descripcion or "", c.origen, *factores,
        ])
    return filas


class ServicioExportacion:
    def __init__(self, conexion, repo_calificaciones: RepositorioCalificaciones,
                 repo_auditoria: RepositorioAuditoria, reloj=ahora):
        self.conexion = conexion
        self.repo = repo_calificaciones
        self.repo_auditoria = repo_auditoria
        self.reloj = reloj

    def _completa(self, usuario: Usuario, c: Calificacion) -> Calificacion:
        """Relee la calificación desde la base (con detalle) y verifica que el usuario la pueda ver."""
        fila = self.repo.obtener_por_id(c.id)
        if fila is None:
            raise ErrorNegocio(f"La calificación de {c.instrumento} ya no existe; vuelva a buscar.")
        if usuario.rol != "admin" and fila["corredor_id"] not in (None, usuario.corredor_id):
            raise PermisoDenegado("No puede exportar calificaciones de otro corredor.")
        return desde_bd(fila, self.repo.obtener_detalle(c.id))

    def exportar(self, usuario: Usuario, calificaciones: list[Calificacion], ruta: str) -> int:
        """El formato lo da la extensión (.csv, .xlsx, .xls). Devuelve la cantidad exportada."""
        requiere_permiso(usuario, "exportar")
        extension = Path(ruta).suffix.lower()
        if extension not in EXTENSIONES:
            raise ValidacionError(f"Formato no soportado: '{extension}' (use .csv, .xlsx o .xls).")
        completas = [self._completa(usuario, c) for c in calificaciones]

        if extension == ".csv":
            from infraestructura import lector_csv
            lector_csv.escribir(ruta, ENCABEZADOS_EXPORTACION, calificaciones_a_filas(completas, False))
        else:
            from infraestructura import lector_excel
            formatos = {_INDICE_FECHA: "dd-mm-yyyy"}
            formatos |= {_PRIMER_FACTOR + i: "0.00000000" for i in range(len(config.COLUMNAS))}
            lector_excel.escribir(ruta, ENCABEZADOS_EXPORTACION,
                                  calificaciones_a_filas(completas, True), formatos)

        with self.conexion:
            self.repo_auditoria.registrar(self.reloj(), usuario.id, "EXPORTACION", "calificacion", None,
                                          {"archivo": Path(ruta).name, "formato": extension,
                                           "cantidad": len(completas)})
        log.info("Exportación de %s calificaciones (%s)", len(completas), extension)
        return len(completas)
