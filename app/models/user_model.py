"""
Modelo de dados do Usuário (Entidade do Banco de Dados).
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    full_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False) 
    credits = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relacionamento 1:1 com a tabela de assinaturas.
    # uselist=False garante que o SQLAlchemy retorne um único objeto, não uma lista.
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")