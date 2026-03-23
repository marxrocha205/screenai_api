"""
Módulo de conexão com o banco de dados.
Configura o motor do SQLAlchemy utilizando a URL fornecida pelas variáveis de ambiente.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# O SQLAlchemy exige que URLs do Postgres comecem com 'postgresql://'
# A Railway às vezes fornece 'postgres://', então fazemos a conversão de segurança.
SQLALCHEMY_DATABASE_URL = settings.database_url
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    # Cria o motor de conexão. Pool pre_ping verifica se a conexão está ativa antes de usá-la.
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("Motor de banco de dados inicializado com sucesso.")
except Exception as e:
    logger.error(f"Erro ao inicializar o banco de dados: {str(e)}")
    raise

def get_db():
    """
    Gerador de dependência para criar e fechar sessões do banco de dados por requisição.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()