"""
nodes/supervisor_node.py
--------------------------
Último nó do grafo (Fase 7) — valida e consolida o resultado final.

Sem mudanças de lógica em relação à Fase 6 — só os nomes de campos
de log foram atualizados para refletir a origem via repositório.
"""

import logging
from typing import Any

from src.application.state import DocumentacaoState

logger = logging.getLogger(__name__)


def supervisor_node(state: DocumentacaoState) -> dict[str, Any]:
    """
    Valida o resultado final e consolida o estado do grafo.
    """
    logger.info("=" * 55)
    logger.info("[supervisor_node] Validando resultado final do grafo")
    logger.info("=" * 55)

    erros = list(state.get("erros", []))
    id_previa = state.get("id_mongodb_previa")
    id_metadados = state.get("id_mongodb_metadados")
    id_postgres = state.get("id_postgres")
    metadados = state.get("metadados_catalogo", {})

    if state.get("status_final") == "erro":
        logger.error(
            "[supervisor_node] ✗ Grafo encerrado com ERRO — %d erro(s)",
            len(erros),
        )
        for i, erro in enumerate(erros, 1):
            logger.error("[supervisor_node]   Erro %d: %s", i, erro)
        return {
            "status_final": "erro",
            "etapa_atual": "supervisor_node",
        }

    problemas = []
    if not id_previa:
        problemas.append("ID da documentação MongoDB não gerado")
    if not id_metadados:
        problemas.append("ID dos metadados MongoDB não gerado")
    if not id_postgres:
        problemas.append("ID do PostgreSQL não gerado")

    if problemas:
        erros.extend(problemas)
        logger.warning("[supervisor_node] ⚠ Execução com problemas parciais:")
        for problema in problemas:
            logger.warning("[supervisor_node]   • %s", problema)
        return {
            "erros": erros,
            "status_final": "erro_parcial",
            "etapa_atual": "supervisor_node",
        }

    status_final = "sucesso" if not erros else "sucesso_com_avisos"

    logger.info("[supervisor_node] ✓ GRAFO EXECUTADO COM SUCESSO")
    logger.info("-" * 55)
    logger.info(
        "[supervisor_node] ✓ Componente    : '%s'",
        metadados.get("component_name"),
    )
    logger.info(
        "[supervisor_node] ✓ Repositório   : '%s'",
        metadados.get("repository"),
    )
    logger.info(
        "[supervisor_node] ✓ ID doc wiki   : %s → documentos_gerados_previas (MongoDB)",
        id_previa,
    )
    logger.info(
        "[supervisor_node] ✓ ID checklist  : %s → componentes_catalogados_metadados (MongoDB)",
        id_metadados,
    )
    logger.info(
        "[supervisor_node] ✓ ID postgres   : %s → objetos_gerados_previas (PostgreSQL)",
        id_postgres,
    )
    logger.info("[supervisor_node] ✓ Status        : %s", status_final)

    if erros:
        logger.warning("[supervisor_node] ⚠ %d aviso(s):", len(erros))
        for aviso in erros:
            logger.warning("[supervisor_node]   • %s", aviso)

    logger.info("=" * 55)

    return {
        "erros": erros,
        "status_final": status_final,
        "etapa_atual": "supervisor_node",
    }