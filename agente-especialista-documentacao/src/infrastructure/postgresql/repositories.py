"""
infrastructure/postgresql/repositories.py
-------------------------------------------
Repositório para a tabela objetos_gerados_previas no PostgreSQL.

Fase 9: colunas renomeadas de português para inglês (ver
        docs/RENOMEACAO_CAMPOS.md). Como a tabela já tem registros
        reais (local e Sicredi), a migração usa RENAME COLUMN em vez
        de recriar a tabela — preserva todos os dados existentes.

CREATE TABLE IF NOT EXISTS + migração idempotente de nomes:
  1. Se a tabela não existe, cria já com os nomes em inglês
  2. Se a tabela existe com nomes antigos (PT), renomeia cada coluna
     — verificando antes se ela ainda existe com o nome antigo, para
     que rodar isso múltiplas vezes seja sempre seguro
"""

import logging
from datetime import datetime, timezone
from typing import Any

from psycopg2.extensions import connection as PgConnection

logger = logging.getLogger(__name__)

TABELA = "objetos_gerados_previas"

# --- Criação da tabela (ambientes novos, já com nomes em inglês) ---
SQL_CRIAR_TABELA = f"""
CREATE TABLE IF NOT EXISTS {TABELA} (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id                 VARCHAR(100),
    transaction_id           VARCHAR(100),
    component_name           VARCHAR(200) NOT NULL,
    application_name         VARCHAR(200),
    team_id                  VARCHAR(100),
    responsible_team         VARCHAR(200),
    project                  VARCHAR(200),
    tribe                    VARCHAR(200),
    application_type         VARCHAR(100),
    application_category     VARCHAR(100),
    criticality               VARCHAR(50),
    environment               TEXT[],
    application_status       VARCHAR(50),
    repository                VARCHAR(500),
    mongodb_documentation_id VARCHAR(100),
    mongodb_metadata_id      VARCHAR(100),
    registration_status      VARCHAR(50) DEFAULT 'pendente_aprovacao',
    version                   INTEGER DEFAULT 1,
    is_active_version        BOOLEAN DEFAULT TRUE,
    rejection_reason          TEXT,
    evaluated_by               VARCHAR(100),
    created_at                 TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at                 TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

# --- Migração idempotente: renomeia colunas antigas (PT) para os novos
#     nomes (EN), somente se a coluna antiga ainda existir. Seguro
#     rodar em toda inicialização, mesmo em bancos já migrados ou
#     criados do zero já com os nomes novos. ---
SQL_MIGRAR_NOMES_FASE9 = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='tribo') THEN
        ALTER TABLE {TABELA} RENAME COLUMN tribo TO tribe;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='versao') THEN
        ALTER TABLE {TABELA} RENAME COLUMN versao TO version;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='projeto') THEN
        ALTER TABLE {TABELA} RENAME COLUMN projeto TO project;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='criado_em') THEN
        ALTER TABLE {TABELA} RENAME COLUMN criado_em TO created_at;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='criticidade') THEN
        ALTER TABLE {TABELA} RENAME COLUMN criticidade TO criticality;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='avaliado_por') THEN
        ALTER TABLE {TABELA} RENAME COLUMN avaliado_por TO evaluated_by;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='versao_ativa') THEN
        ALTER TABLE {TABELA} RENAME COLUMN versao_ativa TO is_active_version;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='atualizado_em') THEN
        ALTER TABLE {TABELA} RENAME COLUMN atualizado_em TO updated_at;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='tipo_aplicacao') THEN
        ALTER TABLE {TABELA} RENAME COLUMN tipo_aplicacao TO application_type;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='status_cadastro') THEN
        ALTER TABLE {TABELA} RENAME COLUMN status_cadastro TO registration_status;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='status_aplicacao') THEN
        ALTER TABLE {TABELA} RENAME COLUMN status_aplicacao TO application_status;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='time_responsavel') THEN
        ALTER TABLE {TABELA} RENAME COLUMN time_responsavel TO responsible_team;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='id_mongodb_previa') THEN
        ALTER TABLE {TABELA} RENAME COLUMN id_mongodb_previa TO mongodb_documentation_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='motivo_reprovacao') THEN
        ALTER TABLE {TABELA} RENAME COLUMN motivo_reprovacao TO rejection_reason;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='categoria_aplicacao') THEN
        ALTER TABLE {TABELA} RENAME COLUMN categoria_aplicacao TO application_category;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{TABELA}' AND column_name='id_mongodb_metadados') THEN
        ALTER TABLE {TABELA} RENAME COLUMN id_mongodb_metadados TO mongodb_metadata_id;
    END IF;
END $$;
"""

