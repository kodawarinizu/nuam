"""DTOs del sistema."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Usuario:
    id: int
    nombre: str
    rol: str
    corredor_id: int | None
    activo: bool = True


@dataclass
class Calificacion:
    ejercicio: int | None
    mercado: str | None
    instrumento: str | None
    fecha_pago: str | None          # ISO AAAA-MM-DD
    secuencia: int | None
    corredor_id: int | None = None  # None = bolsa
    numero_dividendo: int = 0
    tipo_sociedad: str | None = None
    valor_historico: int | None = None
    descripcion: str | None = None
    origen: str | None = None
    montos: dict[int, int] = field(default_factory=dict)
    factores: dict[int, Decimal] = field(default_factory=dict)
    id: int | None = None
    creado_en: str | None = None
    modificado_en: str | None = None

    def llave(self) -> tuple:
        """Llave de negocio dentro de un ámbito (bolsa o corredor)."""
        return (self.ejercicio, self.mercado, self.instrumento, self.secuencia)


@dataclass
class FilaInvalida:
    numero_fila: int
    motivo: str


@dataclass
class FilaValida:
    numero_fila: int
    calificacion: Calificacion
    estado: str  # "nueva" o "actualiza"


@dataclass
class ResultadoCarga:
    corredor_id: int | None
    validas: list[FilaValida] = field(default_factory=list)
    invalidas: list[FilaInvalida] = field(default_factory=list)
