"""
Módulo de configuração da aplicação.
Utiliza Pydantic Settings para validar e carregar variáveis de ambiente.
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    environment: str = "development"
    database_url: str
    secret_key: str = "chave_padrao_para_desenvolvimento"
    gemini_api_key: str
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str
    app_name: str = "assistente-api"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    log_level: str = "DEBUG"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  


# Instância global de configurações
settings = Settings()