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

email_service = EmailService()