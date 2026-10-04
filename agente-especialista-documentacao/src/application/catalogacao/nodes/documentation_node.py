"""
nodes/documentation_node.py
-----------------------------
Terceiro nó do grafo (Fase 8/9) — gera a documentação em formato wiki
multi-seção via LLM OpenAI, a partir do document_context estruturado
vindo do atlas-apis-ingestao.

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
    SYSTEM_WIKI_DOCUMENTACAO,
    montar_prompt_wiki_documentacao,
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


def _chamar_llm_wiki(document_context: dict[str, Any]) -> dict[str, Any]:
    """
    Chama a LLM OpenAI para gerar a documentação em formato wiki.

    Args:
        document_context: dados buscados pelo ingestao_fetch_node

    Returns:
        dict estruturado no formato da collection documentos_gerados_previas,
        com nomes de campo em inglês (title, sections, data_source,
        generated_at, generated_by, tokens_used)
    """
    settings = get_settings()

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
    )

    mensagens = [
        SystemMessage(content=SYSTEM_WIKI_DOCUMENTACAO),
        HumanMessage(content=montar_prompt_wiki_documentacao(document_context)),
    ]

    logger.info(
        "[documentation_node] Chamando LLM '%s' para gerar wiki...",
        settings.openai_model,
    )

    resposta = llm.invoke(mensagens)
    texto_limpo = _limpar_json_llm(resposta.content)

    try:
        resultado_wiki = json.loads(texto_limpo)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM retornou JSON inválido para a wiki: {str(exc)}\n"
            f"Conteúdo retornado: {texto_limpo[:200]}..."
        ) from exc

    sections = resultado_wiki.get("sections", [])
    logger.info("[documentation_node] ✓ LLM gerou %d seção(ões)", len(sections))

    return {
        "event_id": document_context.get("component_name"),
        "repository": document_context.get("repository"),
        "component_name": document_context.get("component_name"),
        "title": resultado_wiki.get(
            "general_title", f"{document_context.get('component_name')} — Documentação"
        ),
        "sections": sections,
        "data_source": "atlas_ingestao_api.ingestion_payloads",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": settings.openai_model,
        "tokens_used": resposta.usage_metadata,
    }


def documentation_node(state: DocumentacaoState) -> dict[str, Any]:
    """
    Gera a documentação wiki do componente via LLM OpenAI.

    Args:
        state: Estado atual com document_context validado

    Returns:
        dict com secoes_documentacao preenchido pela LLM (nome interno
        do estado — não confundir com o campo "sections" do documento
        persistido; ver state.py)
    """
    logger.info("-" * 55)
    logger.info("[documentation_node] Gerando documentação wiki via LLM OpenAI")
    logger.info("-" * 55)

    if state.get("status_final") == "erro":
        logger.warning(
            "[documentation_node] ⚠ Erro detectado no estado — pulando geração"
        )
        return {"etapa_atual": "documentation_node"}

    document_context = state["document_context"]
    erros = list(state.get("erros", []))

    try:
        documento = _chamar_llm_wiki(document_context)

        logger.info(
            "[documentation_node] ✓ Documentação gerada para: '%s'",
            documento.get("component_name"),
        )
        for secao in documento.get("sections", []):
            logger.info(
                "[documentation_node]   • Seção %s: '%s'",
                secao.get("order"),
                secao.get("title"),
            )
        logger.info(
            "[documentation_node] ✓ Gerado por: '%s'", documento.get("generated_by")
        )
        logger.info("[documentation_node] ✓ Seguindo para cataloging_node")

        return {
            "secoes_documentacao": documento,
            "erros": erros,
            "etapa_atual": "documentation_node",
        }

    except Exception as exc:
        erro = f"Erro ao gerar documentação wiki: {str(exc)}"
        logger.error("[documentation_node] ✗ %s", erro)
        erros.append(erro)
        return {
            "erros": erros,
            "status_final": "erro",
            "etapa_atual": "documentation_node",
        }