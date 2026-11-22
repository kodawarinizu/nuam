"""Repositorios: acceso a datos con SQL parametrizado, sin reglas de negocio.

Los repositorios no hacen commit: cada servicio envuelve la operación y su
registro de auditoría en `with conexion:`.
"""

import json
import sqlite3

CAMPOS_CALIFICACION = (
    "corredor_id", "ejercicio", "mercado", "instrumento", "fecha_pago",
    "secuencia", "numero_dividendo", "tipo_sociedad", "valor_historico",
    "descripcion", "origen", "creado_en", "modificado_en",
)
# El upsert no toca la llave ni creado_en.
_CAMPOS_ACTUALIZABLES = tuple(
    c for c in CAMPOS_CALIFICACION
    if c not in ("corredor_id", "ejercicio", "mercado", "instrumento", "secuencia", "creado_en")
)
_DESTINO_CORREDOR = (
    "(corredor_id, ejercicio, mercado, instrumento, secuencia) WHERE corredor_id IS NOT NULL"
)
_DESTINO_BOLSA = "(ejercicio, mercado, instrumento, secuencia) WHERE corredor_id IS NULL"


def _a_dict(fila: sqlite3.Row | None) -> dict | None:
    return dict(fila) if fila is not None else None


def _filtros_sql(filtros: dict | None) -> tuple[str, list]:
    """Convierte {ejercicio, mercado, origen} en condiciones AND parametrizadas."""
    condiciones, parametros = [], []
    for campo in ("ejercicio", "mercado", "origen"):
        valor = (filtros or {}).get(campo)
        if valor is not None:
            condiciones.append(f"{campo} = ?")
            parametros.append(valor)
    sql = "".join(f" AND {c}" for c in condiciones)
    return sql, parametros


_ORDEN = " ORDER BY ejercicio DESC, mercado, instrumento, secuencia"


class RepositorioUsuarios:
    def __init__(self, conexion: sqlite3.Connection):
        self.conexion = conexion

    def crear_corredor(self, nombre: str) -> int:
        cursor = self.conexion.execute("INSERT INTO corredor (nombre) VALUES (?)", (nombre,))
        return cursor.lastrowid

    def obtener_corredor_por_nombre(self, nombre: str) -> dict | None:
        fila = self.conexion.execute(
            "SELECT id, nombre FROM corredor WHERE nombre = ?", (nombre,)
        ).fetchone()
        return _a_dict(fila)

    def listar_corredores(self) -> list[dict]:
        filas = self.conexion.execute("SELECT id, nombre FROM corredor ORDER BY nombre")
        return [dict(f) for f in filas]

    def crear(self, nombre: str, hash_clave: str, sal: str, rol: str,
              corredor_id: int | None) -> int:
        cursor = self.conexion.execute(
            "INSERT INTO usuario (nombre, hash, sal, rol, corredor_id) VALUES (?, ?, ?, ?, ?)",
            (nombre, hash_clave, sal, rol, corredor_id),
        )
        return cursor.lastrowid

    def obtener_por_nombre(self, nombre: str) -> dict | None:
        fila = self.conexion.execute(
            "SELECT id, nombre, hash, sal, rol, corredor_id, activo FROM usuario WHERE nombre = ?",
            (nombre,),
        ).fetchone()
        return _a_dict(fila)

    def hay_usuarios(self) -> bool:
        return self.conexion.execute("SELECT 1 FROM usuario LIMIT 1").fetchone() is not None


