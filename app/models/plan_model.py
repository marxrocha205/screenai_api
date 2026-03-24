"""
Modelo de dados para os Planos do sistema (Catálogo).
Define as regras base de créditos e custos para cada nível de acesso.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    
    # Preço do plano (0.00 para Free)
    price = Column(Float, default=0.0, nullable=False)
    
    # Quantidade de créditos que o usuário recebe por mês neste plano
    monthly_credits = Column(Integer, nullable=False)
    
    # Permite desativar um plano antigo sem excluí-lo do banco (Soft Delete lógico)
    is_active = Column(Boolean, default=True)

    # Relacionamento reverso com as assinaturas
    subscriptions = relationship("Subscription", back_populates="plan")