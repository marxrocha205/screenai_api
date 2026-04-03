import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.subscription_model import Subscription
from app.models.user_model import User
from app.services.email_service import email_service
from app.core.logger import setup_logger

logger = setup_logger(__name__)

async def check_expirations():
    """Verifica vencimentos, envia e-mails e aplica o Downgrade de Carência."""
    logger.info("Executando o Cron Job diário de Assinaturas...")
    
    async with AsyncSessionLocal() as db:
        hoje = datetime.utcnow().date()
        
        # Pega todas as assinaturas pagas (Plano > 1) que possuem data de vencimento
        result = await db.execute(
            select(Subscription, User.email)
            .join(User, User.id == Subscription.user_id)
            .where(Subscription.plan_id > 1)
            .where(Subscription.expires_at.isnot(None))
        )
        assinaturas = result.all()

        for sub, user_email in assinaturas:
            vencimento = sub.expires_at.date()
            dias_restantes = (vencimento - hoje).days

            # 1. Falta 5 dias (Aviso Prévio)
            if dias_restantes == 5:
                await email_service.send_billing_alert(user_email, "expiring_soon")
            
            # 2. Venceu hoje (Entra nos 2 dias de Carência)
            elif dias_restantes == 0:
                await email_service.send_billing_alert(user_email, "expired")
            
            # 3. Acabou a Carência (-2 dias). Volta para o Plano Free (1)
            elif dias_restantes <= -2:
                sub.plan_id = 1 # Downgrade para Free
                sub.expires_at = None # O Free não expira
                # Não tiramos os créditos imediatamente por compaixão, mas ele já está travado no Free
                await db.commit()
                await email_service.send_billing_alert(user_email, "downgraded")
                logger.info(f"Usuário {sub.user_id} rebaixado para Free (Carência esgotada).")

async def start_daily_cron():
    """Loop infinito que roda 1x por dia (86400 segundos)."""
    while True:
        try:
            await check_expirations()
        except Exception as e:
            logger.error(f"Erro no Cron Job: {e}")
        # Pausa por 24 horas
        await asyncio.sleep(86400)