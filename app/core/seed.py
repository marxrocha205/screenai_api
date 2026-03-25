"""
Módulo responsável por popular a base de dados com os dados essenciais de negócio (Seed).
Garante que os Planos (Free, Pro, Premium) existam antes de qualquer utilizador se registar.
"""
from sqlalchemy.orm import Session
from app.models.plan_model import Plan
from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.core.logger import setup_logger

logger = setup_logger(__name__)

def seed_plans(db: Session):
    """
    Verifica a existência dos planos padrão e cria-os caso não existam.
    """
    planos_padrao = [
        {
            "name": "Free",
            "price": 0.0,
            "monthly_credits": 100, # Atualizado
            "is_active": True
        },
        {
            "name": "Pro",
            "price": 44.90, # Atualizado
            "monthly_credits": 1500, # Atualizado
            "is_active": True
        },
        {
            "name": "Plus",
            "price": 89.90, # Atualizado
            "monthly_credits": 4000, # Atualizado
            "is_active": True
        }
    ]

    try:
        for plano_data in planos_padrao:
            # Verifica se o plano já existe para evitar duplicações
            plano_existente = db.query(Plan).filter(Plan.name == plano_data["name"]).first()
            
            if not plano_existente:
                novo_plano = Plan(**plano_data)
                db.add(novo_plano)
                logger.info(f"Seed: Plano '{plano_data['name']}' criado com sucesso.")
        
        # Consolida as alterações na base de dados
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao executar o seed de planos: {str(e)}")