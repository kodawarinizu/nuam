"""Autenticación (PBKDF2) y control de acceso por rol (RBAC)."""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime

import config
from datos.repositorios import RepositorioAuditoria, RepositorioUsuarios
from servicios.entidades import Usuario
from servicios.errores import CredencialesInvalidas, PermisoDenegado, ValidacionError

log = logging.getLogger(__name__)

PERMISOS = {
    "admin": {"ver", "crear", "modificar", "eliminar", "cargar", "exportar"},
    "corredor": {"ver", "crear", "modificar", "eliminar", "cargar", "exportar"},
    "consulta": {"ver", "exportar"},
}
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."
LARGO_MINIMO_CLAVE = 8


class _NoElegido:
    def __repr__(self):
        return "NO_ELEGIDO"


# Distingue "el admin no eligió nada" de "eligió Bolsa" (None).
NO_ELEGIDO = _NoElegido()


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def generar_hash(clave: str, iteraciones: int = config.PBKDF2_ITERACIONES,
                 sal: bytes | None = None) -> tuple[str, str]:
    """Devuelve (hash, sal) en texto. El hash guarda las iteraciones: "600000$<hex>"."""
    sal = sal if sal is not None else secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones)
    return f"{iteraciones}${derivada.hex()}", sal.hex()


def verificar_clave(clave: str, hash_guardado: str, sal_hex: str) -> bool:
    iteraciones_texto, _ = hash_guardado.split("$", 1)
    calculado, _ = generar_hash(clave, int(iteraciones_texto), bytes.fromhex(sal_hex))
    return hmac.compare_digest(calculado, hash_guardado)


def puede(usuario: Usuario, accion: str) -> bool:
    return accion in PERMISOS.get(usuario.rol, set())


def requiere_rol(usuario: Usuario, *roles: str) -> None:
    if usuario.rol not in roles:
        raise PermisoDenegado("No tiene permiso para esta operación.")


def requiere_permiso(usuario: Usuario, accion: str) -> None:
    if not puede(usuario, accion):
        raise PermisoDenegado(f"Su rol ({usuario.rol}) no permite {accion}.")


def corredor_efectivo(usuario: Usuario, corredor_elegido=NO_ELEGIDO) -> int | None:
    """Ámbito sobre el que opera el usuario. None = bolsa (solo admin).

    corredor y consulta: siempre el de su usuario (se ignora el elegido).
    admin: el elegido es obligatorio (un corredor o None para bolsa).
    """
    if usuario.rol != "admin":
        return usuario.corredor_id
    if corredor_elegido is NO_ELEGIDO:
        raise ValidacionError("Seleccione un corredor o Bolsa.", campo="corredor")
    return corredor_elegido


def verificar_ambito(usuario: Usuario, corredor_id: int | None) -> None:
    """Solo el admin opera sobre bolsa o sobre otros corredores."""
    if usuario.rol == "admin":
        return
    if corredor_id is None:
        raise PermisoDenegado("Solo el administrador puede modificar calificaciones de bolsa.")
    if corredor_id != usuario.corredor_id:
        raise PermisoDenegado("No puede operar sobre calificaciones de otro corredor.")


class ServicioAuth:
    def __init__(self, conexion, repo_usuarios: RepositorioUsuarios,
                 repo_auditoria: RepositorioAuditoria,
                 iteraciones: int = config.PBKDF2_ITERACIONES, reloj=ahora):
        self.conexion = conexion
        self.repo_usuarios = repo_usuarios
        self.repo_auditoria = repo_auditoria
        self.iteraciones = iteraciones
        self.reloj = reloj

    def iniciar_sesion(self, nombre: str, clave: str) -> Usuario:
        fila = self.repo_usuarios.obtener_por_nombre(nombre.strip())
        if fila is None:
            # Hash de relleno: el tiempo de respuesta no revela si el usuario existe.
            generar_hash(clave, self.iteraciones)
            self._registrar_fallido(None, nombre, "usuario inexistente")
            raise CredencialesInvalidas(MENSAJE_CREDENCIALES)
        if not verificar_clave(clave, fila["hash"], fila["sal"]):
            self._registrar_fallido(fila["id"], nombre, "clave incorrecta")
            raise CredencialesInvalidas(MENSAJE_CREDENCIALES)
        if not fila["activo"]:
            self._registrar_fallido(fila["id"], nombre, "usuario inactivo")
            raise CredencialesInvalidas(MENSAJE_CREDENCIALES)
        usuario = Usuario(fila["id"], fila["nombre"], fila["rol"], fila["corredor_id"], True)
        with self.conexion:
            self.repo_auditoria.registrar(self.reloj(), usuario.id, "LOGIN_OK", "usuario",
                                          usuario.id, {"nombre": usuario.nombre})
        log.info("Inicio de sesión de usuario id=%s", usuario.id)
        return usuario

    def _registrar_fallido(self, usuario_id, nombre: str, motivo: str) -> None:
        with self.conexion:
            self.repo_auditoria.registrar(self.reloj(), usuario_id, "LOGIN_FALLIDO", "usuario",
                                          usuario_id, {"nombre": nombre, "motivo": motivo})
        log.warning("Inicio de sesión fallido (%s)", motivo)

    def crear_usuario(self, nombre: str, clave: str, rol: str,
                      corredor_id: int | None) -> Usuario:
        """Usado por scripts/inicializar_bd.py (no hay pantalla de gestión de usuarios)."""
        nombre = nombre.strip()
        if not nombre:
            raise ValidacionError("El nombre de usuario es obligatorio.", campo="nombre")
        if rol not in config.ROLES:
            raise ValidacionError(f"Rol inválido (válidos: {', '.join(config.ROLES)}).", campo="rol")
        if rol != "admin" and corredor_id is None:
            raise ValidacionError("Los roles corredor y consulta requieren un corredor.", campo="corredor")
        if rol == "admin":
            corredor_id = None
        if len(clave) < LARGO_MINIMO_CLAVE:
            raise ValidacionError(f"La contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres.",
                                  campo="clave")
        if self.repo_usuarios.obtener_por_nombre(nombre) is not None:
            raise ValidacionError(f"Ya existe el usuario '{nombre}'.", campo="nombre")
        hash_clave, sal = generar_hash(clave, self.iteraciones)
        with self.conexion:
            usuario_id = self.repo_usuarios.crear(nombre, hash_clave, sal, rol, corredor_id)
            self.repo_auditoria.registrar(self.reloj(), None, "INSERT", "usuario", usuario_id,
                                          {"nombre": nombre, "rol": rol, "corredor_id": corredor_id})
        return Usuario(usuario_id, nombre, rol, corredor_id)

    def obtener_o_crear_corredor(self, nombre: str) -> int:
        nombre = nombre.strip()
        if not nombre:
            raise ValidacionError("El nombre del corredor es obligatorio.", campo="corredor")
        existente = self.repo_usuarios.obtener_corredor_por_nombre(nombre)
        if existente:
            return existente["id"]
        with self.conexion:
            corredor_id = self.repo_usuarios.crear_corredor(nombre)
            self.repo_auditoria.registrar(self.reloj(), None, "INSERT", "corredor", corredor_id,
                                          {"nombre": nombre})
        return corredor_id

    def listar_corredores(self, usuario: Usuario) -> list[dict]:
        """El admin ve todos; los demás, solo el suyo."""
        corredores = self.repo_usuarios.listar_corredores()
        if usuario.rol == "admin":
            return corredores
        return [c for c in corredores if c["id"] == usuario.corredor_id]

    def hay_usuarios(self) -> bool:
        return self.repo_usuarios.hay_usuarios()
