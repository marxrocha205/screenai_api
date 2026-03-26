"""
Serviço de integração com a API Text-to-Speech (TTS) da OpenAI.
Responsável por converter texto em áudio neural realista.
"""
import base64
import re
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class TTSService:
    def __init__(self):
        """Inicializa o cliente assíncrono da OpenAI."""
        try:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            
            # tts-1 é o modelo otimizado para baixa latência (ideal para tempo real)
            # tts-1-hd tem mais qualidade, mas demora mais para gerar
            self.model = "tts-1" 
            
            # 'nova' é a voz feminina padrão da OpenAI. 
            # Outras opções: alloy, echo, fable, onyx, shimmer.
            self.voice = "nova" 
            
            logger.info("Serviço OpenAI TTS inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao inicializar o cliente OpenAI: {str(e)}")
            raise

    def _limpar_texto_para_fala(self, texto: str) -> str:
        """
        Remove marcações markdown que a IA usa para formatação visual,
        evitando que o sintetizador leia asteriscos ou hashtags em voz alta.
        """
        texto_limpo = re.sub(r'[*#_]', '', texto)
        return texto_limpo

    async def generate_audio_base64(self, text: str, plan_id: int) -> str:
        """
        Envia o texto para a OpenAI e retorna o áudio MP3 codificado em Base64.
        
        Args:
            text (str): O texto gerado pela IA (ScreenAI).
            
        Returns:
            str: String Base64 do arquivo de áudio, ou string vazia em caso de erro.
        """
        if not text:
            return ""

        # if plan_id == 1:
        #     logger.debug("Utilizador Free (Plano 1). Geração de voz premium ignorada para poupar custos.")
        #     return "" # Retorna vazio. O frontend usará a Web Speech API (gratuita).

        texto_processado = self._limpar_texto_para_fala(text)
        logger.info(f"Solicitando geração de áudio OpenAI para utilizador do Plano {plan_id}...")

        try:
            # Chamada assíncrona para não bloquear o servidor FastAPI
            response = await self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=texto_processado,
                response_format="mp3"
            )
            
            # Lê os bytes binários do MP3 retornado pela OpenAI
            audio_bytes = response.read()
            
            # Converte para Base64 para trafegar via WebSocket com segurança
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            logger.debug("Áudio gerado e convertido para Base64 com sucesso.")
            return audio_base64
            
        except Exception as e:
            logger.error(f"Erro na comunicação com OpenAI TTS: {str(e)}")
            return ""

# Instância Singleton
tts_service = TTSService()