"""Modelo de Qt para la tabla de calificaciones (Model-View)."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from servicios.calificaciones import entero_a_texto, fecha_a_texto, fecha_hora_a_texto
from servicios.entidades import Calificacion

COLUMNAS = ["Ejercicio", "Instrumento", "Fecha de pago", "Descripción", "Secuencia", "Origen", "Modificado"]
_NUMERICAS = {0, 4}


class ModeloCalificaciones(QAbstractTableModel):
    def __init__(self, nombres_corredor: dict[int, str] | None = None, padre=None):
        """Si se entregan `nombres_corredor` (admin), se agrega la columna Corredor."""
        super().__init__(padre)
        self._filas: list[Calificacion] = []
        self._nombres_corredor = nombres_corredor
        self._columnas = COLUMNAS + (["Corredor"] if nombres_corredor is not None else [])

    def establecer(self, calificaciones: list[Calificacion]) -> None:
        self.beginResetModel()
        self._filas = list(calificaciones)
        self.endResetModel()

    def calificaciones(self) -> list[Calificacion]:
        return list(self._filas)

    def calificacion(self, fila: int) -> Calificacion:
        return self._filas[fila]

    def rowCount(self, padre=QModelIndex()):
        return 0 if padre.isValid() else len(self._filas)

    def columnCount(self, padre=QModelIndex()):
        return 0 if padre.isValid() else len(self._columnas)

    def headerData(self, seccion, orientacion, rol=Qt.ItemDataRole.DisplayRole):
        if rol == Qt.ItemDataRole.DisplayRole and orientacion == Qt.Orientation.Horizontal:
            return self._columnas[seccion]
        return None

    def data(self, indice, rol=Qt.ItemDataRole.DisplayRole):
        if not indice.isValid():
            return None
        c = self._filas[indice.row()]
        columna = indice.column()
        if rol == Qt.ItemDataRole.DisplayRole:
            return self._texto(c, columna)
        if rol == Qt.ItemDataRole.TextAlignmentRole and columna in _NUMERICAS:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if rol == Qt.ItemDataRole.ToolTipRole and columna == 5 and c.origen == "BOLSA":
            return "Calificación de bolsa: si la modifica, se crea su copia local."
        return None

    def _texto(self, c: Calificacion, columna: int) -> str:
        valores = (
            str(c.ejercicio),
            c.instrumento,
            fecha_a_texto(c.fecha_pago),
            c.descripcion or "",
            entero_a_texto(c.secuencia),
            c.origen,
            fecha_hora_a_texto(c.modificado_en),
        )
        if columna < len(valores):
            return valores[columna]
        if c.corredor_id is None:
            return "Bolsa"
        return self._nombres_corredor.get(c.corredor_id, str(c.corredor_id))
