"""
infrastructure/postgresql
---------------------------
Módulo de infraestrutura PostgreSQL.

Expõe apenas o necessário para o restante da aplicação:
  - get_connection: context manager de conexão
  - ObjetosGeradosPreViasRepository: operações na tabela
"""

from src.infrastructure.postgresql.client import get_connection
from src.infrastructure.postgresql.repositories import ObjetosGeradosPreViasRepository

__all__ = [
    "get_connection",
    "ObjetosGeradosPreViasRepository",
]