class RepositorioCalificaciones:
    def __init__(self, conexion: sqlite3.Connection):
        self.conexion = conexion

    def guardar(self, datos: dict, detalle: dict[int, tuple[int | None, str | None]]) -> int:
        """Inserta o actualiza por llave (según el ámbito) y reemplaza el detalle.

        `detalle` es {columna: (monto, factor_texto)}. Devuelve el id.
        """
        columnas = ", ".join(CAMPOS_CALIFICACION)
        marcas = ", ".join("?" for _ in CAMPOS_CALIFICACION)
        asignaciones = ", ".join(f"{c} = excluded.{c}" for c in _CAMPOS_ACTUALIZABLES)
        destino = _DESTINO_BOLSA if datos["corredor_id"] is None else _DESTINO_CORREDOR
        sql = (
            f"INSERT INTO calificacion ({columnas}) VALUES ({marcas}) "
            f"ON CONFLICT {destino} DO UPDATE SET {asignaciones} RETURNING id"
        )
        filas = self.conexion.execute(sql, [datos[c] for c in CAMPOS_CALIFICACION]).fetchall()
        calificacion_id = filas[0][0]

        self.conexion.execute(
            "DELETE FROM calificacion_detalle WHERE calificacion_id = ?", (calificacion_id,)
        )
        self.conexion.executemany(
            "INSERT INTO calificacion_detalle (calificacion_id, columna, monto, factor) "
            "VALUES (?, ?, ?, ?)",
            [(calificacion_id, col, monto, factor)
             for col, (monto, factor) in sorted(detalle.items())],
        )
        return calificacion_id

    def obtener_por_id(self, calificacion_id: int) -> dict | None:
        fila = self.conexion.execute(
            "SELECT * FROM calificacion WHERE id = ?", (calificacion_id,)
        ).fetchone()
        return _a_dict(fila)

    def obtener_por_llave(self, corredor_id: int | None, ejercicio: int, mercado: str,
                          instrumento: str, secuencia: int) -> dict | None:
        """Con `corredor_id` None busca en bolsa (`IS` compara bien los NULL)."""
        fila = self.conexion.execute(
            "SELECT * FROM calificacion WHERE corredor_id IS ? AND ejercicio = ? "
            "AND mercado = ? AND instrumento = ? AND secuencia = ?",
            (corredor_id, ejercicio, mercado, instrumento, secuencia),
        ).fetchone()
        return _a_dict(fila)

    def obtener_detalle(self, calificacion_id: int) -> dict[int, tuple[int | None, str | None]]:
        filas = self.conexion.execute(
            "SELECT columna, monto, factor FROM calificacion_detalle "
            "WHERE calificacion_id = ? ORDER BY columna",
            (calificacion_id,),
        )
        return {f["columna"]: (f["monto"], f["factor"]) for f in filas}

    def buscar_vista_corredor(self, corredor_id: int, filtros: dict | None = None) -> list[dict]:
        """Calificaciones del corredor más las de bolsa cuya llave el corredor no tenga."""
        sql_filtros, parametros = _filtros_sql(filtros)
        sql = (
            f"SELECT * FROM calificacion WHERE corredor_id = ?{sql_filtros} "
            "UNION ALL "
            f"SELECT * FROM calificacion AS b WHERE b.corredor_id IS NULL{sql_filtros} "
            "AND NOT EXISTS (SELECT 1 FROM calificacion AS p WHERE p.corredor_id = ? "
            "AND p.ejercicio = b.ejercicio AND p.mercado = b.mercado "
            "AND p.instrumento = b.instrumento AND p.secuencia = b.secuencia)"
            + _ORDEN
        )
        filas = self.conexion.execute(
            sql, [corredor_id, *parametros, *parametros, corredor_id]
        )
        return [dict(f) for f in filas]

    def buscar_por_ambito(self, corredor_id: int | None, filtros: dict | None = None) -> list[dict]:
        """Solo las calificaciones propias de un ámbito (un corredor, o bolsa si es None)."""
        sql_filtros, parametros = _filtros_sql(filtros)
        filas = self.conexion.execute(
            f"SELECT * FROM calificacion WHERE corredor_id IS ?{sql_filtros}" + _ORDEN,
            [corredor_id, *parametros],
        )
        return [dict(f) for f in filas]

    def buscar_todas(self, filtros: dict | None = None) -> list[dict]:
        """Para el admin: bolsa y todos los corredores."""
        sql_filtros, parametros = _filtros_sql(filtros)
        filas = self.conexion.execute(
            f"SELECT * FROM calificacion WHERE 1 = 1{sql_filtros}" + _ORDEN, parametros
        )
        return [dict(f) for f in filas]

    def eliminar(self, calificacion_id: int) -> None:
        self.conexion.execute("DELETE FROM calificacion WHERE id = ?", (calificacion_id,))


class RepositorioAuditoria:
    def __init__(self, conexion: sqlite3.Connection):
        self.conexion = conexion

    def registrar(self, fecha: str, usuario_id: int | None, accion: str,
                  tabla: str | None = None, registro_id: int | None = None,
                  detalle: dict | None = None) -> int:
        texto = json.dumps(detalle, ensure_ascii=False, default=str) if detalle is not None else None
        cursor = self.conexion.execute(
            "INSERT INTO log_auditoria (fecha, usuario_id, accion, tabla, registro_id, detalle) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (fecha, usuario_id, accion, tabla, registro_id, texto),
        )
        return cursor.lastrowid

    def listar(self) -> list[dict]:
        filas = self.conexion.execute("SELECT * FROM log_auditoria ORDER BY id")
        resultado = []
        for fila in filas:
            registro = dict(fila)
            registro["detalle"] = json.loads(registro["detalle"]) if registro["detalle"] else None
            resultado.append(registro)
        return resultado
