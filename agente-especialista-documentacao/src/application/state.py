"""
agent_application/state.py
------------------------------
Define o Estado compartilhado do grafo LangGraph.

Fase 8: repository_url e repo_data são substituídos por component_name
        e document_context — a entrada principal passa a ser o nome
        do componente (chave de busca no atlas_ingestao_api), não mais
        uma URL de repositório.

Ciclo de vida do Estado neste grafo:
  1. ingestao_fetch_node → preenche document_context a partir do component_name
  2. input_node          → valida document_context
  3. documentation_node  → preenche secoes_documentacao (formato wiki)
  4. cataloging_node     → preenche metadados_catalogo (checklist técnico)
  5. persistence_node    → preenche id_mongodb_previa e id_mongodb_metadados
  6. postgres_node       → preenche id_postgres
  7. supervisor_node     → preenche status_final e encerra
"""

from typing import Any
from typing_extensions import TypedDict


class DocumentacaoState(TypedDict):
    """
    Estado completo do grafo de documentação e catalogação.

    Campos:
        component_name: nome do componente a ser processado (entrada,
                         chave de busca no atlas_ingestao_api)

        document_context: dados completos do componente, buscados pelo
                           ingestao_fetch_node no MongoDB atlas_ingestao_api
                           (ownership, classification, technology, api,
                           integrations, security, observability, data,
                           runtime, quality, deployment, jira)

        secoes_documentacao: documento wiki gerado pelo documentation_node
                             → salvo em documentos_gerados_previas (MongoDB)

        metadados_catalogo: checklist técnico gerado pelo cataloging_node
                            → salvo em componentes_catalogados_metadados (MongoDB)

        id_mongodb_previa: ID do documento em documentos_gerados_previas
        id_mongodb_metadados: ID do documento em componentes_catalogados_metadados
        id_postgres: UUID do registro em objetos_gerados_previas (PostgreSQL)

        status_final: "sucesso" | "erro" | "erro_parcial" | "processando"
        erros: lista de erros acumulados durante a execução
        etapa_atual: nome do nó sendo executado
    """

    # --- Entrada ---
    component_name: str

    # --- Preenchido pelo ingestao_fetch_node ---
    document_context: dict[str, Any] | None

    # --- Gerado pelo documentation_node ---
    secoes_documentacao: dict[str, Any] | None

    # --- Gerado pelo cataloging_node ---
    metadados_catalogo: dict[str, Any] | None

    # --- Preenchido pelo persistence_node (MongoDB) ---
    id_mongodb_previa: str | None
    id_mongodb_metadados: str | None

    # --- Preenchido pelo postgres_node (PostgreSQL) ---
    id_postgres: str | None

    # --- Controle de fluxo ---
    status_final: str | None
    erros: list[str]
    etapa_atual: str | None


def criar_estado_inicial(component_name: str) -> DocumentacaoState:
    """
    Cria o estado inicial do grafo com valores padrão.

    Args:
        component_name: nome do componente a ser buscado e processado

    Returns:
        DocumentacaoState com component_name preenchido e todos os
        outros campos com valores padrão seguros.
    """
    return DocumentacaoState(
        component_name=component_name,
        document_context=None,
        secoes_documentacao=None,
        metadados_catalogo=None,
        id_mongodb_previa=None,
        id_mongodb_metadados=None,
        id_postgres=None,
        status_final="processando",
        erros=[],
        etapa_atual="iniciando",
    )