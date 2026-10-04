"""
infrastructure/mongodb/client.py
---------------------------------
Gerenciador de conexão com o MongoDB.

Responsabilidade única: criar, manter e fechar a conexão com o banco.
Nenhuma regra de negócio aqui — apenas infraestrutura.

Padrão utilizado: Context Manager (with statement) para garantir que
a conexão seja sempre fechada, mesmo em caso de exceção. Esse padrão
é o mesmo utilizado com arquivos, sessões HTTP, etc.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.settings import get_settings

logger = logging.getLogger(__name__)


@contextmanager
def get_database() -> Generator[Database, None, None]:
    """
    Context manager que fornece uma conexão ativa com o banco MongoDB.

    Uso:
        with get_database() as db:
            collection = db["minha_collection"]
            collection.insert_one({...})

    O bloco `finally` garante que o cliente é sempre fechado,
    independente de sucesso ou falha dentro do `with`.

    Raises:
        ConnectionFailure: se o MongoDB não estiver acessível.
        ServerSelectionTimeoutError: se o timeout de conexão expirar.
    """
    settings = get_settings()
    client: MongoClient | None = None

    try:
        logger.info("Conectando ao MongoDB em: %s", settings.mongodb_uri)

        client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,  # 5 segundos para falhar rápido
            connectTimeoutMS=5000,
        )

        # Força a verificação da conexão antes de prosseguir.
        # O MongoClient é lazy — sem isso, erros só aparecem na primeira query.
        client.admin.command("ping")
        logger.info("Conexão com MongoDB estabelecida com sucesso.")

        database = client[settings.mongodb_database]
        yield database

    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error(
            "Falha ao conectar ao MongoDB '%s': %s",
            settings.mongodb_uri,
            str(exc),
        )
        raise

    finally:
        if client is not None:
            client.close()
            logger.info("Conexão com MongoDB encerrada.")