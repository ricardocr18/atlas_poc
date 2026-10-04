"""
infrastructure/postgresql/repositories.py
-------------------------------------------
Repositório para o schema normalizado do catálogo (Fase 11).

Substitui a tabela única 'objetos_gerados_previas' por 7 tabelas
relacionais. Ver docs/decisao-arquitetura-postgresql-normalizado.md
(projeto Sicredi) para o raciocínio completo.

Fontes dos dados (uma rodada do agente produz os três):
  - document_context: payload bruto lido de ingestion_payloads (Mongo)
  - metadados:         dict gerado pelo cataloging_node (chaves em inglês)
  - documento_wiki:    dict gerado pelo documentation_node (contém
                        'title' e 'sections')

Modelo de versionamento (Opção B, decidida com o time):
  - application: 1 linha por componente real — UPSERT por technical_name
  - documentation / document / dependencies / application_approver:
    sempre INSERT novo a cada rodada, vinculados à mesma application
  - is_current: só a versão mais recente de documentation tem
    is_current = true (índice único parcial garante isso no banco)
"""

import logging
from datetime import datetime, timezone
from typing import Any

from psycopg2.extensions import connection as PgConnection

logger = logging.getLogger(__name__)


# ============================================================
# DDL — idempotente, seguro para rodar em toda inicialização
# ============================================================
SQL_CRIAR_TABELAS = """
CREATE TABLE IF NOT EXISTS application (
    id                  BIGSERIAL PRIMARY KEY,
    gitlab_project_id   VARCHAR(100),
    title               VARCHAR(255),
    technical_name      VARCHAR(255) NOT NULL,
    type                VARCHAR(50),
    criticality         VARCHAR(10)
                            CHECK (criticality IN ('LOW', 'MEDIUM', 'HIGH')),
    sensitivity         VARCHAR(20)
                            CHECK (sensitivity IN ('CONFIDENTIAL', 'RESTRICTED', 'PUBLIC')),
    description         TEXT,
    team                VARCHAR(255),
    tribe               VARCHAR(255),
    project             VARCHAR(255),
    status              VARCHAR(30),
    version             VARCHAR(50),
    category            VARCHAR(50),
    cmdb_component      BOOLEAN NOT NULL DEFAULT FALSE,
    repository_url      TEXT,
    default_branch      VARCHAR(100),
    created_by          VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_application_technical_name UNIQUE (technical_name)
);
CREATE INDEX IF NOT EXISTS idx_application_criticality ON application (criticality);
CREATE INDEX IF NOT EXISTS idx_application_team        ON application (team);
CREATE INDEX IF NOT EXISTS idx_application_tribe       ON application (tribe);

CREATE TABLE IF NOT EXISTS documentation (
    id                  BIGSERIAL PRIMARY KEY,
    application_id      BIGINT NOT NULL
                            REFERENCES application (id) ON DELETE RESTRICT,
    version             INTEGER NOT NULL,
    summary             TEXT,
    approved_by         VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at         TIMESTAMPTZ,
    approval_comment    TEXT,
    status              VARCHAR(30) NOT NULL
                            CHECK (status IN ('em_aprovacao', 'reprocessando', 'aprovado', 'depreciado')),
    is_current          BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_documentation_application_version UNIQUE (application_id, version)
);
CREATE INDEX IF NOT EXISTS idx_documentation_application_id ON documentation (application_id);
CREATE INDEX IF NOT EXISTS idx_documentation_status         ON documentation (status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_documentation_current_per_application
    ON documentation (application_id)
    WHERE is_current;

CREATE TABLE IF NOT EXISTS document (
    id                  BIGSERIAL PRIMARY KEY,
    documentation_id    BIGINT NOT NULL
                            REFERENCES documentation (id) ON DELETE RESTRICT,
    title               VARCHAR(255),
    summary             TEXT,
    mongo_content_id    VARCHAR(24) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_document_documentation_id ON document (documentation_id);

CREATE TABLE IF NOT EXISTS dependencies (
    id                  BIGSERIAL PRIMARY KEY,
    documentation_id    BIGINT NOT NULL
                            REFERENCES documentation (id) ON DELETE RESTRICT,
    name                VARCHAR(255) NOT NULL,
    relationship        VARCHAR(20) NOT NULL
                            CHECK (relationship IN ('CONSUMER', 'RESOURCE')),
    type                VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS idx_dependencies_documentation_id ON dependencies (documentation_id);

CREATE TABLE IF NOT EXISTS application_approver (
    id                  BIGSERIAL PRIMARY KEY,
    documentation_id    BIGINT NOT NULL
                            REFERENCES documentation (id) ON DELETE RESTRICT,
    username            VARCHAR(100) NOT NULL,
    name                VARCHAR(255),
    role                VARCHAR(100),
    CONSTRAINT uq_approver_documentation_username UNIQUE (documentation_id, username)
);
CREATE INDEX IF NOT EXISTS idx_application_approver_documentation_id ON application_approver (documentation_id);

CREATE TABLE IF NOT EXISTS tag (
    id      BIGSERIAL PRIMARY KEY,
    name    VARCHAR(100) NOT NULL,
    CONSTRAINT uq_tag_name UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS application_tag (
    application_id  BIGINT NOT NULL
                        REFERENCES application (id) ON DELETE RESTRICT,
    tag_id          BIGINT NOT NULL
                        REFERENCES tag (id) ON DELETE RESTRICT,
    PRIMARY KEY (application_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_application_tag_tag_id ON application_tag (tag_id);
"""


