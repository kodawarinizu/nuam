"""Servicio de calificaciones: búsqueda y CRUD con permisos y auditoría."""

import logging
from dataclasses import asdict, replace
from decimal import Decimal

import config
from datos.repositorios import RepositorioAuditoria, RepositorioCalificaciones
from infraestructura.numeros import (  # noqa: F401  (formato reexportado para la interfaz)
    a_decimal, a_entero, a_fecha, a_texto, decimal_a_texto, entero_a_texto,
    fecha_a_texto, fecha_hora_a_texto,
)
from servicios import factores as modulo_factores
from servicios.auth import NO_ELEGIDO, ahora, corredor_efectivo, requiere_permiso, verificar_ambito
from servicios.entidades import Calificacion, Usuario
from servicios.errores import ErrorNegocio, PermisoDenegado, ValidacionError
from servicios.validaciones import validar_calificacion

log = logging.getLogger(__name__)

TODOS = "TODOS"  # filtro del admin: bolsa y todos los corredores

ETIQUETAS = {
    "ejercicio": "Ejercicio", "mercado": "Mercado", "instrumento": "Instrumento",
    "fecha_pago": "Fecha de pago", "secuencia": "Secuencia",
    "numero_dividendo": "Número de dividendo", "tipo_sociedad": "Tipo de sociedad",
    "valor_historico": "Valor histórico", "descripcion": "Descripción",
}
_CAMPOS_LLAVE = ("ejercicio", "mercado", "instrumento", "secuencia")


def origen_para(corredor_id: int | None, tipo: str) -> str:
    """El origen se deduce del ámbito: BOLSA para bolsa; si no, el tipo (MANUAL, ARCHIVO o PDF)."""
    return "BOLSA" if corredor_id is None else tipo


# ---------- conversión entre formatos ----------

def calificacion_desde_fila(fila: dict) -> Calificacion:
    """Convierte un dict crudo (lectores de archivo o formulario) en Calificacion.

    Claves: ejercicio, mercado, instrumento, fecha_pago, secuencia, numero_dividendo,
    tipo_sociedad, valor_historico, descripcion, monto_N y factor_N.
    """
    def convertir(clave: str, conversor, etiqueta: str | None = None):
        try:
            return conversor(fila.get(clave))
        except ValidacionError as error:
            raise ValidacionError(f"{etiqueta or ETIQUETAS[clave]}: {error}", campo=clave) from None

    montos, factores = {}, {}
    for columna in config.COLUMNAS:
        monto = convertir(f"monto_{columna}", a_entero, f"Monto {columna}")
        if monto is not None:
            montos[columna] = monto
        factor = convertir(f"factor_{columna}", a_decimal, f"Factor {columna}")
        if factor is not None:
            factores[columna] = factor

    return Calificacion(
        ejercicio=convertir("ejercicio", a_entero),
        mercado=a_texto(fila.get("mercado")),
        instrumento=a_texto(fila.get("instrumento")),
        fecha_pago=convertir("fecha_pago", a_fecha),
        secuencia=convertir("secuencia", a_entero),
        numero_dividendo=convertir("numero_dividendo", a_entero) or 0,
        tipo_sociedad=a_texto(fila.get("tipo_sociedad")),
        valor_historico=convertir("valor_historico", a_entero),
        descripcion=a_texto(fila.get("descripcion")),
        montos=montos,
        factores=factores,
    )


def a_datos(c: Calificacion) -> dict:
    """Calificacion → dict de columnas para el repositorio."""
    return {
        "corredor_id": c.corredor_id, "ejercicio": c.ejercicio, "mercado": c.mercado,
        "instrumento": c.instrumento, "fecha_pago": c.fecha_pago, "secuencia": c.secuencia,
        "numero_dividendo": c.numero_dividendo, "tipo_sociedad": c.tipo_sociedad,
        "valor_historico": c.valor_historico, "descripcion": c.descripcion, "origen": c.origen,
        "creado_en": c.creado_en, "modificado_en": c.modificado_en,
    }


def a_detalle(c: Calificacion) -> dict[int, tuple[int | None, str | None]]:
    """Montos y factores → {columna: (monto, factor_texto)}. Factores con 8 decimales fijos."""
    columnas = set(c.montos) | set(c.factores)
    return {
        col: (c.montos.get(col),
              f"{c.factores[col]:.{config.DECIMALES_FACTOR}f}" if col in c.factores else None)
        for col in columnas
    }


