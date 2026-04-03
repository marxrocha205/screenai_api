"""
Módulo responsável por popular a base de dados com os dados essenciais de negócio (Seed).
Garante que os Planos e o Administrador existam antes de qualquer utilizador se registar.
Refatorado para a nova Arquitetura Assíncrona (SQLAlchemy 2.0).
"""
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.plan_model import Plan
from app.models.user_model import User
from app.core.logger import setup_logger
from app.core.security import get_password_hash

logger = setup_logger(__name__)

async def seed_data():
    """
    Verifica a existência dos planos e do admin. Cria-os caso o banco de dados esteja vazio.
    Esta função é chamada automaticamente pelo main.py quando o servidor liga.
    """
    async with AsyncSessionLocal() as db:
        try:
            # ---------------------------------------------------------
            # 1. SEED DOS PLANOS DE ASSINATURA
            # ---------------------------------------------------------
            planos_padrao = [
                {
                    "name": "Free",
                    "price": 0.0,
                    "monthly_credits": 100,
                    "is_active": True
                },
                {
                    "name": "Pro",
                    "price": 44.90,
                    "monthly_credits": 1500,
                    "is_active": True
                },
                {
                    "name": "Plus",
                    "price": 89.90,
                    "monthly_credits": 4000,
                    "is_active": True
                }
            ]

            for plano_data in planos_padrao:
                # Nova sintaxe assíncrona para fazer consultas
                result = await db.execute(select(Plan).where(Plan.name == plano_data["name"]))
                plano_existente = result.scalars().first()
                
                if not plano_existente:
                    novo_plano = Plan(**plano_data)
                    db.add(novo_plano)
                    logger.info(f"Seed: Plano '{plano_data['name']}' preparado para criação.")

            # ---------------------------------------------------------
            # 2. SEED DO ADMINISTRADOR PADRÃO
            # ---------------------------------------------------------
            admin_email = "admin@frontscreen.ai"
            
            result_admin = await db.execute(select(User).where(User.email == admin_email))
            admin_existente = result_admin.scalars().first()
            
            if not admin_existente:
                admin_user = User(
                    email=admin_email,
                    hashed_password=get_password_hash("admin123"), # Altere no painel depois
                    is_active=True,
                    is_admin=True
                )
                db.add(admin_user)
                logger.info(f"Seed: Administrador padrão preparado para criação.")

            # ---------------------------------------------------------
            # 3. CONSOLIDAÇÃO (SALVAR NO BANCO)
            # ---------------------------------------------------------
            # O commit guarda tudo de uma só vez para ser mais rápido
            await db.commit()

        except Exception as e:
            await db.rollback()
            logger.error(f"Erro crítico ao executar o seed_data: {str(e)}")