# ============================================================
# Mapeamento visibility (ingestion_payload) -> sensitivity
# (CHECK constraint só aceita CONFIDENTIAL/RESTRICTED/PUBLIC)
#
# Regra provisória — vocabulário ainda não confirmado com o time de
# ingestão (ver pendência no doc de arquitetura). Valor não mapeado
# vira NULL (não falha o insert, mas fica visível para revisão).
# ============================================================
_VISIBILITY_PARA_SENSITIVITY = {
    "private": "RESTRICTED",
    "internal": "CONFIDENTIAL",
    "public": "PUBLIC",
}


def _mapear_sensitivity(visibility: str | None) -> str | None:
    if not visibility:
        return None
    valor = _VISIBILITY_PARA_SENSITIVITY.get(visibility.lower())
    if valor is None:
        logger.warning(
            "[repositories] ⚠ visibility '%s' sem mapeamento conhecido para "
            "sensitivity — gravando NULL, revisar manualmente.",
            visibility,
        )
    return valor


class CatalogoRepository:
    """
    Repositório do schema normalizado do catálogo (7 tabelas).

    Uma chamada a `persistir(...)` executa, numa única transação:
      1. UPSERT de application (por technical_name)
      2. fecha a versão corrente anterior (is_current = false)
      3. INSERT de documentation (nova versão, is_current = true)
      4. INSERT de document (referência ao Mongo)
      5. INSERT de dependencies (fotografia de integrations)
      6. INSERT de application_approver (fotografia de ownership.approvers)
      7. UPSERT de tag + vínculo em application_tag
    """

    def __init__(self, conn: PgConnection) -> None:
        self._conn = conn
        logger.debug("CatalogoRepository inicializado.")

    def garantir_tabelas(self) -> None:
        """Cria as 7 tabelas se não existirem. Seguro rodar sempre."""
        with self._conn.cursor() as cur:
            cur.execute(SQL_CRIAR_TABELAS)
        self._conn.commit()
        logger.info("Schema do catálogo (7 tabelas) verificado/criado com sucesso.")

    # ------------------------------------------------------------------
    # Passo 1 — application (UPSERT por technical_name)
    # ------------------------------------------------------------------
    def _upsert_application(
        self, cur, document_context: dict[str, Any], metadados: dict[str, Any]
    ) -> int:
        cmdb_component = bool(document_context.get("cmdb"))
        sensitivity = _mapear_sensitivity(document_context.get("visibility"))
        agora = datetime.now(timezone.utc)

        cur.execute(
            """
            INSERT INTO application (
                gitlab_project_id, title, technical_name, type, criticality,
                sensitivity, description, team, tribe, project, status,
                version, category, cmdb_component, repository_url,
                default_branch, created_by, created_at, updated_at
            ) VALUES (
                %(gitlab_project_id)s, %(title)s, %(technical_name)s, %(type)s,
                %(criticality)s, %(sensitivity)s, %(description)s, %(team)s,
                %(tribe)s, %(project)s, %(status)s, %(version)s, %(category)s,
                %(cmdb_component)s, %(repository_url)s, %(default_branch)s,
                %(created_by)s, %(created_at)s, %(updated_at)s
            )
            ON CONFLICT (technical_name) DO UPDATE SET
                type             = EXCLUDED.type,
                criticality      = EXCLUDED.criticality,
                sensitivity      = EXCLUDED.sensitivity,
                description      = EXCLUDED.description,
                team             = EXCLUDED.team,
                tribe            = EXCLUDED.tribe,
                project          = EXCLUDED.project,
                status           = EXCLUDED.status,
                category         = EXCLUDED.category,
                cmdb_component   = EXCLUDED.cmdb_component,
                repository_url   = EXCLUDED.repository_url,
                default_branch   = EXCLUDED.default_branch,
                updated_at       = EXCLUDED.updated_at
            RETURNING id;
            """,
            {
                "gitlab_project_id": "vamos_analisar",
                "title": "vamos_analisar",
                "technical_name": metadados.get("component_name"),
                "type": document_context.get("classification", {}).get("application_type"),
                "criticality": metadados.get("criticality"),
                "sensitivity": sensitivity,
                "description": document_context.get("description"),
                "team": metadados.get("responsible_team"),
                "tribe": metadados.get("tribe"),
                "project": metadados.get("project"),
                "status": metadados.get("application_status"),
                "version": "vamos_analisar",
                "category": document_context.get("category"),
                "cmdb_component": cmdb_component,
                "repository_url": document_context.get("repository"),
                "default_branch": document_context.get("deployment", {}).get("default_branch"),
                "created_by": "vamos_analisar",
                "created_at": agora,
                "updated_at": agora,
            },
        )
        return cur.fetchone()["id"]

    # ------------------------------------------------------------------
    # Passo 2+3 — fecha versão corrente anterior, insere a nova
    # ------------------------------------------------------------------
    def _inserir_documentation(
        self, cur, application_id: int, metadados: dict[str, Any]
    ) -> tuple[int, int]:
        cur.execute(
            "UPDATE documentation SET is_current = false "
            "WHERE application_id = %(application_id)s AND is_current = true;",
            {"application_id": application_id},
        )

        # Não precisa de FOR UPDATE aqui: o UPSERT em application (passo
        # anterior, mesma transação) já tomou um lock de linha nessa
        # application_id via ON CONFLICT DO UPDATE, serializando chamadas
        # concorrentes de persistir() para o mesmo componente.
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS proxima_versao "
            "FROM documentation WHERE application_id = %(application_id)s;",
            {"application_id": application_id},
        )
        proxima_versao = cur.fetchone()["proxima_versao"]

        cur.execute(
            """
            INSERT INTO documentation (
                application_id, version, summary, status, is_current
            ) VALUES (
                %(application_id)s, %(version)s, %(summary)s, %(status)s, true
            )
            RETURNING id;
            """,
            {
                "application_id": application_id,
                "version": proxima_versao,
                "summary": metadados.get("executive_summary"),
                "status": "em_aprovacao",
            },
        )
        documentation_id = cur.fetchone()["id"]
        return documentation_id, proxima_versao

    # ------------------------------------------------------------------
    # Passo 4 — document (referência ao Mongo)
    # ------------------------------------------------------------------
    def _inserir_document(
        self,
        cur,
        documentation_id: int,
        documento_wiki: dict[str, Any],
        metadados: dict[str, Any],
        mongo_content_id: str,
    ) -> int:
        cur.execute(
            """
            INSERT INTO document (documentation_id, title, summary, mongo_content_id)
            VALUES (%(documentation_id)s, %(title)s, %(summary)s, %(mongo_content_id)s)
            RETURNING id;
            """,
            {
                "documentation_id": documentation_id,
                "title": documento_wiki.get("title") or documento_wiki.get("general_title"),
                "summary": metadados.get("executive_summary"),
                "mongo_content_id": mongo_content_id,
            },
        )
        return cur.fetchone()["id"]

    # ------------------------------------------------------------------
    # Passo 5 — dependencies (fotografia de integrations)
    #
    # Convenção adotada (confirmar com o time do BFF): itens em
    # integrations.consumed = esta aplicação é CONSUMER deles;
    # itens em integrations.consumers = esta aplicação é o RESOURCE
    # consumido por eles.
    # ------------------------------------------------------------------
    def _inserir_dependencies(
        self, cur, documentation_id: int, document_context: dict[str, Any]
    ) -> int:
        integrations = document_context.get("integrations", {})
        total = 0

        for relationship, chave in (("CONSUMER", "consumed"), ("RESOURCE", "consumers")):
            por_ambiente = integrations.get(chave, {}) or {}
            for itens in por_ambiente.values():
                for item in itens:
                    cur.execute(
                        """
                        INSERT INTO dependencies (documentation_id, name, relationship, type)
                        VALUES (%(documentation_id)s, %(name)s, %(relationship)s, %(type)s);
                        """,
                        {
                            "documentation_id": documentation_id,
                            "name": item.get("resource_name"),
                            "relationship": relationship,
                            "type": item.get("resource_type"),
                        },
                    )
                    total += 1
        return total

    # ------------------------------------------------------------------
    # Passo 6 — application_approver (fotografia de ownership.approvers)
    # ------------------------------------------------------------------
    def _inserir_approvers(
        self, cur, documentation_id: int, document_context: dict[str, Any]
    ) -> int:
        approvers = document_context.get("ownership", {}).get("approvers", []) or []
        total = 0

        for approver in approvers:
            username = approver.get("username")
            if not username:
                continue
            cur.execute(
                """
                INSERT INTO application_approver (documentation_id, username, name, role)
                VALUES (%(documentation_id)s, %(username)s, %(name)s, %(role)s)
                ON CONFLICT (documentation_id, username) DO NOTHING;
                """,
                {
                    "documentation_id": documentation_id,
                    "username": username,
                    "name": approver.get("name"),
                    "role": approver.get("role"),
                },
            )
            total += 1
        return total

    # ------------------------------------------------------------------
    # Passo 7 — tag / application_tag (N:N)
    # ------------------------------------------------------------------
    def _upsert_tags(self, cur, application_id: int, tags: list[str]) -> int:
        total = 0
        for nome in tags or []:
            nome = (nome or "").strip()
            if not nome:
                continue
            cur.execute(
                """
                INSERT INTO tag (name) VALUES (%(name)s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id;
                """,
                {"name": nome},
            )
            tag_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO application_tag (application_id, tag_id)
                VALUES (%(application_id)s, %(tag_id)s)
                ON CONFLICT DO NOTHING;
                """,
                {"application_id": application_id, "tag_id": tag_id},
            )
            total += 1
        return total

    # ------------------------------------------------------------------
    # Orquestração — chamada única pelo postgres_node
    # ------------------------------------------------------------------
    def persistir(
        self,
        document_context: dict[str, Any],
        metadados: dict[str, Any],
        documento_wiki: dict[str, Any],
        mongo_content_id: str,
    ) -> dict[str, Any]:
        """
        Persiste uma rodada completa do agente nas 7 tabelas, numa
        única transação (tudo ou nada).

        Returns:
            dict com os IDs gerados: application_id, documentation_id,
            document_id, version, total_dependencies, total_approvers,
            total_tags
        """
        try:
            with self._conn.cursor() as cur:
                application_id = self._upsert_application(cur, document_context, metadados)
                documentation_id, versao = self._inserir_documentation(cur, application_id, metadados)
                document_id = self._inserir_document(
                    cur, documentation_id, documento_wiki, metadados, mongo_content_id
                )
                total_deps = self._inserir_dependencies(cur, documentation_id, document_context)
                total_approvers = self._inserir_approvers(cur, documentation_id, document_context)
                total_tags = self._upsert_tags(cur, application_id, metadados.get("tags", []))

            self._conn.commit()

        except Exception:
            self._conn.rollback()
            raise

        logger.info(
            "[CatalogoRepository] ✓ application_id=%s documentation_id=%s "
            "(version=%s) document_id=%s dependencies=%s approvers=%s tags=%s",
            application_id, documentation_id, versao, document_id,
            total_deps, total_approvers, total_tags,
        )

        return {
            "application_id": application_id,
            "documentation_id": documentation_id,
            "document_id": document_id,
            "version": versao,
            "total_dependencies": total_deps,
            "total_approvers": total_approvers,
            "total_tags": total_tags,
        }