SQL_INSERIR = f"""
INSERT INTO {TABELA} (
    event_id,
    transaction_id,
    component_name,
    application_name,
    team_id,
    responsible_team,
    project,
    tribe,
    application_type,
    application_category,
    criticality,
    environment,
    application_status,
    repository,
    mongodb_documentation_id,
    mongodb_metadata_id,
    registration_status,
    version,
    is_active_version,
    created_at,
    updated_at
) VALUES (
    %(event_id)s,
    %(transaction_id)s,
    %(component_name)s,
    %(application_name)s,
    %(team_id)s,
    %(responsible_team)s,
    %(project)s,
    %(tribe)s,
    %(application_type)s,
    %(application_category)s,
    %(criticality)s,
    %(environment)s,
    %(application_status)s,
    %(repository)s,
    %(mongodb_documentation_id)s,
    %(mongodb_metadata_id)s,
    %(registration_status)s,
    %(version)s,
    %(is_active_version)s,
    %(created_at)s,
    %(updated_at)s
)
RETURNING id;
"""

SQL_BUSCAR_POR_EVENT_ID = f"""
SELECT * FROM {TABELA}
WHERE event_id = %(event_id)s
ORDER BY created_at DESC
LIMIT 1;
"""


class ObjetosGeradosPreViasRepository:
    """
    Repositório para a tabela objetos_gerados_previas.

    Fase 9: campos de negócio agora lidos do dict `metadados` usando
            nomes em inglês (ex: metadados.get("responsible_team") em
            vez de metadados.get("time_responsavel")).
    """

    def __init__(self, conn: PgConnection) -> None:
        self._conn = conn
        logger.debug("Repositório '%s' inicializado.", TABELA)

    def garantir_tabela(self) -> None:
        """
        Cria a tabela se não existir (já com nomes em inglês), e migra
        os nomes de coluna de instalações anteriores (PT → EN).

        Seguro chamar múltiplas vezes — nunca apaga dados, e a
        migração de nomes só age sobre colunas que ainda existem com
        o nome antigo.
        """
        with self._conn.cursor() as cur:
            cur.execute(SQL_CRIAR_TABELA)
            cur.execute(SQL_MIGRAR_NOMES_FASE9)
        self._conn.commit()
        logger.info(
            "Tabela '%s' verificada/migrada com sucesso (nomes em inglês garantidos).",
            TABELA,
        )

    def inserir(
        self,
        metadados: dict[str, Any],
        previa: dict[str, Any],
        id_mongodb_previa: str,
        id_mongodb_metadados: str,
    ) -> str:
        """
        Insere o pré-cadastro do componente na tabela.

        Args:
            metadados: dict gerado pelo cataloging_node (chaves em inglês)
            previa: dict gerado pelo documentation_node
            id_mongodb_previa: ID do documento na collection previas
            id_mongodb_metadados: ID do documento na collection metadados

        Returns:
            str: UUID do registro inserido no PostgreSQL
        """
        agora = datetime.now(timezone.utc)

        dados = {
            "event_id": metadados.get("event_id"),
            "transaction_id": metadados.get("transaction_id"),
            "component_name": metadados.get("component_name"),
            "application_name": metadados.get("application_name"),
            "team_id": metadados.get("team_id"),
            "responsible_team": metadados.get("responsible_team"),
            "project": metadados.get("project"),
            "tribe": metadados.get("tribe"),
            "application_type": metadados.get("application_type"),
            "application_category": metadados.get("application_category"),
            "criticality": metadados.get("criticality"),
            "environment": metadados.get("environment"),
            "application_status": metadados.get("application_status"),
            "repository": metadados.get("repository"),
            "mongodb_documentation_id": id_mongodb_previa,
            "mongodb_metadata_id": id_mongodb_metadados,
            "registration_status": "pendente_aprovacao",
            "version": 1,
            "is_active_version": True,
            "created_at": agora,
            "updated_at": agora,
        }

        with self._conn.cursor() as cur:
            cur.execute(SQL_INSERIR, dados)
            resultado = cur.fetchone()

        self._conn.commit()

        id_gerado = str(resultado["id"])
        logger.info(
            "Pré-cadastro inserido em '%s' com ID: %s (version=1)",
            TABELA,
            id_gerado,
        )
        return id_gerado

    def buscar_por_event_id(self, event_id: str) -> dict[str, Any] | None:
        """
        Busca o registro mais recente de um event_id.

        Returns:
            dict com o registro encontrado, ou None se não existir.
        """
        with self._conn.cursor() as cur:
            cur.execute(SQL_BUSCAR_POR_EVENT_ID, {"event_id": event_id})
            resultado = cur.fetchone()

        if resultado:
            logger.info("Registro encontrado para event_id: '%s'", event_id)
            return dict(resultado)

        logger.warning("Registro não encontrado para event_id: '%s'", event_id)
        return None