"""
infrastructure/postgresql
---------------------------
Módulo de infraestrutura PostgreSQL.

Fase 11: expõe o CatalogoRepository (schema normalizado de 7 tabelas)
no lugar do antigo ObjetosGeradosPreViasRepository.
"""

from src.infrastructure.postgresql.client import get_connection
from src.infrastructure.postgresql.repositories import CatalogoRepository

__all__ = [
    "get_connection",
    "CatalogoRepository",
]