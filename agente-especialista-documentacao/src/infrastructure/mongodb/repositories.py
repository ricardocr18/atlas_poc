"""
infrastructure/mongodb/repositories.py
----------------------------------------
Repositórios para as collections do MongoDB.

Padrão Repository: cada classe encapsula todas as operações de
persistência de uma collection específica. O restante da aplicação
(agente, nós do LangGraph) nunca faz queries diretas ao banco —
sempre passa por aqui.

Vantagem: se precisarmos trocar o MongoDB por outro banco,
ou adicionar cache, só mudamos os repositórios. O agente não sabe
e não precisa saber como os dados são armazenados.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.results import InsertOneResult

logger = logging.getLogger(__name__)

# Nomes das collections — centralizados aqui para evitar typos espalhados
COLLECTION_METADADOS = "componentes_catalogados_metadados"
COLLECTION_PREVIAS = "documentos_gerados_previas"


class ComponentesMetadadosRepository:
    """
    Repositório para a collection 'componentes_catalogados_metadados'.

    Responsável por armazenar os metadados estruturados de componentes
    após o processamento pelo agente de catalogação.
    """

    def __init__(self, database: Database) -> None:
        self._collection: Collection = database[COLLECTION_METADADOS]
        logger.debug("Repositório '%s' inicializado.", COLLECTION_METADADOS)

    def inserir(self, metadados: dict[str, Any]) -> str:
        """
        Insere um documento de metadados na collection.

        Adiciona automaticamente campos de controle:
        - created_at: timestamp de criação (UTC)
        - updated_at: timestamp da última atualização (UTC)
        - schema_version: versão do schema para compatibilidade futura

        Returns:
            str: ID do documento inserido (ObjectId como string)
        """
        documento = {
            **metadados,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "schema_version": "1.0",
        }

        resultado: InsertOneResult = self._collection.insert_one(documento)
        doc_id = str(resultado.inserted_id)

        logger.info(
            "Metadados inseridos em '%s' com ID: %s",
            COLLECTION_METADADOS,
            doc_id,
        )
        return doc_id

    def buscar_por_component_name(self, component_name: str) -> dict[str, Any] | None:
        """
        Busca um componente pelo nome na collection de metadados.

        Returns:
            dict com o documento encontrado, ou None se não existir.
        """
        resultado = self._collection.find_one(
            {"component_name": component_name},
            {"_id": 0},  # Exclui o _id do retorno para serialização simples
        )

        if resultado:
            logger.info("Componente '%s' encontrado.", component_name)
        else:
            logger.warning("Componente '%s' não encontrado.", component_name)

        return resultado

    def listar_todos(self) -> list[dict[str, Any]]:
        """
        Lista todos os documentos da collection (sem o campo _id).
        Usado principalmente para validação e testes.
        """
        return list(self._collection.find({}, {"_id": 0}))


class DocumentosPreViasRepository:
    """
    Repositório para a collection 'documentos_gerados_previas'.

    Responsável por armazenar as prévias de documentação geradas
    pelo agente antes da aprovação e publicação final.
    """

    def __init__(self, database: Database) -> None:
        self._collection: Collection = database[COLLECTION_PREVIAS]
        logger.debug("Repositório '%s' inicializado.", COLLECTION_PREVIAS)

    def inserir(self, previa: dict[str, Any]) -> str:
        """
        Insere uma prévia de documentação na collection.

        Adiciona automaticamente:
        - created_at: timestamp de criação (UTC)
        - status: estado inicial da prévia ('pendente_revisao')
        - schema_version: versão do schema

        Returns:
            str: ID do documento inserido (ObjectId como string)
        """
        documento = {
            **previa,
            "created_at": datetime.now(timezone.utc),
            "status": "pendente_revisao",
            "schema_version": "1.0",
        }

        resultado: InsertOneResult = self._collection.insert_one(documento)
        doc_id = str(resultado.inserted_id)

        logger.info(
            "Prévia inserida em '%s' com ID: %s",
            COLLECTION_PREVIAS,
            doc_id,
        )
        return doc_id

    def buscar_por_event_id(self, event_id: str) -> dict[str, Any] | None:
        """
        Busca uma prévia pelo event_id do processamento.

        Returns:
            dict com o documento encontrado, ou None se não existir.
        """
        resultado = self._collection.find_one(
            {"event_id": event_id},
            {"_id": 0},
        )

        if resultado:
            logger.info("Prévia para event_id '%s' encontrada.", event_id)
        else:
            logger.warning("Prévia para event_id '%s' não encontrada.", event_id)

        return resultado

    def listar_todos(self) -> list[dict[str, Any]]:
        """
        Lista todas as prévias da collection (sem o campo _id).
        """
        return list(self._collection.find({}, {"_id": 0}))