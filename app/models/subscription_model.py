"""
Modelo de dados para as Assinaturas dos usuários.
Gerencia o saldo de créditos atual e o status financeiro da conta.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Chaves Estrangeiras conectando as tabelas
    # unique=True garante que um usuário tenha apenas uma assinatura ativa por vez
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    
    # Status financeiro: 'active', 'past_due', 'canceled'
    status = Column(String, default="active", nullable=False)
    
    # O "saldo" atual do usuário. É daqui que o pedágio vai descontar.
    remaining_credits = Column(Integer, default=0, nullable=False)
    
    # Datas de controle de ciclo
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos para facilitar consultas cruzadas no SQLAlchemy
    user = relationship("User", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")