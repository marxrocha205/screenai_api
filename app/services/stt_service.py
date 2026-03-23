"""
Serviço de integração com a API Speech-to-Text (STT) da OpenAI (Whisper).
Responsável por receber arquivos de áudio ou dados em Base64 e convertê-los em texto.
"""
import base64
import tempfile
import os
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class STTService:
    def __init__(self):
        """Inicializa o cliente assíncrono da OpenAI."""
        try:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "whisper-1"
            logger.info("Serviço OpenAI STT (Whisper) inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao inicializar o cliente OpenAI STT: {str(e)}")
            raise

    async def transcribe_audio_file(self, file_bytes: bytes, suffix: str = ".webm") -> str:
        """
        Transcreve um arquivo de áudio binário para texto.
        A API do Whisper exige que o arquivo tenha um nome no sistema operacional,
        por isso usamos um arquivo temporário.
        """
        logger.info("Iniciando transcrição de áudio via Whisper...")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
            temp_audio.write(file_bytes)
            temp_path = temp_audio.name

        try:
            with open(temp_path, "rb") as audio_file:
                # O parâmetro language="pt" otimiza a velocidade e precisão para português
                response = await self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language="pt" 
                )
            
            texto_transcrito = response.text
            logger.debug(f"Áudio transcrito com sucesso: '{texto_transcrito}'")
            return texto_transcrito
            
        except Exception as e:
            logger.error(f"Erro na comunicação com OpenAI Whisper: {str(e)}")
            return ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def transcribe_base64(self, audio_b64: str) -> str:
        """
        Desempacota um áudio em Base64 recebido via WebSocket e envia para transcrição.
        """
        if not audio_b64:
            return ""
            
        try:
            # Remove o cabeçalho 'data:audio/webm;base64,' se o frontend enviar
            if "," in audio_b64:
                audio_b64 = audio_b64.split(",")[1]
                
            audio_bytes = base64.b64decode(audio_b64)
            return await self.transcribe_audio_file(audio_bytes)
        except Exception as e:
            logger.error(f"Erro ao decodificar Base64 do áudio: {str(e)}")
            return ""

# Instância Singleton
stt_service = STTService()