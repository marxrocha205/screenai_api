"""
Serviço de envio de emails assíncrono via API REST (Resend).
Bypass automático de bloqueios de portas SMTP em provedores Cloud (Railway).
"""
import resend
import asyncio
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class EmailService:
    def __init__(self):
        # O Pydantic (settings) precisa ter a variável resend_api_key criada no app/core/config.py
        self.api_key = getattr(settings, "resend_api_key", None)
        if self.api_key:
            resend.api_key = self.api_key

    async def send_verification_code(self, to_email: str, code: str) -> bool:
        """
        Envia o código de verificação via API HTTP (Porta 443).
        """
        if not self.api_key:
            logger.warning(f"⚠️ MODO DEV: Simulação de email para {to_email}. Código: {code}")
            return True

        # Email HTML Bonito
        html_body = f"""
        <div style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
            <h2>Bem-vindo à ScreenAI!</h2>
            <p>O seu código de segurança é:</p>
            <h1 style="background: #f4f4f4; padding: 10px; letter-spacing: 5px;">{code}</h1>
            <p style="color: #666; font-size: 12px;">Este código expira em 15 minutos.</p>
        </div>
        """

        params = {
            "from": f"ScreenAI <{settings.smtp_username}>", # O seu email pago da Hostinger
            "to": [to_email],
            "subject": "O seu código de verificação - ScreenAI",
            "html": html_body,
        }

        try:
            # Envia via API (Nunca é bloqueado pela Railway)
            await asyncio.to_thread(resend.Emails.send, params)
            logger.info(f"✅ Email via API enviado com sucesso para {to_email}")
            return True
        except Exception as e:
            logger.error(f"❌ Falha ao enviar email via API: {str(e)}")
            return False
        
        
    async def send_billing_alert(self, to_email: str, alert_type: str, days: int = 0):
        """Envia alertas automáticos de vencimento e carência."""
        if not self.api_key:
            return True

        subjects = {
            "expiring_soon": "Sua assinatura ScreenAI vence em 5 dias",
            "expired": "Assinatura Vencida - Período de Carência",
            "downgraded": "Sua conta retornou para o Plano Free"
        }

        html_bodies = {
            "expiring_soon": f"<p>Olá! Faltam apenas 5 dias para a renovação do seu plano. Garanta seu pagamento para não perder os recursos Premium!</p>",
            "expired": f"<p>Olá! Não identificamos o pagamento da sua assinatura. Você tem 2 dias de carência para pagar antes de voltar ao plano Free.</p>",
            "downgraded": f"<p>Olá. Como o pagamento não foi confirmado após a carência, sua conta retornou para o plano Free. Faça o upgrade a qualquer momento!</p>"
        }

        params = {
            "from": f"ScreenAI <{settings.smtp_username}>",
            "to": [to_email],
            "subject": subjects.get(alert_type, "Aviso da Conta"),
            "html": html_bodies.get(alert_type, ""),
        }
        try:
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            logger.error(f"Erro ao enviar email de billing: {e}")        

email_service = EmailService()