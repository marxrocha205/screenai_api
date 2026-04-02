"""
Serviço de Faturação e Controlo de Créditos (O Pedágio).
Traduz regras de negócio em consumo de energia de IA.
Refatorado para SQLAlchemy 2.0 (Assíncrono) com Recarga Diária Lazy.
"""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.models.subscription_model import Subscription
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# ---------------------------------------------------------
# REGRAS DE NEGÓCIO: TABELA DE CUSTOS (NOVO PLANO)
# ---------------------------------------------------------
COST_TEXT_ONLY = 1
COST_IMAGE_ANALYSIS = 2
COST_PREMIUM_VOICE = 4
FREE_DAILY_TOKENS = 100

class BillingService:
    
    def calculate_interaction_cost(self, has_image: bool = False, use_premium_voice: bool = False) -> int:
        """Calcula o custo total da interação em créditos."""
        total_cost = COST_TEXT_ONLY
        if has_image:
            total_cost += COST_IMAGE_ANALYSIS
        if use_premium_voice:
            total_cost += COST_PREMIUM_VOICE
        return total_cost

    async def _ensure_daily_reset(self, db: AsyncSession, subscription: Subscription) -> None:
        """
        Avaliação Preguiçosa (Lazy Evaluation):
        Verifica se o utilizador é Free (plan_id == 1) e se virou o dia.
        Se sim, recarrega o saldo para 100 e atualiza a data do último reset.
        """
        if subscription.plan_id == 1:
            hoje = date.today()
            # Se for a primeira vez (None) ou se a data gravada for diferente de hoje
            if subscription.last_reset_date != hoje:
                subscription.remaining_credits = FREE_DAILY_TOKENS
                subscription.last_reset_date = hoje
                await db.commit()
                logger.info(f"Recarga Diária (Lazy): Utilizador {subscription.user_id} recebeu {FREE_DAILY_TOKENS} tokens.")

    async def check_balance(self, db: AsyncSession, user_id: int, required_credits: int) -> bool:
        """Verifica se o utilizador tem saldo suficiente ANTES de executar."""
        result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        subscription = result.scalars().first()
        
        if not subscription or subscription.status != "active":
            return False
            
        # MAGIA: Verifica e aplica a recarga diária (se necessário) ANTES de validar o saldo
        await self._ensure_daily_reset(db, subscription)
            
        return subscription.remaining_credits >= required_credits

    async def deduct_credits(self, db: AsyncSession, user_id: int, amount: int) -> bool:
        """Abate os créditos da conta do utilizador."""
        try:
            result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalars().first()
            
            if not subscription:
                return False

            # Por segurança, garante a recarga aqui também (caso o deduct seja chamado diretamente)
            await self._ensure_daily_reset(db, subscription)
            
            if subscription.remaining_credits < amount:
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
        """Devolve os créditos ao utilizador caso ocorra uma falha técnica no Worker."""
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