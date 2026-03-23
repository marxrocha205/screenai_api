import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Adiciona o diretório raiz do projeto ao path do sistema
# Isso é vital para que o Alembic consiga importar os módulos da pasta 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.core.database import Base

# IMPORTANTE: Você deve importar TODOS os seus modelos aqui.
# Se criar um novo modelo no futuro, importe-o neste arquivo.
from app.models.user_model import User

config = context.config

# Configuração de logs padrão do Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Define os metadados para o Alembic ler a estrutura das tabelas
target_metadata = Base.metadata

def get_url():
    """
    Busca a URL do banco de dados das nossas configurações centrais (Pydantic).
    Converte postgres:// para postgresql:// caso a Railway envie o formato antigo.
    """
    url = settings.database_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def run_migrations_offline() -> None:
    """Executa migrações no modo 'offline' (gera o script SQL bruto sem conectar)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Executa migrações no modo 'online' (conecta no banco e aplica as mudanças)."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()