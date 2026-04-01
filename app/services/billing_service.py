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

# Tabela de Custos (Regras de Negócio Oficiais)
COST_TEXT_ONLY = 1
COST_IMAGE_ANALYSIS = 5
COST_PREMIUM_VOICE = 50

class BillingService:
    
    def calculate_interaction_cost(self, has_image: bool = False, use_premium_voice: bool = False) -> int:
        """
        Calcula o custo total da interação em créditos.
        A base é sempre 1 crédito (processamento de texto).
        """
        total_cost = COST_TEXT_ONLY
        
        if has_image:
            total_cost += COST_IMAGE_ANALYSIS
            
        if use_premium_voice:
            total_cost += COST_PREMIUM_VOICE
            
        return total_cost

    async def check_balance(self, db: AsyncSession, user_id: int, required_credits: int) -> bool:
        """
        Verifica se o utilizador tem saldo suficiente para a operação ANTES de a executar.
        """
        result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        subscription = result.scalars().first()
        
        if not subscription or subscription.status != "active":
            return False
            
        return subscription.remaining_credits >= required_credits

    async def deduct_credits(self, db: AsyncSession, user_id: int, amount: int) -> bool:
        """
        Abate os créditos da conta do utilizador de forma segura.
        """
        try:
            result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalars().first()
            
            if not subscription or subscription.remaining_credits < amount:
                logger.warning(f"Tentativa de dedução falhou: Utilizador {user_id} sem saldo suficiente.")
                return False
                
            # Abate o valor
            subscription.remaining_credits -= amount
            await db.commit()
            
            logger.info(f"Cobrança: {amount} créditos deduzidos do Utilizador {user_id}. Saldo atual: {subscription.remaining_credits}")
            return True
            
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Erro na base de dados ao deduzir créditos do utilizador {user_id}: {str(e)}")
            return False

# Instância Singleton
billing_service = BillingService()