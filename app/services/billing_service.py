"""
Serviço de Faturação e Controlo de Créditos (O Pedágio).
Traduz regras de negócio em consumo de energia de IA.
Refatorado para SQLAlchemy 2.0 (Assíncrono).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.models.subscription_model import Subscription
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------
# REGRAS DE NEGÓCIO: TABELA DE CUSTOS
# ---------------------------------------------------------
COST_TEXT_ONLY = 1
COST_IMAGE_ANALYSIS = 5
COST_PREMIUM_VOICE = 50

class BillingService:
    
    def calculate_interaction_cost(self, has_image: bool = False, use_premium_voice: bool = False) -> int:
        """Calcula o custo total da interação em créditos."""
        total_cost = COST_TEXT_ONLY
        if has_image:
            total_cost += COST_IMAGE_ANALYSIS
        if use_premium_voice:
            total_cost += COST_PREMIUM_VOICE
        return total_cost

    async def check_balance(self, db: AsyncSession, user_id: int, required_credits: int) -> bool:
        """Verifica se o utilizador tem saldo suficiente ANTES de executar."""
        result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        subscription = result.scalars().first()
        
        if not subscription or subscription.status != "active":
            return False
            
        return subscription.remaining_credits >= required_credits

    async def deduct_credits(self, db: AsyncSession, user_id: int, amount: int) -> bool:
        """Abate os créditos da conta do utilizador."""
        try:
            result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalars().first()
            
            if not subscription or subscription.remaining_credits < amount:
                logger.warning(f"Tentativa de dedução falhou: Utilizador {user_id} sem saldo.")
                return False
                
            subscription.remaining_credits -= amount
            await db.commit()
            return True
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Erro ao deduzir créditos: {str(e)}")
            return False

    async def refund_credits(self, db: AsyncSession, user_id: int, amount: int) -> bool:
        """
        Devolve os créditos ao utilizador caso ocorra uma falha técnica no processamento (Worker).
        """
        try:
            result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalars().first()
            
            if subscription:
                subscription.remaining_credits += amount
                await db.commit()
                logger.info(f"Reembolso efetuado: {amount} créditos devolvidos ao Utilizador {user_id}.")
                return True
            return False
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Erro ao reembolsar créditos do utilizador {user_id}: {str(e)}")
            return False

# Instância Singleton
billing_service = BillingService()