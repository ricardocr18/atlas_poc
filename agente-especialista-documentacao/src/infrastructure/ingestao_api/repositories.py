"""
infrastructure/ingestao_api/repositories.py
------------------------------------------------
Repositório de LEITURA para a collection ingestion_payloads
(banco atlas_ingestao_api, mantido pelo atlas-apis-ingestao).

Fase 10: fonte trocada de 'document_context' (resumo já curado) para
         'ingestion_payloads' (evento de ingestão bruto/preview). A
         estrutura central dos dados (cmdb, ownership, classification,
         technology, api, integrations, security, observability, data,
         runtime, quality, deployment, jira) é idêntica entre as duas
         collections — 'ingestion_payloads' apenas acrescenta campos de
         diagnóstico (processing, sources, completeness,
         ingestion_diagnostics, ingestion_key, schema_version) que não
         são consumidos pelos prompts no momento.

Descoberta ainda manual (Fase 8), por component_name via .env — isso
não muda nesta fase.

Este repositório é estritamente de LEITURA — nenhum método de escrita
é exposto aqui de propósito, para deixar explícito que este projeto
nunca deve alterar dados de outro serviço.
"""

import logging
from typing import Any

from pymongo.database import Database

logger = logging.getLogger(__name__)

COLLECTION_INGESTION_PAYLOADS = "ingestion_payloads"


class IngestionPayloadsRepository:
    """
    Repositório de leitura para a collection ingestion_payloads.

    Responsável por buscar o payload de ingestão mais recente de um
    componente, a partir do component_name.
    """

    def __init__(self, database: Database) -> None:
        self._collection = database[COLLECTION_INGESTION_PAYLOADS]
        logger.debug(
            "Repositório de leitura '%s' inicializado.", COLLECTION_INGESTION_PAYLOADS
        )

    def buscar_por_component_name(self, component_name: str) -> dict[str, Any] | None:
        """
        Busca o payload de ingestão mais recente de um componente pelo
        nome exato.

        Quando há mais de um documento para o mesmo componente (reenvios,
        novos eventos de deploy), retorna o mais recente por created_at —
        a mesma convenção já usada em exportar_markdown.py para
        documentos_gerados_previas.

        Args:
            component_name: nome do componente, deve bater exatamente
                             com o valor gravado pelo atlas-apis-ingestao

        Returns:
            dict com o documento completo (sem o campo _id do Mongo),
            ou None se nenhum componente com esse nome for encontrado
        """
        resultado = self._collection.find_one(
            {"component_name": component_name},
            {"_id": 0},
            sort=[("created_at", -1)],
        )

        if resultado:
            logger.info(
                "[ingestion_payloads] ✓ Componente '%s' encontrado.", component_name
            )
        else:
            logger.warning(
                "[ingestion_payloads] ✗ Componente '%s' não encontrado "
                "no atlas_ingestao_api.",
                component_name,
            )

        return resultado