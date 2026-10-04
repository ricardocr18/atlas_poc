"""
nodes/persistence_node.py
---------------------------
Quinto nó do grafo — persiste a documentação wiki e o checklist
técnico nas collections corretas do MongoDB.

Fase 9: única mudança é a referência de log a "sections" (antes
        "secoes"), acompanhando a renomeação de campos do documento
        persistido. A lógica de roteamento não muda.
"""

import logging
from typing import Any

from src.application.state import DocumentacaoState
from src.infrastructure.mongodb import (
    ComponentesMetadadosRepository,
    DocumentosPreViasRepository,
    get_database,
)

logger = logging.getLogger(__name__)


def persistence_node(state: DocumentacaoState) -> dict[str, Any]:
    """
    Persiste a documentação wiki e os metadados técnicos no MongoDB.

    Roteamento (inalterado):
      secoes_documentacao (estado) → collection documentos_gerados_previas
      metadados_catalogo (estado)  → collection componentes_catalogados_metadados

    Args:
        state: Estado com secoes_documentacao e metadados_catalogo gerados

    Returns:
        dict com id_mongodb_previa e id_mongodb_metadados preenchidos
    """
    logger.info("-" * 55)
    logger.info("[persistence_node] Iniciando persistência no MongoDB")
    logger.info("-" * 55)

    if state.get("status_final") == "erro":
        logger.warning(
            "[persistence_node] ⚠ Erro crítico detectado — abortando persistência"
        )
        return {"etapa_atual": "persistence_node"}

    documento_wiki = state.get("secoes_documentacao")
    metadados = state.get("metadados_catalogo")
    erros = list(state.get("erros", []))

    if not documento_wiki:
        erro = "secoes_documentacao não foi gerada pelo documentation_node"
        logger.error("[persistence_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "persistence_node",
        }

    if not metadados:
        erro = "metadados_catalogo não foram gerados pelo cataloging_node"
        logger.error("[persistence_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "persistence_node",
        }

    try:
        with get_database() as db:
            repo_previas = DocumentosPreViasRepository(db)
            repo_metadados = ComponentesMetadadosRepository(db)

            logger.info(
                "[persistence_node] Salvando documentação wiki em "
                "'documentos_gerados_previas'..."
            )
            id_previa = repo_previas.inserir(documento_wiki)
            logger.info(
                "[persistence_node] ✓ Documentação salva com ID: %s (%d seções)",
                id_previa,
                len(documento_wiki.get("sections", [])),
            )

            logger.info(
                "[persistence_node] Salvando checklist técnico em "
                "'componentes_catalogados_metadados'..."
            )
            id_metadados = repo_metadados.inserir(metadados)
            logger.info(
                "[persistence_node] ✓ Checklist salvo com ID: %s", id_metadados
            )

        logger.info(
            "[persistence_node] ✓ Persistência concluída — seguindo para postgres_node"
        )

        return {
            "id_mongodb_previa": id_previa,
            "id_mongodb_metadados": id_metadados,
            "erros": erros,
            "etapa_atual": "persistence_node",
        }

    except Exception as exc:
        erro = f"Erro ao persistir no MongoDB: {str(exc)}"
        logger.error("[persistence_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "persistence_node",
        }