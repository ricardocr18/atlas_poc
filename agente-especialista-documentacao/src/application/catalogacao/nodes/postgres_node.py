"""
nodes/postgres_node.py
------------------------
Sexto nó do grafo (Fase 7, reescrito na Fase 11) — persiste o
catálogo normalizado no PostgreSQL.

Fase 11: a tabela única 'objetos_gerados_previas' foi substituída por
         7 tabelas relacionais (application, documentation, document,
         dependencies, application_approver, tag, application_tag).
         Ver docs/decisao-arquitetura-postgresql-normalizado.md.

Diferença em relação à Fase 7/9: este nó agora também lê
state["document_context"] diretamente — vários campos do catálogo
(description, category, repository, default_branch, cmdb, dependencies,
approvers) vêm do payload bruto de ingestão, não do dict `metadados`
(que carrega principalmente o resultado do checklist técnico da LLM).
"""

import logging
from typing import Any

from src.application.state import DocumentacaoState
from src.infrastructure.postgresql import (
    CatalogoRepository,
    get_connection,
)

logger = logging.getLogger(__name__)


def postgres_node(state: DocumentacaoState) -> dict[str, Any]:
    """
    Persiste o catálogo normalizado da rodada atual no PostgreSQL.

    Args:
        state: Estado com document_context, metadados_catalogo,
               secoes_documentacao e id_mongodb_previa já preenchidos

    Returns:
        dict com os IDs gerados nas tabelas do catálogo
    """
    logger.info("-" * 55)
    logger.info("[postgres_node] Iniciando persistência no PostgreSQL")
    logger.info("-" * 55)

    if state.get("status_final") == "erro":
        logger.warning(
            "[postgres_node] ⚠ Erro crítico detectado — abortando persistência"
        )
        return {"etapa_atual": "postgres_node"}

    document_context = state.get("document_context")
    metadados = state.get("metadados_catalogo")
    documento_wiki = state.get("secoes_documentacao")
    id_mongodb_previa = state.get("id_mongodb_previa")
    erros = list(state.get("erros", []))

    if not document_context or not metadados or not documento_wiki:
        erro = (
            "document_context, metadados ou documentação wiki ausentes — "
            "nós anteriores podem ter falhado"
        )
        logger.error("[postgres_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "postgres_node",
        }

    if not id_mongodb_previa:
        erro = "id_mongodb_previa ausente — persistence_node pode ter falhado"
        logger.error("[postgres_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "postgres_node",
        }

    try:
        with get_connection() as conn:
            repo = CatalogoRepository(conn)
            repo.garantir_tabelas()

            logger.info(
                "[postgres_node] Persistindo catálogo de '%s'...",
                metadados.get("component_name"),
            )

            resultado = repo.persistir(
                document_context=document_context,
                metadados=metadados,
                documento_wiki=documento_wiki,
                mongo_content_id=id_mongodb_previa,
            )

            logger.info(
                "[postgres_node] ✓ application_id=%s documentation_id=%s (version=%s)",
                resultado["application_id"],
                resultado["documentation_id"],
                resultado["version"],
            )

        logger.info(
            "[postgres_node] ✓ Persistência PostgreSQL concluída — "
            "seguindo para supervisor_node"
        )

        return {
            "id_postgres_application": resultado["application_id"],
            "id_postgres_documentation": resultado["documentation_id"],
            "erros": erros,
            "etapa_atual": "postgres_node",
        }

    except Exception as exc:
        erro = f"Erro ao persistir no PostgreSQL: {str(exc)}"
        logger.error("[postgres_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "postgres_node",
        }