"""
Módulo de conexão com o banco de dados.
Configura o motor ASSÍNCRONO do SQLAlchemy utilizando a URL fornecida.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

SQLALCHEMY_DATABASE_URL = settings.database_url

# Normalização da URL para o driver assíncrono
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Garante que a URL usa o driver asyncpg
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

try:
    # Cria o motor de conexão assíncrono.
    engine = create_async_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
    
    # SessionLocal agora gera AsyncSession
    AsyncSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine, 
        class_=AsyncSession
    )
    Base = declarative_base()
    logger.info("Motor de banco de dados ASSÍNCRONO inicializado com sucesso.")
except Exception as e:
    logger.error(f"Erro ao inicializar o banco de dados: {str(e)}")
    raise

async def get_db():
    """
    Gerador de dependência assíncrono para injetar o DB nas rotas.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

# Mantido por retrocompatibilidade temporária com scripts síncronos (ex: seed.py)
# Recomendado não usar nas rotas FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
try:
    SYNC_URL = SQLALCHEMY_DATABASE_URL.replace("+asyncpg", "")
    sync_engine = create_engine(SYNC_URL, pool_pre_ping=True)
    SessionLocalSync = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
except Exception:
    pass