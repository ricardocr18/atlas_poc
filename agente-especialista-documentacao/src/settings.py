"""
settings.py
-----------
Gerenciamento centralizado de configurações da aplicação.

Fase 7: adicionadas variáveis para busca de repositórios (GitHub/GitLab).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações centrais da aplicação."""

    # --- MongoDB ---
    mongodb_uri: str
    mongodb_database: str

    # --- Aplicação ---
    app_env: str = "development"
    app_log_level: str = "INFO"

    # --- OpenAI ---
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.3

    # --- Modo de entrada ---
    input_mode: str = "file"

    # --- Kafka ---
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "atlas-processamento-assincrono-dados"
    kafka_group_id: str = "atlas-documentacao-agent-group"
    kafka_auto_offset_reset: str = "earliest"

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "atlas_documentacao_agente"
    postgres_user: str = "postgres"
    postgres_password: str
    postgres_sslmode: str = "prefer"
    postgres_connect_timeout: int = 10

    # --- Repositório (Fase 7) ---
    repository_url: str = "https://github.com/ricardocr18/rocketseat-nodejs-projeto3SolidGympass"
    repository_provider: str = "github"
    github_token: str | None = None
    gitlab_base_url: str = "https://gitlab.sicredi.net"
    gitlab_token: str | None = None

     # --- Ingestão (Fase 8) ---
    # Conexão de LEITURA, separada do banco onde escrevemos nossos resultados
    ingestao_mongodb_uri: str = "mongodb://localhost:27017"
    ingestao_mongodb_database: str = "atlas_ingestao_api"
 
    # Descoberta manual (decisão explícita para este momento do projeto):
    # o nome do componente a processar vem fixo do .env, não de um
    # mecanismo automático (polling ou Kafka ficam para fase futura)
    component_name: str = "quality-console-back-end"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """Retorna a instância única de Settings (singleton via cache)."""
    return Settings()