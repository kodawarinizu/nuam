"""Log técnico de la aplicación.

Prohibido registrar montos, factores o contraseñas aquí (eso va, si corresponde,
a log_auditoria en la base).
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config


def configurar_logging(ruta: str = config.RUTA_LOGS) -> None:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    manejador = RotatingFileHandler(ruta, maxBytes=config.LOG_MAX_BYTES,
                                    backupCount=config.LOG_BACKUPS, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(manejador)
