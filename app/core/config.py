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

    class Config:
        env_file = ".env"
        case_sensitive = False

# Instância global de configurações
settings = Settings()