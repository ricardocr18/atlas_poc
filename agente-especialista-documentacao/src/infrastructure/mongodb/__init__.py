# SEM o __init__.py com conteúdo — importação verbosa, expõe detalhes internos:
from src.infrastructure.mongodb.client import get_database
from src.infrastructure.mongodb.repositories import (
    ComponentesMetadadosRepository,
    DocumentosPreViasRepository,
)

__all__ = [
    "get_database",
    "ComponentesMetadadosRepository",
    "DocumentosPreViasRepository",
]