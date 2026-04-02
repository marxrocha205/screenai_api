


import aiosmtplib
from email.message import EmailMessage
from app.core.logger import setup_logger
from app.core.config import settings
logger = setup_logger(__name__)

class EmailSerivce:
    async def send_verification_code(self, to_email: str, code: str) -> bool : 
        
        
        subject = "O seu código de verificação - ScreenAI"
        body = f"""
        Olá,
               
        O seu código de verificação chegou: {code}
        
        este código expira em 15 minutos. Se não solicitou este registro, ignore este email
        
        Bem vindo ao futuro
        Equipe ScreenAI
        """
        
        
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = settings.smtp_username
        msg["To"] = to_email
        porta = settings.smtp_port
        usa_ssl_implicito = (porta == 465)
        usa_starttls = (porta == 587)
        
        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_server,
                port=porta,
                use_tls=usa_ssl_implicito,
                start_tls=usa_starttls,
                username= settings.smtp_username,
                password=settings.smtp_password,
                timeout=15
                
            )
            logger.info(f"Email de verificacao enviado com sucesso para {to_email}")
            return True
        except Exception as e: 
            logger.error(f"Falha ao enviar email para {to_email}: {str(e)}")
            return False
        
        
        
email_service = EmailSerivce()
    