def desde_bd(fila: dict, detalle: dict | None = None) -> Calificacion:
    montos, factores = {}, {}
    for columna, (monto, factor) in (detalle or {}).items():
        if monto is not None:
            montos[columna] = monto
        if factor is not None:
            factores[columna] = Decimal(factor)
    return Calificacion(
        id=fila["id"], corredor_id=fila["corredor_id"], ejercicio=fila["ejercicio"],
        mercado=fila["mercado"], instrumento=fila["instrumento"], fecha_pago=fila["fecha_pago"],
        secuencia=fila["secuencia"], numero_dividendo=fila["numero_dividendo"],
        tipo_sociedad=fila["tipo_sociedad"], valor_historico=fila["valor_historico"],
        descripcion=fila["descripcion"], origen=fila["origen"], creado_en=fila["creado_en"],
        modificado_en=fila["modificado_en"], montos=montos, factores=factores,
    )


def _para_auditoria(c: Calificacion) -> dict:
    datos = asdict(c)
    for clave in ("id", "creado_en", "modificado_en"):
        datos.pop(clave)
    datos["montos"] = {str(k): v for k, v in sorted(c.montos.items())}
    datos["factores"] = {str(k): f"{v:.{config.DECIMALES_FACTOR}f}" for k, v in sorted(c.factores.items())}
    return datos


def _llave_auditoria(c: Calificacion) -> dict:
    return {"corredor_id": c.corredor_id, **{k: getattr(c, k) for k in _CAMPOS_LLAVE}}


def _diferencias(antes: Calificacion, despues: Calificacion) -> dict:
    a, d = _para_auditoria(antes), _para_auditoria(despues)
    return {campo: [a[campo], d[campo]] for campo in a if a[campo] != d[campo]}


def _factores_finales(c: Calificacion) -> dict[int, Decimal]:
    """Con montos, los factores 8–33 se recalculan (se ignoran los que traiga la entidad,
    que pueden ser los calculados antes); los 34–37 se conservan.

    La regla "monto y factor en la misma columna" se aplica a la entrada cruda
    (archivos), en la carga masiva.
    """
    if c.montos:
        ingresados = {col: f for col, f in c.factores.items() if col in config.COLUMNAS_SOLO_INGRESO}
    else:
        ingresados = c.factores
    return modulo_factores.preparar_factores(c.montos, ingresados)


# ---------- ayudas para el formulario ----------

def calcular_desde_textos(montos_texto: dict[int, str]) -> dict[int, Decimal]:
    """Botón Calcular: convierte los montos escritos y calcula los factores."""
    montos = {}
    for columna, texto in montos_texto.items():
        try:
            valor = a_entero(texto)
        except ValidacionError as error:
            raise ValidacionError(f"Monto {columna}: {error}", campo=f"monto_{columna}") from None
        if valor is not None:
            montos[columna] = valor
    return modulo_factores.calcular_factores(montos)


def sumar_factores_textos(factores_texto: dict[int, str]) -> Decimal | None:
    """Suma del rango para mostrar; None si algún factor no es un número."""
    try:
        factores = {c: a_decimal(t) for c, t in factores_texto.items()}
    except ValidacionError:
        return None
    return modulo_factores.suma_factores({c: f for c, f in factores.items() if f is not None})


# ---------- servicio ----------

