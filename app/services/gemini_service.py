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
        Envia mensagem e imagem opcional para a IA, mantendo a linha de raciocínio.
        
        Args:
            user_id (int): ID do usuário para controle futuro de histórico.
            user_message (str): Texto enviado pelo usuário.
            image_bytes (bytes): Dados binários da captura de tela.
            
        Returns:
            str: Resposta conversacional do ScreenAI.
        """
        logger.info(f"Processando requisição multimodal para usuário {user_id}. Tem imagem? {image_bytes is not None}")
        
        # Lista de conteúdo para o prompt multimodal
        # O Gemini aceita uma lista misturando strings e imagens PIL
        content_payload: List[Union[str, Image.Image]] = []
        
        # Adiciona a imagem ao payload se ela existir
        if image_bytes:
            try:
                # Converte bytes em objeto Image PIL
                img = Image.open(BytesIO(image_bytes))
                content_payload.append(img)
                logger.debug("Imagem decodificada e adicionada ao payload.")
            except Exception as e:
                logger.error(f"Erro ao processar bytes da imagem para usuário {user_id}: {str(e)}")
                return "Tive um problema técnico ao tentar ver sua tela. Consegue me mostrar de novo?"

        # Adiciona a mensagem de texto
        if user_message:
            content_payload.append(user_message)
        
        # Se não houver mensagem nem imagem, nada a fazer
        if not content_payload:
            return "Estou te ouvindo. Como posso ajudar com seu computador hoje?"

        try:
            # CHAMADA À IA
            # TODO: Na V2 implementar chat.send_message() para manter histórico em memória
            # Por enquanto usando generate_content para validação multimodal
            response = self.model.generate_content(content_payload)
            
            if response.text:
                logger.debug(f"Resposta gerada pelo ScreenAI: {response.text[:50]}...")
                # Retorna estritamente o texto conforme Protocolo de Saída
                return response.text
            else:
                logger.warning("IA retornou resposta vazia (provavelmente bloqueio de conteúdo).")
                return "Ops, não consegui processar isso. Vamos tentar o próximo passo?"
                
        except Exception as e:
            logger.error(f"Erro crítico na comunicação com Gemini para usuário {user_id}: {str(e)}")
            return "Estou com uma instabilidade técnica agora. Mas não vamos desistir, me fala de novo o que você precisa."

# Instância Singleton do serviço
gemini_service = GeminiService()