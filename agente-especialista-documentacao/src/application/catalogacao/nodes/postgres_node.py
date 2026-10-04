"""
nodes/postgres_node.py
------------------------
Sexto nó do grafo (Fase 7) — persiste o pré-cadastro no PostgreSQL.

Fase 7: os campos de negócio (team_id, criticidade, environment etc)
        chegam como None dentro de metadados_catalogo — o repositório
        de persistência já trata isso automaticamente (usa .get(),
        que retorna None para chaves ausentes ou com valor None).
        Nenhuma mudança de lógica é necessária aqui, só a origem dos
        dados (secoes_documentacao no lugar de previa_documentacao).
"""

import logging
from typing import Any

from src.application.state import DocumentacaoState
from src.infrastructure.postgresql import (
    ObjetosGeradosPreViasRepository,
    get_connection,
)

logger = logging.getLogger(__name__)


def postgres_node(state: DocumentacaoState) -> dict[str, Any]:
    """
    Persiste o pré-cadastro do componente no PostgreSQL.

    Args:
        state: Estado com secoes_documentacao, metadados_catalogo e
               IDs do MongoDB já preenchidos

    Returns:
        dict com id_postgres preenchido
    """
    logger.info("-" * 55)
    logger.info("[postgres_node] Iniciando persistência no PostgreSQL")
    logger.info("-" * 55)

    if state.get("status_final") == "erro":
        logger.warning(
            "[postgres_node] ⚠ Erro crítico detectado — abortando persistência"
        )
        return {"etapa_atual": "postgres_node"}

    metadados = state.get("metadados_catalogo")
    documento_wiki = state.get("secoes_documentacao")
    id_mongodb_previa = state.get("id_mongodb_previa")
    id_mongodb_metadados = state.get("id_mongodb_metadados")
    erros = list(state.get("erros", []))

    if not metadados or not documento_wiki:
        erro = "metadados ou documentação wiki ausentes — nós anteriores podem ter falhado"
        logger.error("[postgres_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "postgres_node",
        }

    if not id_mongodb_previa or not id_mongodb_metadados:
        erro = "IDs do MongoDB ausentes — persistence_node pode ter falhado"
        logger.error("[postgres_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "postgres_node",
        }

    try:
        with get_connection() as conn:
            repo = ObjetosGeradosPreViasRepository(conn)
            repo.garantir_tabela()

            logger.info(
                "[postgres_node] Inserindo pré-cadastro de '%s'...",
                metadados.get("component_name"),
            )
            logger.info(
                "[postgres_node] ℹ Campos de negócio (team_id, criticidade, "
                "environment etc) serão nulos — não derivam do repositório"
            )

            id_postgres = repo.inserir(
                metadados=metadados,
                previa=documento_wiki,
                id_mongodb_previa=id_mongodb_previa,
                id_mongodb_metadados=id_mongodb_metadados,
            )

            logger.info(
                "[postgres_node] ✓ Pré-cadastro salvo com ID: %s",
                id_postgres,
            )

        logger.info(
            "[postgres_node] ✓ Persistência PostgreSQL concluída — "
            "seguindo para supervisor_node"
        )

        return {
            "id_postgres": id_postgres,
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