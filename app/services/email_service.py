"""
Serviço de envio de emails assíncrono.
Configurado especificamente para SMTP Hostinger via porta 587 (STARTTLS).
"""
import aiosmtplib
from email.message import EmailMessage
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class EmailService:
    async def send_verification_code(self, to_email: str, code: str) -> bool:
        """
        Envia o código de verificação de 6 dígitos via SMTP Hostinger.
        """
        subject = "O seu código de verificação - ScreenAI"
        body = f"""
Olá,

O seu código de verificação chegou: {code}

Este código expira em 15 minutos. Se não solicitou este registro, ignore este email.

Bem-vindo ao futuro.
Equipe ScreenAI
"""
        
        # Modo de Desenvolvimento (Fallback)
        if not settings.smtp_username or not settings.smtp_password:
            logger.warning(f"⚠️ MODO DEV: Simulação de envio para {to_email}. Código: {code}")
            return True

        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = f"ScreenAI <{settings.smtp_username}>"
        msg["To"] = to_email

        # Configurações para Porta 587 (STARTTLS)
        # Se você decidir voltar para 465, inverta: use_tls=True, start_tls=False
        porta = int(settings.smtp_port)
        usa_tls_direto = (porta == 465)
        usa_starttls = (porta == 587)

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_server,
                port=porta,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=usa_tls_direto,
                start_tls=usa_starttls,
                timeout=30  # Timeout aumentado conforme sugestão da Hostinger
            )
            logger.info(f"✅ Email enviado com sucesso para {to_email} via porta {porta}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro crítico ao enviar email via Hostinger: {str(e)}")
            return False

# Instância Singleton para o projeto
email_service = EmailService()