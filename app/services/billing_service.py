from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.models.subscription_model import Subscription
from app.core.logger import setup_logger

logger = setup_logger(__name__)

COST_TEXT_ONLY = 1
COST_IMAGE_ANALYSIS = 5
COST_PREMIUM_VOICE = 50


class BillingService:

    def calculate_interaction_cost(self, has_image: bool = False, use_premium_voice: bool = False) -> int:
        total_cost = COST_TEXT_ONLY

        if has_image:
            total_cost += COST_IMAGE_ANALYSIS

        if use_premium_voice:
            total_cost += COST_PREMIUM_VOICE

        return total_cost

    async def charge_credits(
        self,
        db: AsyncSession,
        user_id: int,
        amount: int
    ) -> bool:
        """
        Cobrança ATÔMICA com lock
        """

        try:
            result = await db.execute(
                select(Subscription)
                .where(Subscription.user_id == user_id)
                .with_for_update()
            )

            subscription = result.scalars().first()

            if not subscription or subscription.status != "active":
                return False

            if subscription.remaining_credits < amount:
                return False

            subscription.remaining_credits -= amount

            await db.commit()

            logger.info(
                f"[SAFE] {amount} créditos cobrados do usuário {user_id}. "
                f"Saldo: {subscription.remaining_credits}"
            )

            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Erro no billing seguro: {str(e)}")
            return False

    async def refund_credits(
        self,
        db: AsyncSession,
        user_id: int,
        amount: int
    ):
        try:
            result = await db.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )
            sub = result.scalars().first()

            if sub:
                sub.remaining_credits += amount
                await db.commit()

                logger.info(f"[REFUND] {amount} créditos devolvidos para {user_id}")

        except Exception as e:
            await db.rollback()
            logger.error(f"Erro ao reembolsar créditos: {str(e)}")


billing_service = BillingService()