"""Inicializa la base y crea usuarios.

    python scripts/inicializar_bd.py init
    python scripts/inicializar_bd.py crear-usuario

Las contraseñas se piden por consola (getpass); nunca están en el código.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from datos.conexion import crear_conexion  # noqa: E402
from datos.repositorios import RepositorioAuditoria, RepositorioUsuarios  # noqa: E402
from servicios.auth import ServicioAuth  # noqa: E402
from servicios.errores import ErrorNegocio  # noqa: E402

CORREDOR_EJEMPLO = "Corredor de ejemplo"


def _pedir_clave() -> str:
    while True:
        clave = getpass.getpass("Contraseña (mín. 8 caracteres): ")
        if clave != getpass.getpass("Repita la contraseña: "):
            print("Las contraseñas no coinciden.")
        elif len(clave) < 8:
            print("La contraseña debe tener al menos 8 caracteres.")
        else:
            return clave


def _servicio() -> ServicioAuth:
    conexion = crear_conexion(config.RUTA_BD)
    return ServicioAuth(conexion, RepositorioUsuarios(conexion), RepositorioAuditoria(conexion))


def comando_init() -> None:
    auth = _servicio()
    auth.obtener_o_crear_corredor(CORREDOR_EJEMPLO)
    print(f"Base lista en {config.RUTA_BD}. Corredor '{CORREDOR_EJEMPLO}' disponible.")
    if auth.repo_usuarios.obtener_por_nombre("admin") is not None:
        print("El usuario 'admin' ya existe; no se modifica.")
        return
    print("Cree la contraseña del usuario 'admin'.")
    auth.crear_usuario("admin", _pedir_clave(), "admin", None)
    print("Usuario 'admin' creado.")


def comando_crear_usuario() -> None:
    auth = _servicio()
    nombre = input("Nombre de usuario: ").strip()
    rol = ""
    while rol not in config.ROLES:
        rol = input(f"Rol ({'/'.join(config.ROLES)}): ").strip().lower()
    corredor_id = None
    if rol != "admin":
        existentes = auth.repo_usuarios.listar_corredores()
        if existentes:
            print("Corredores existentes: " + ", ".join(c["nombre"] for c in existentes))
        nombre_corredor = input("Corredor (si no existe, se crea): ").strip()
        corredor_id = auth.obtener_o_crear_corredor(nombre_corredor)
    auth.crear_usuario(nombre, _pedir_clave(), rol, corredor_id)
    print(f"Usuario '{nombre}' creado con rol {rol}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicializa la base de calificaciones NUAM.")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("init", help="Crea la base, un corredor de ejemplo y el usuario admin.")
    sub.add_parser("crear-usuario", help="Crea un usuario (admin, corredor o consulta).")
    argumentos = parser.parse_args()
    try:
        if argumentos.comando == "init":
            comando_init()
        else:
            comando_crear_usuario()
    except ErrorNegocio as error:
        print(f"Error: {error}")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
