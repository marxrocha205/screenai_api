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
    resend_api_key: str | None = None
    alphapay_api_token: str | None = None
    
    smtp_server: str = "smtp.hostinger.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

# Instância global de configurações
settings = Settings()