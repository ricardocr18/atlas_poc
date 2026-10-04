"""
agent_application/agent_service.py
-------------------------------------
Orquestrador da aplicação — ponto de entrada do grafo LangGraph.

Fase 8: a entrada principal passa a ser um component_name
        (COMPONENT_NAME no .env), buscado manualmente — descoberta
        automática (polling ou Kafka) fica para uma fase futura.
"""

import logging

from src.application.graph import criar_grafo_documentacao
from src.application.state import criar_estado_inicial
from src.settings import get_settings

logger = logging.getLogger(__name__)


def _processar_componente(component_name: str) -> None:
    """
    Executa o grafo completo para um component_name.

    Args:
        component_name: nome do componente a ser buscado e processado
    """
    logger.info("Componente a processar: '%s'", component_name)

    estado_inicial = criar_estado_inicial(component_name)
    grafo = criar_grafo_documentacao()
    estado_final = grafo.invoke(estado_inicial)

    logger.info("")
    logger.info("=" * 60)
    logger.info("RESULTADO FINAL DO GRAFO")
    logger.info("=" * 60)
    logger.info("Status         : %s", estado_final.get("status_final"))
    logger.info("Última etapa   : %s", estado_final.get("etapa_atual"))
    logger.info("ID documentação: %s", estado_final.get("id_mongodb_previa"))
    logger.info("ID checklist   : %s", estado_final.get("id_mongodb_metadados"))
    logger.info("ID postgres    : %s", estado_final.get("id_postgres"))

    erros = estado_final.get("erros", [])
    if erros:
        logger.warning("Avisos/Erros   : %d ocorrência(s)", len(erros))
        for erro in erros:
            logger.warning("  • %s", erro)
    else:
        logger.info("Erros          : nenhum")

    logger.info("=" * 60)


def executar_grafo() -> None:
    """
    Ponto de entrada principal — Fase 8: entrada via atlas_ingestao_api.

    O component_name é lido de COMPONENT_NAME no .env (descoberta
    manual nesta fase). No futuro, esta função poderá ser chamada
    como callback de um consumer Kafka ou de um loop de polling,
    exatamente como já demonstramos com o padrão de callback usado
    desde a Fase 4 — nenhuma mudança estrutural no restante do
    projeto seria necessária.
    """
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("ATLAS DOCUMENTACAO AGENT — FASE 8")
    logger.info("Entrada via atlas_ingestao_api.document_context")
    logger.info("=" * 60)

    _processar_componente(settings.component_name)