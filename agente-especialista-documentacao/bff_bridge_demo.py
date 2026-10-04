"""
bff_bridge_demo.py
--------------------
Simula o que o BFF faz: consulta o PostgreSQL (schema normalizado) para
achar o `mongo_content_id` da versao atual de um componente, e usa esse
ID para buscar o conteudo real (campo `sections`) direto no MongoDB,
na colecao `documentos_gerados_previas`.

Reaproveita as conexoes ja existentes no projeto (src.infrastructure),
entao basta colocar este arquivo na RAIZ do projeto
(agente-especialista-documentacao/) e rodar com:

    poetry run python bff_bridge_demo.py
    poetry run python bff_bridge_demo.py cooper-ai-codex-api

Se nenhum nome for passado, usa COMPONENT_NAME do .env.
"""

import json
import logging
import sys

from bson import ObjectId
from bson.errors import InvalidId

from src.infrastructure.mongodb.client import get_database
from src.infrastructure.postgresql.client import get_connection
from src.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def buscar_mongo_content_id_atual(technical_name: str) -> dict | None:
    """
    Passo 1 (PostgreSQL): acha a versao atual (is_current = true) da
    documentation do componente e traz o mongo_content_id do document
    vinculado a ela. E exatamente a consulta que o BFF faria.
    """
    sql = """
        SELECT
            a.technical_name,
            a.criticality,
            d.version,
            d.status        AS documentation_status,
            doc.title        AS document_title,
            doc.mongo_content_id
        FROM application a
        JOIN documentation d   ON d.application_id = a.id
        JOIN document doc      ON doc.documentation_id = d.id
        WHERE a.technical_name = %(technical_name)s
          AND d.is_current = true;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"technical_name": technical_name})
            linha = cur.fetchone()

    return dict(linha) if linha else None


def buscar_sections_no_mongo(mongo_content_id: str) -> list | None:
    """
    Passo 2 (MongoDB): usa o mongo_content_id (que e o _id do
    documento) para buscar o conteudo real em documentos_gerados_previas
    e devolve o campo 'sections'.
    """
    try:
        object_id = ObjectId(mongo_content_id)
    except InvalidId:
        logger.error("mongo_content_id invalido: %s", mongo_content_id)
        return None

    with get_database() as db:
        colecao = db["documentos_gerados_previas"]
        documento = colecao.find_one({"_id": object_id})

    if not documento:
        logger.error(
            "Nenhum documento encontrado em documentos_gerados_previas "
            "com _id=%s", mongo_content_id,
        )
        return None

    return documento.get("sections")


def main() -> None:
    settings = get_settings()
    technical_name = sys.argv[1] if len(sys.argv) > 1 else settings.component_name

    logger.info("=" * 60)
    logger.info("Simulacao BFF: PostgreSQL -> MongoDB")
    logger.info("Componente: %s", technical_name)
    logger.info("=" * 60)

    # Passo 1 — PostgreSQL
    logger.info("\n[1/2] Consultando PostgreSQL (versao atual + mongo_content_id)...")
    linha = buscar_mongo_content_id_atual(technical_name)

    if not linha:
        logger.error(
            "Nao encontrei nenhuma application/documentation 'is_current=true' "
            "para technical_name='%s'. Confira o nome ou rode o agente antes.",
            technical_name,
        )
        return

    logger.info("  technical_name       : %s", linha["technical_name"])
    logger.info("  criticality          : %s", linha["criticality"])
    logger.info("  version (atual)      : %s", linha["version"])
    logger.info("  documentation_status : %s", linha["documentation_status"])
    logger.info("  document_title       : %s", linha["document_title"])
    logger.info("  mongo_content_id     : %s", linha["mongo_content_id"])

    # Passo 2 — MongoDB
    logger.info("\n[2/2] Buscando 'sections' no MongoDB (documentos_gerados_previas)...")
    sections = buscar_sections_no_mongo(linha["mongo_content_id"])

    if sections is None:
        return

    logger.info("\n" + "=" * 60)
    logger.info("SECTIONS ENCONTRADAS (%d)", len(sections) if isinstance(sections, list) else 1)
    logger.info("=" * 60)
    print(json.dumps(sections, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()