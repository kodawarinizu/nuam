"""Excepciones de negocio."""


class ErrorNegocio(Exception):
    """Error esperado que se muestra al usuario."""


class ValidacionError(ErrorNegocio):
    """Dato inválido. `campo` indica qué campo corregir (si se conoce)."""

    def __init__(self, mensaje: str, campo: str | None = None):
        super().__init__(mensaje)
        self.campo = campo


class PermisoDenegado(ErrorNegocio):
    """El usuario no tiene permiso para la operación."""


class CredencialesInvalidas(ErrorNegocio):
    """Usuario o contraseña incorrectos."""


class ArchivoInvalido(ErrorNegocio):
    """El archivo no se puede leer o no tiene el formato esperado."""
