"""
infrastructure/ingestao_api/client.py
----------------------------------------
Gerenciador de conexão com o MongoDB do atlas-apis-ingestao (Fase 8).

Por que uma conexão separada do infrastructure/mongodb/ já existente?
  O infrastructure/mongodb/ é usado para ESCREVER nossos resultados
  (documentos_gerados_previas, componentes_catalogados_metadados) no
  banco atlas_documentacao_agente.

  Este módulo é usado só para LER dados de um banco DIFERENTE
  (atlas_ingestao_api), pertencente a outro serviço da plataforma
  Atlas. São clusters/credenciais distintos, mesmo sendo a mesma
  tecnologia de banco — por isso a separação em módulos diferentes,
  cada um com sua própria string de conexão.

Segue o mesmo padrão de Context Manager já usado no restante do
projeto (infrastructure/mongodb/client.py), garantindo abertura e
fechamento seguros da conexão.
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
def get_ingestao_database() -> Generator[Database, None, None]:
    """
    Context manager que fornece uma conexão ativa com o MongoDB
    do atlas-apis-ingestao (somente leitura, por convenção — nenhum
    código deste projeto deve escrever neste banco).

    Uso:
        with get_ingestao_database() as db:
            collection = db["document_context"]
            collection.find_one({...})

    Raises:
        ConnectionFailure: se o MongoDB não estiver acessível.
        ServerSelectionTimeoutError: se o timeout de conexão expirar.
    """
    settings = get_settings()
    client: MongoClient | None = None

    try:
        logger.info(
            "Conectando ao MongoDB de ingestão em: %s",
            settings.ingestao_mongodb_uri,
        )

        client = MongoClient(
            settings.ingestao_mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )

        client.admin.command("ping")
        logger.info("Conexão com MongoDB de ingestão estabelecida com sucesso.")

        database = client[settings.ingestao_mongodb_database]
        yield database

    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error(
            "Falha ao conectar ao MongoDB de ingestão '%s': %s",
            settings.ingestao_mongodb_uri,
            str(exc),
        )
        raise

    finally:
        if client is not None:
            client.close()
            logger.info("Conexão com MongoDB de ingestão encerrada.")