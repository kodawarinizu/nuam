"""Carga masiva: lectura de archivos, previsualización y confirmación."""

import logging
from dataclasses import replace
from pathlib import Path

from datos.repositorios import RepositorioAuditoria, RepositorioCalificaciones
from servicios import factores as modulo_factores
from servicios.auth import ahora, requiere_permiso, verificar_ambito
from servicios.calificaciones import a_datos, a_detalle, calificacion_desde_fila, origen_para
from servicios.entidades import FilaInvalida, FilaValida, ResultadoCarga, Usuario
from servicios.errores import ArchivoInvalido, ErrorNegocio, ValidacionError
from servicios.validaciones import validar_calificacion

log = logging.getLogger(__name__)

EXTENSIONES_EXCEL = (".xlsx", ".xls", ".xlsm")
EXTENSIONES_ARCHIVO = (".csv", *EXTENSIONES_EXCEL)


def tipo_de_archivo(ruta: str) -> str:
    """"PDF" o "ARCHIVO" (CSV/Excel), que define el origen de la carga."""
    return "PDF" if Path(ruta).suffix.lower() == ".pdf" else "ARCHIVO"


def requiere_excel(ruta: str) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_EXCEL


def leer_archivo(ruta: str) -> list[dict]:
    """Elige el lector según la extensión. No usa la base, así que puede correr en un hilo."""
    extension = Path(ruta).suffix.lower()
    if extension == ".csv":
        from infraestructura import lector_csv
        return lector_csv.leer(ruta)
    if extension in EXTENSIONES_EXCEL:
        from infraestructura import lector_excel
        return lector_excel.leer(ruta)
    if extension == ".pdf":
        from infraestructura import lector_pdf
        return lector_pdf.leer(ruta)
    raise ArchivoInvalido(f"Extensión no soportada: '{extension}' (use .csv, .xlsx, .xls, .xlsm o .pdf).")


class ServicioCargaMasiva:
    def __init__(self, conexion, repo_calificaciones: RepositorioCalificaciones,
                 repo_auditoria: RepositorioAuditoria, reloj=ahora):
        self.conexion = conexion
        self.repo = repo_calificaciones
        self.repo_auditoria = repo_auditoria
        self.reloj = reloj

    def previsualizar(self, filas: list[dict], corredor_id: int | None,
                      tipo_archivo: str = "ARCHIVO") -> ResultadoCarga:
        """Normaliza, valida y marca cada fila como "nueva" o "actualiza" dentro del ámbito."""
        resultado = ResultadoCarga(corredor_id)
        llaves_vistas: dict[tuple, int] = {}
        for indice, fila in enumerate(filas):
            numero = fila.get("_fila", indice + 2)  # fila 1 = encabezados
            try:
                c = calificacion_desde_fila(fila)
                c.corredor_id = corredor_id
                c.origen = origen_para(corredor_id, tipo_archivo)
                validar_calificacion(c)
                c.factores = modulo_factores.preparar_factores(c.montos, c.factores)
            except ValidacionError as error:
                resultado.invalidas.append(FilaInvalida(numero, str(error)))
                continue
            llave = c.llave()
            if llave in llaves_vistas:
                resultado.invalidas.append(FilaInvalida(
                    numero, f"Llave repetida en el archivo (igual a la fila {llaves_vistas[llave]})."))
                continue
            llaves_vistas[llave] = numero
            existe = self.repo.obtener_por_llave(corredor_id, *llave) is not None
            resultado.validas.append(FilaValida(numero, c, "actualiza" if existe else "nueva"))
        return resultado

    def confirmar(self, usuario: Usuario, resultado: ResultadoCarga, tipo_archivo: str) -> dict:
        """Guarda las filas válidas en una sola transacción. El origen se deduce del ámbito."""
        requiere_permiso(usuario, "cargar")
        verificar_ambito(usuario, resultado.corredor_id)
        if not resultado.validas:
            raise ErrorNegocio("No hay filas válidas para cargar.")
        origen = origen_para(resultado.corredor_id, tipo_archivo)
        momento = self.reloj()
        insertadas = actualizadas = 0
        with self.conexion:
            for fila in resultado.validas:
                c = replace(fila.calificacion, id=None, corredor_id=resultado.corredor_id, origen=origen)
                existente = self.repo.obtener_por_llave(resultado.corredor_id, *c.llave())
                c.creado_en = existente["creado_en"] if existente else momento
                c.modificado_en = momento
                self.repo.guardar(a_datos(c), a_detalle(c))
                if existente:
                    actualizadas += 1
                else:
                    insertadas += 1
            resumen = {"origen": origen, "corredor_id": resultado.corredor_id,
                       "insertadas": insertadas, "actualizadas": actualizadas,
                       "invalidas": len(resultado.invalidas)}
            self.repo_auditoria.registrar(momento, usuario.id, "CARGA_MASIVA", "calificacion",
                                          None, resumen)
        log.info("Carga masiva: %s insertadas, %s actualizadas, %s inválidas",
                 insertadas, actualizadas, len(resultado.invalidas))
        return resumen