class ServicioCalificaciones:
    def __init__(self, conexion, repo_calificaciones: RepositorioCalificaciones,
                 repo_auditoria: RepositorioAuditoria, reloj=ahora):
        self.conexion = conexion
        self.repo = repo_calificaciones
        self.repo_auditoria = repo_auditoria
        self.reloj = reloj

    def buscar(self, usuario: Usuario, ejercicio: int | None = None, mercado: str | None = None,
               origen: str | None = None, corredor=TODOS) -> list[Calificacion]:
        """Corredor y consulta: su vista (lo suyo más bolsa). Admin: todo, bolsa (None) o un corredor."""
        requiere_permiso(usuario, "ver")
        filtros = {"ejercicio": ejercicio, "mercado": mercado, "origen": origen}
        if usuario.rol == "admin":
            if corredor == TODOS:
                filas = self.repo.buscar_todas(filtros)
            else:
                filas = self.repo.buscar_por_ambito(corredor, filtros)
        else:
            filas = self.repo.buscar_vista_corredor(usuario.corredor_id, filtros)
        return [desde_bd(f) for f in filas]

    def obtener(self, usuario: Usuario, calificacion_id: int) -> Calificacion:
        """Calificación con su detalle de columnas."""
        requiere_permiso(usuario, "ver")
        fila = self.repo.obtener_por_id(calificacion_id)
        if fila is None:
            raise ErrorNegocio("La calificación ya no existe.")
        if usuario.rol != "admin" and fila["corredor_id"] not in (None, usuario.corredor_id):
            raise PermisoDenegado("No puede ver calificaciones de otro corredor.")
        return desde_bd(fila, self.repo.obtener_detalle(calificacion_id))

    def crear(self, usuario: Usuario, calificacion: Calificacion, corredor=NO_ELEGIDO) -> Calificacion:
        requiere_permiso(usuario, "crear")
        corredor_id = corredor_efectivo(usuario, corredor)
        verificar_ambito(usuario, corredor_id)
        c = replace(calificacion, id=None, corredor_id=corredor_id,
                    origen=origen_para(corredor_id, "MANUAL"))
        validar_calificacion(c)
        c.factores = _factores_finales(c)
        if self.repo.obtener_por_llave(corredor_id, *c.llave()) is not None:
            raise ErrorNegocio("Ya existe una calificación con ese ejercicio, mercado, instrumento "
                               "y secuencia. Use Modificar.")
        c.creado_en = c.modificado_en = self.reloj()
        with self.conexion:
            c.id = self.repo.guardar(a_datos(c), a_detalle(c))
            self.repo_auditoria.registrar(c.modificado_en, usuario.id, "INSERT", "calificacion", c.id,
                                          {"llave": _llave_auditoria(c), "nuevo": _para_auditoria(c)})
        log.info("Calificación creada id=%s", c.id)
        return c

    def modificar(self, usuario: Usuario, calificacion_id: int, nueva: Calificacion) -> Calificacion:
        """`nueva` es el estado completo (cabecera y detalle). La llave no puede cambiar.

        Si un corredor modifica una de bolsa, se crea su copia y bolsa queda intacta.
        """
        requiere_permiso(usuario, "modificar")
        fila = self.repo.obtener_por_id(calificacion_id)
        if fila is None:
            raise ErrorNegocio("La calificación ya no existe.")
        actual = desde_bd(fila, self.repo.obtener_detalle(calificacion_id))

        es_copia = actual.corredor_id is None and usuario.rol != "admin"
        if es_copia:
            destino = usuario.corredor_id
        else:
            verificar_ambito(usuario, actual.corredor_id)
            destino = actual.corredor_id

        c = replace(nueva, id=None, corredor_id=destino, origen=origen_para(destino, "MANUAL"))
        validar_calificacion(c)
        for campo in _CAMPOS_LLAVE:
            if getattr(c, campo) != getattr(actual, campo):
                raise ValidacionError(
                    "No se puede cambiar ejercicio, mercado, instrumento ni secuencia. "
                    "Para cambiarlos, elimine la calificación y créela de nuevo.", campo=campo)
        c.factores = _factores_finales(c)

        momento = self.reloj()
        if es_copia:
            existente = self.repo.obtener_por_llave(destino, *c.llave())
            c.creado_en = existente["creado_en"] if existente else momento
        else:
            c.creado_en = actual.creado_en
        c.modificado_en = momento

        with self.conexion:
            c.id = self.repo.guardar(a_datos(c), a_detalle(c))
            if es_copia:
                self.repo_auditoria.registrar(
                    momento, usuario.id, "INSERT", "calificacion", c.id,
                    {"llave": _llave_auditoria(c), "copia_de_bolsa": actual.id,
                     "nuevo": _para_auditoria(c)})
            else:
                self.repo_auditoria.registrar(
                    momento, usuario.id, "UPDATE", "calificacion", c.id,
                    {"llave": _llave_auditoria(c), "cambios": _diferencias(actual, c)})
        log.info("Calificación %s id=%s", "copiada desde bolsa" if es_copia else "modificada", c.id)
        return c

    def eliminar(self, usuario: Usuario, calificacion_id: int) -> None:
        requiere_permiso(usuario, "eliminar")
        fila = self.repo.obtener_por_id(calificacion_id)
        if fila is None:
            raise ErrorNegocio("La calificación ya no existe.")
        verificar_ambito(usuario, fila["corredor_id"])
        actual = desde_bd(fila, self.repo.obtener_detalle(calificacion_id))
        with self.conexion:
            self.repo_auditoria.registrar(self.reloj(), usuario.id, "DELETE", "calificacion",
                                          calificacion_id,
                                          {"llave": _llave_auditoria(actual),
                                           "anterior": _para_auditoria(actual)})
            self.repo.eliminar(calificacion_id)
        log.info("Calificación eliminada id=%s", calificacion_id)
