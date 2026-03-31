"""
Módulo responsável por popular a base de dados com os dados essenciais de negócio (Seed).
Garante que os Planos (Free, Pro, Premium) existam antes de qualquer utilizador se registar.
"""
from sqlalchemy.orm import Session
from app.models.plan_model import Plan
from app.core.logger import setup_logger
from app.core.security import get_password_hash
from app.models.user_model import User

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
        
def create_default_admin(db: Session):
    """
    Cria um usuário administrador padrão de acordo com o User model atual.
    Removidos campos inexistentes: 'full_name' e 'credits'.
    """
    admin_email = "admin@frontscreen.ai"
    
    # Verifica se o usuário já existe
    user = db.query(User).filter(User.email == admin_email).first()
    
    if not user:
        logger.info(f"Iniciando criação do administrador: {admin_email}")
        try:
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash("admin123"), # Altere via painel depois
                is_active=True,
                is_admin=True
            )
            # Nota: 'created_at' é preenchido automaticamente pelo banco (func.now())
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            logger.info("Sucesso: Usuário administrador criado.")
        except Exception as e:
            db.rollback()
            logger.error(f"Falha ao criar admin: {str(e)}")
            raise e
    else:
        logger.info("Aviso: Usuário administrador já existe.")