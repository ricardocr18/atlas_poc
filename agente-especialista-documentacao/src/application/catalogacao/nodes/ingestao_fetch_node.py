"""
nodes/ingestao_fetch_node.py
--------------------------------
Primeiro nó do grafo (Fase 8, atualizado na Fase 10) — busca o
contexto do componente no MongoDB do atlas-apis-ingestao.

Fase 10: fonte trocada de document_context para ingestion_payloads.
A chave de estado continua se chamando 'document_context' de propósito
— é o nome interno que documentation_node, cataloging_node e os
prompts já esperam, e a estrutura de dados central é a mesma entre as
duas collections (só muda a origem e os campos de diagnóstico, que não
são usados ainda).

Este nó não usa LLM — é busca determinística de dados, mesma natureza
dos nós de persistência (infraestrutura, não geração).

Descoberta manual (Fase 8): o component_name vem fixo do .env. Um
mecanismo automático (polling periódico no MongoDB, ou consumo de
evento Kafka publicado pelo atlas-apis-ingestao) fica para uma fase
futura, quando o volume ou a necessidade justificar a automação.
"""

import logging
from typing import Any

from src.application.state import DocumentacaoState
from src.infrastructure.ingestao_api import (
    IngestionPayloadsRepository,
    get_ingestao_database,
)

logger = logging.getLogger(__name__)


def ingestao_fetch_node(state: DocumentacaoState) -> dict[str, Any]:
    """
    Busca o payload de ingestão do componente no MongoDB de ingestão.

    Args:
        state: Estado atual com component_name preenchido

    Returns:
        dict com document_context preenchido (agora a partir de
        ingestion_payloads), ou erro no estado se o componente não for
        encontrado ou a conexão falhar
    """
    logger.info("=" * 55)
    logger.info("[ingestao_fetch_node] Buscando contexto do componente")
    logger.info("=" * 55)

    component_name = state["component_name"]
    erros = list(state.get("erros", []))

    logger.info("[ingestao_fetch_node] component_name: '%s'", component_name)

    try:
        with get_ingestao_database() as db:
            repo = IngestionPayloadsRepository(db)
            document_context = repo.buscar_por_component_name(component_name)

        if not document_context:
            erro = (
                f"Componente '{component_name}' não encontrado em "
                f"atlas_ingestao_api.ingestion_payloads"
            )
            logger.error("[ingestao_fetch_node] ✗ %s", erro)
            erros.append(erro)
            return {
                "erros": erros,
                "status_final": "erro",
                "etapa_atual": "ingestao_fetch_node",
            }

        logger.info(
            "[ingestao_fetch_node] ✓ Componente encontrado: '%s'",
            document_context.get("component_name"),
        )
        logger.info(
            "[ingestao_fetch_node] ✓ Categoria: '%s' | Status: '%s'",
            document_context.get("classification", {}).get("application_type"),
            document_context.get("status"),
        )
        logger.info(
            "[ingestao_fetch_node] ✓ Criticidade: '%s'",
            document_context.get("quality", {}).get("criticality"),
        )
        logger.info(
            "[ingestao_fetch_node] ✓ Completude da ingestão: '%s'",
            document_context.get("completeness", {}).get("status"),
        )
        logger.info(
            "[ingestao_fetch_node] ✓ Busca concluída — seguindo para input_node"
        )

        return {
            "document_context": document_context,
            "erros": erros,
            "etapa_atual": "ingestao_fetch_node",
        }

    except Exception as exc:
        erro = f"Erro ao buscar componente '{component_name}': {str(exc)}"
        logger.error("[ingestao_fetch_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "ingestao_fetch_node",
        }