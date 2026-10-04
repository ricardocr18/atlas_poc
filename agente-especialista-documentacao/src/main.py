"""
main.py
--------
Entry point da aplicação atlas-documentacao-agent.

Responsabilidade: inicializar o logging e delegar para o serviço.
Nenhuma lógica de negócio aqui — apenas bootstrap da aplicação.

Execução:
    poetry run python -m src.main
"""

import logging
import sys

from src.application.agent_service import executar_grafo
from src.settings import get_settings

def configurar_logging() -> None:
    """
    Configura o sistema de logging da aplicação.

    Formato: [TIMESTAMP] [LEVEL] [MÓDULO] — mensagem
    O nível é lido do .env via settings (APP_LOG_LEVEL).
    """
    settings = get_settings()
    nivel = getattr(logging, settings.app_log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=nivel,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Ponto de entrada principal da aplicação."""
    configurar_logging()

    logger = logging.getLogger(__name__)
    settings = get_settings()

    logger.info("Atlas Documentacao Agent iniciando...")
    logger.info("Ambiente: %s | Banco: %s", settings.app_env, settings.mongodb_database)

    try:
        executar_grafo()
    except Exception as exc:
        logger.error("Erro fatal na execução: %s", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()