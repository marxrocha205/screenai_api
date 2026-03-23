"""
Serviço de integração com a API do Google Gemini.
Atualizado para suportar upload de arquivos (Áudio e Documentos) usando
a File API do Google Generative AI.
"""
import os
import tempfile
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from PIL import Image
from io import BytesIO
from typing import List, Optional, Union, Any

from app.core.config import settings
from app.core.logger import setup_logger
from app.services.redis_service import redis_service

logger = setup_logger(__name__)

class GeminiService:
    def __init__(self):
        try:
            genai.configure(api_key=settings.gemini_api_key)
            self.model_name = "gemini-1.5-flash"
            
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            self.system_instruction = self._load_system_prompt()
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                safety_settings=self.safety_settings,
                system_instruction=self.system_instruction
            )
            logger.info(f"Serviço ScreenAI ({self.model_name}) inicializado.")
        except Exception as e:
            logger.error(f"Falha ao inicializar o Gemini API: {str(e)}")
            raise

    def _load_system_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'system_prompt.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except FileNotFoundError:
            logger.error(f"Arquivo de prompt não encontrado em {prompt_path}.")
            raise

    async def upload_file_to_gemini(self, file_bytes: bytes, mime_type: str, file_name: str) -> Any:
        """
        Salva o arquivo temporariamente no disco e faz o upload para a File API do Gemini.
        Essencial para PDFs e arquivos de Áudio.
        """
        logger.info(f"Fazendo upload de arquivo para o Gemini: {file_name} ({mime_type})")
        
        # Cria um arquivo temporário no sistema operacional
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        try:
            # Faz o upload para os servidores do Google (expira automaticamente em 48h)
            uploaded_file = genai.upload_file(path=temp_path, mime_type=mime_type)
            logger.debug(f"Upload concluído. URI do arquivo: {uploaded_file.uri}")
            return uploaded_file
        except Exception as e:
            logger.error(f"Erro ao fazer upload do arquivo {file_name} para o Gemini: {str(e)}")
            raise
        finally:
            # Garante que o arquivo temporário seja apagado do nosso servidor para não lotar o disco
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def generate_response(
        self, 
        user_id: int, 
        user_message: str = "", 
        image_bytes: Optional[bytes] = None,
        uploaded_files: Optional[List[Any]] = None
    ) -> str:
        """
        Gera resposta mantendo o histórico, suportando texto, imagem (inline) e arquivos pesados (File API).
        """
        logger.info(f"Processando requisição multimodal para usuário {user_id}.")
        
        history = await redis_service.get_history(user_id)
        chat_session = self.model.start_chat(history=history)
        
        # O payload pode conter strings, imagens PIL ou referências a arquivos no Google (uploaded_files)
        content_payload: List[Any] = []
        
        # Adiciona arquivos pesados (Áudio/Documentos) processados previamente
        if uploaded_files:
            content_payload.extend(uploaded_files)

        # Adiciona imagem inline (Prints de tela do WebSocket)
        if image_bytes:
            try:
                img = Image.open(BytesIO(image_bytes))
                content_payload.append(img)
            except Exception as e:
                logger.error(f"Erro ao processar imagem para usuário {user_id}: {str(e)}")
                return "Tive um problema técnico ao tentar ver sua tela."

        # Adiciona o texto
        if user_message:
            content_payload.append(user_message)
            
        if not content_payload:
             return "Como posso ajudar?"

        try:
            response = chat_session.send_message(content_payload)
            
            if response.text:
                resposta_final = response.text
                
                # Resumo visual para o histórico não ficar poluído com objetos de arquivo
                resumo_interacao = user_message
                if uploaded_files:
                    resumo_interacao += " [Usuário enviou arquivos]"
                if image_bytes:
                    resumo_interacao += " [Usuário enviou imagem da tela]"
                    
                await redis_service.save_interaction(
                    user_id=user_id, 
                    user_message=resumo_interacao.strip(), 
                    model_response=resposta_final
                )
                
                return resposta_final
            else:
                return "Ops, não consegui processar isso."
                
        except Exception as e:
            logger.error(f"Erro na comunicação com Gemini para usuário {user_id}: {str(e)}")
            return "Estou com uma instabilidade técnica agora."

gemini_service = GeminiService()