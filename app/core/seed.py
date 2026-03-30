"""
Seed assíncrono - compatível com SQLAlchemy AsyncSession
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.plan_model import Plan
from app.models.user_model import User
from app.core.logger import setup_logger
from app.core.security import get_password_hash

logger = setup_logger(__name__)


async def seed_plans(db: AsyncSession):
    planos_padrao = [
        {"name": "Free", "price": 0.0, "monthly_credits": 100, "is_active": True},
        {"name": "Pro", "price": 44.90, "monthly_credits": 1500, "is_active": True},
        {"name": "Plus", "price": 89.90, "monthly_credits": 4000, "is_active": True},
    ]

    try:
        for plano_data in planos_padrao:
            result = await db.execute(
                select(Plan).where(Plan.name == plano_data["name"])
            )
            plano_existente = result.scalars().first()

            if not plano_existente:
                novo_plano = Plan(**plano_data)
                db.add(novo_plano)
                logger.info(f"Seed: Plano '{plano_data['name']}' criado.")

        await db.commit()

    except Exception as e:
        await db.rollback()
        logger.error(f"Erro ao executar seed de planos: {str(e)}")


async def create_default_admin(db: AsyncSession):
    admin_email = "admin@frontscreen.ai"

    result = await db.execute(
        select(User).where(User.email == admin_email)
    )
    user = result.scalars().first()

    if not user:
        try:
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_admin=True
            )

            db.add(admin_user)
            await db.commit()
            await db.refresh(admin_user)

            logger.info("Admin criado com sucesso.")

        except Exception as e:
            await db.rollback()
            logger.error(f"Erro ao criar admin: {str(e)}")
            raise
    else:
        logger.info("Admin já existe.")