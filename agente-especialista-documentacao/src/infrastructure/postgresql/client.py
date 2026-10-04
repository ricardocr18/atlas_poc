"""
infrastructure/postgresql/client.py
--------------------------------------
Gerenciador de conexão com o PostgreSQL.

Segue o mesmo padrão do client.py do MongoDB:
  - Context Manager para abertura e fechamento seguro
  - Conexão testada imediatamente com SELECT 1
  - Erro claro se o banco não estiver acessível

Compatível com dois ambientes:
  Local:    localhost:5432 (PostgreSQL instalado no Windows)
  Sicredi:  atlas-documentacao-agent-pgdb.dev-sicredi.in:5432

SSL mode "prefer":
  Tenta SSL primeiro, aceita sem SSL se não disponível.
  Compatível com o ambiente da Sicredi (AWS RDS) e local.

Uso:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ...")
"""

import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from src.settings import get_settings

logger = logging.getLogger(__name__)


@contextmanager
def get_connection() -> Generator[PgConnection, None, None]:
    """
    Context manager que fornece uma conexão ativa com o PostgreSQL.

    Monta a string de conexão a partir das variáveis do .env.
    O bloco finally garante que a conexão é sempre fechada,
    independente de sucesso ou falha.

    Yields:
        psycopg2 connection ativa e pronta para uso

    Raises:
        psycopg2.OperationalError: se o banco não estiver acessível
    """
    settings = get_settings()
    conn = None

    try:
        logger.info(
            "Conectando ao PostgreSQL em: %s:%s/%s",
            settings.postgres_host,
            settings.postgres_port,
            settings.postgres_database,
        )

        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_database,
            user=settings.postgres_user,
            password=settings.postgres_password,
            sslmode=settings.postgres_sslmode,
            connect_timeout=settings.postgres_connect_timeout,
            # Retorna dicionários em vez de tuplas — mais legível
            cursor_factory=psycopg2.extras.RealDictCursor,
            client_encoding="utf8", 
        )

        # Testa a conexão imediatamente — falha rápida se algo errado
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

        logger.info("Conexão com PostgreSQL estabelecida com sucesso.")
        yield conn

    except psycopg2.OperationalError as exc:
        logger.error(
            "Falha ao conectar ao PostgreSQL '%s:%s': %s",
            settings.postgres_host,
            settings.postgres_port,
            str(exc),
        )
        raise

    finally:
        if conn is not None and not conn.closed:
            conn.close()
            logger.info("Conexão com PostgreSQL encerrada.")