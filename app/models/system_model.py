from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class AdminAuditLog(Base):
    """
    Regista todas as ações críticas tomadas por administradores no painel.
    Garante o Compliance da plataforma.
    """
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False) # Ex: "UPDATE_CREDITS", "SUSPEND_USER"
    target_entity = Column(String(50), nullable=False) # Ex: "User", "Settings"
    target_id = Column(String(50), nullable=True) # ID do utilizador ou setting afetado
    details = Column(Text, nullable=True) # JSON ou texto livre com o motivo/dados
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamento para podermos buscar o email do admin facilmente
    admin = relationship("User")

class SystemSetting(Base):
    """
    Variáveis dinâmicas globais (Feature Flags, Prompts, Manutenção).
    """
    __tablename__ = "system_settings"

    key = Column(String(50), primary_key=True, index=True) # Ex: "maintenance_mode"
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)