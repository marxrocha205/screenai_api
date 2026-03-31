"""
Módulo de conexão com o banco de dados.
Configura o motor do SQLAlchemy utilizando a URL fornecida pelas variáveis de ambiente.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from app.core.logger import setup_logger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

logger = setup_logger(__name__)


# O driver assíncrono é 'postgresql+asyncpg'
DATABASE_URL = settings.database_url
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
# Se já tiver 'postgresql://' mas NÃO tiver '+asyncpg', nós adicionamos.
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
try:
    # Engine assíncrono com pool otimizado
    engine = create_async_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10
    )
    
    # Gerador de sessões assíncronas
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    
    Base = declarative_base()
    logger.info("Motor de base de dados ASSÍNCRONO inicializado.")
except Exception as e:
    logger.error(f"Erro ao inicializar DB assíncrono: {str(e)}")
    raise

async def get_db():
    """Dependência para FastAPI que fornece uma sessão assíncrona."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()