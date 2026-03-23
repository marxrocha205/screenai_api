"""
Serviço de integração com a API do Google Gemini.
Atualizado para suportar entradas multimodais (imagem + texto) e
manter o histórico da conversa (Linha de Raciocínio do Cliente).
"""
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from PIL import Image
from io import BytesIO
from typing import List, Optional, Union

from app.core.config import settings
from app.core.logger import setup_logger
from app.services.redis_service import redis_service

logger = setup_logger(__name__)

class GeminiService:
    def __init__(self):
        """Inicializa o cliente do Gemini e carrega o prompt do sistema."""
        try:
            genai.configure(api_key=settings.gemini_api_key)
            self.model_name = "gemini-1.5-flash"
            
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # Carrega o prompt do sistema uma única vez na inicialização
            self.system_instruction = self._load_system_prompt()
            
            # Configura o modelo com as instruções do sistema fixas
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                safety_settings=self.safety_settings,
                system_instruction=self.system_instruction # Instrução nativa do Gemini 1.5
            )
            logger.info(f"Serviço ScreenAI ({self.model_name}) inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao inicializar o Gemini API: {str(e)}")
            raise

    def _load_system_prompt(self) -> str:
        """Lê o arquivo de prompt do sistema fornecido pelo usuário."""
        prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'system_prompt.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                return content
        except FileNotFoundError:
            logger.error(f"Arquivo de prompt não encontrado em {prompt_path}. Crítico.")
            raise

    async def generate_response(self, user_id: int, user_message: str, image_bytes: Optional[bytes] = None) -> str:
        """
        Envia mensagem multimodal para a IA, injetando o histórico salvo no Redis.
        """
        logger.info(f"Processando requisição multimodal para usuário {user_id}.")
        
        # 1. Recupera o histórico do Redis
        history = await redis_service.get_history(user_id)
        
        # 2. Inicia uma sessão de chat com a SDK do Gemini passando o histórico anterior
        chat_session = self.model.start_chat(history=history)
        
        # 3. Prepara a nova mensagem multimodal (Mensagem Atual)
        content_payload: List[Union[str, Image.Image]] = []
        
        if image_bytes:
            try:
                img = Image.open(BytesIO(image_bytes))
                content_payload.append(img)
            except Exception as e:
                logger.error(f"Erro ao processar imagem para usuário {user_id}: {str(e)}")
                return "Tive um problema técnico ao tentar ver sua tela. Consegue me mostrar de novo?"

        if user_message:
            content_payload.append(user_message)
        elif not image_bytes:
             return "Estou te ouvindo. Como posso ajudar?"

        try:
            # 4. Envia a nova mensagem usando o objeto de chat (que já contém o contexto)
            response = chat_session.send_message(content_payload)
            
            if response.text:
                resposta_final = response.text
                
                # 5. Salva a interação atual no Redis para a próxima rodada
                # Usamos send_message de forma assíncrona/background para não travar a resposta
                await redis_service.save_interaction(
                    user_id=user_id, 
                    user_message=user_message, 
                    model_response=resposta_final
                )
                
                return resposta_final
            else:
                return "Ops, não consegui processar isso. Vamos tentar o próximo passo?"
                
        except Exception as e:
            logger.error(f"Erro crítico na comunicação com Gemini para usuário {user_id}: {str(e)}")
            return "Estou com uma instabilidade técnica agora. Mas não vamos desistir, me fala de novo o que você precisa."
# Instância Singleton do serviço
gemini_service = GeminiService()


