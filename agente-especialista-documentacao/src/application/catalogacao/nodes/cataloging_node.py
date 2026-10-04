"""
nodes/cataloging_node.py
--------------------------
Quarto nó do grafo (Fase 8/9) — gera o checklist técnico via LLM OpenAI,
a partir do document_context estruturado vindo do atlas-apis-ingestao.

Fase 9: nomes de campo do documento persistido migrados para inglês
        (ver docs/RENOMEACAO_CAMPOS.md).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.application.prompts.prompts_catalog_document import (
    SYSTEM_CHECKLIST_TECNICO,
    montar_prompt_checklist_tecnico,
)
from src.application.state import DocumentacaoState
from src.settings import get_settings

logger = logging.getLogger(__name__)


def _limpar_json_llm(texto: str) -> str:
    """Remove blocos de markdown que a LLM às vezes inclui por engano."""
    texto = texto.strip()
    if texto.startswith("```"):
        linhas = texto.split("\n")
        texto = "\n".join(linhas[1:-1])
    return texto


def _chamar_llm_checklist(document_context: dict[str, Any]) -> dict[str, Any]:
    """
    Chama a LLM OpenAI para preencher o checklist técnico do componente.

    Args:
        document_context: dados buscados pelo ingestao_fetch_node

    Returns:
        dict estruturado no formato da collection
        componentes_catalogados_metadados, com nomes de campo em inglês
    """
    settings = get_settings()

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
    )

    mensagens = [
        SystemMessage(content=SYSTEM_CHECKLIST_TECNICO),
        HumanMessage(content=montar_prompt_checklist_tecnico(document_context)),
    ]

    logger.info(
        "[cataloging_node] Chamando LLM '%s' para o checklist técnico...",
        settings.openai_model,
    )

    resposta = llm.invoke(mensagens)
    texto_limpo = _limpar_json_llm(resposta.content)

    try:
        checklist = json.loads(texto_limpo)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM retornou JSON inválido para o checklist: {str(exc)}\n"
            f"Conteúdo retornado: {texto_limpo[:200]}..."
        ) from exc

    # --- Campos de rastreabilidade ---
    checklist["event_id"] = document_context.get("component_name")
    checklist["repository"] = document_context.get("repository")
    checklist["data_source"] = "atlas_ingestao_api.ingestion_payloads"
    checklist["cataloged_at"] = datetime.now(timezone.utc).isoformat()
    checklist["cataloged_by"] = settings.openai_model
    checklist["tokens_used"] = resposta.usage_metadata

    return checklist


def cataloging_node(state: DocumentacaoState) -> dict[str, Any]:
    """
    Gera o checklist técnico do componente via LLM OpenAI.

    Args:
        state: Estado atual com document_context validado e
               secoes_documentacao já geradas

    Returns:
        dict com metadados_catalogo preenchido pela LLM
    """
    logger.info("-" * 55)
    logger.info("[cataloging_node] Gerando checklist técnico via LLM OpenAI")
    logger.info("-" * 55)

    if state.get("status_final") == "erro":
        logger.warning(
            "[cataloging_node] ⚠ Erro detectado no estado — pulando catalogação"
        )
        return {"etapa_atual": "cataloging_node"}

    document_context = state["document_context"]
    erros = list(state.get("erros", []))

    try:
        metadados = _chamar_llm_checklist(document_context)

        logger.info(
            "[cataloging_node] ✓ Checklist gerado para: '%s'",
            metadados.get("component_name"),
        )
        logger.info(
            "[cataloging_node] ✓ Time responsável: '%s' | Criticidade: '%s'",
            metadados.get("responsible_team"),
            metadados.get("criticality"),
        )
        for item in [
            "security",
            "databases",
            "messaging",
            "main_technology",
            "sicredi_flow_usage",
            "object_storage",
            "containerization",
        ]:
            resultado_item = metadados.get(item, {})
            logger.info(
                "[cataloging_node]   • %s: %s",
                item,
                resultado_item.get("status", "?") if isinstance(resultado_item, dict) else resultado_item,
            )
        logger.info(
            "[cataloging_node] ✓ Catalogado por: '%s'", metadados.get("cataloged_by")
        )
        logger.info("[cataloging_node] ✓ Seguindo para persistence_node")

        return {
            "metadados_catalogo": metadados,
            "erros": erros,
            "etapa_atual": "cataloging_node",
        }

    except Exception as exc:
        erro = f"Erro ao gerar checklist técnico: {str(exc)}"
        logger.error("[cataloging_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "cataloging_node",
        }