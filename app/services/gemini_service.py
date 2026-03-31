"""
Serviço de integração com a API do Google Gemini.
Atualizado para suportar upload de arquivos (Áudio e Documentos) usando
a File API do Google Generative AI e Roteamento Dinâmico por Planos (Arbitragem).
"""
import os
import tempfile
import google.generativeai as genai
import uuid
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from PIL import Image
from io import BytesIO
from typing import List, Optional,  Any, Dict

from app.core.config import settings
from app.core.logger import setup_logger
from app.services.redis_service import redis_service

logger = setup_logger(__name__)

class GeminiService:
    def __init__(self):
        try:
            genai.configure(api_key=settings.gemini_api_key)
            
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            self.system_instruction = self._load_system_prompt()
            logger.info("Serviço ScreenAI (Base de Arbitragem) inicializado com sucesso.")
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

    def _get_model_for_plan(self, plan_id: int) -> str:
        """
        Regra de Negócio de Arbitragem de API:
        ID 3 (Plus) -> gemini-2.5-pro
        ID 2 (Pro)  -> gemini-2.5-flash
        ID 1 (Free) -> gemini-2.5-flash-lite
        """
        if plan_id == 3:
            return "gemini-2.5-pro"
        elif plan_id == 2:
            return "gemini-2.5-flash"
        else:
            return "gemini-2.5-flash-lite"

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

    async def generate_response_stream(
        self,
        user_id: int,
        plan_id: int,
        session_id: Optional[str] = None,
        user_message: str = "",
        image_bytes: Optional[bytes] = None,
        uploaded_files: Optional[List[Any]] = None
    ):
        """
        Streaming REAL do Gemini (token por token)
        """

        if not session_id:
            session_id = str(uuid.uuid4())

        model_name = self._get_model_for_plan(plan_id)

        model = genai.GenerativeModel(
            model_name=model_name,
            safety_settings=self.safety_settings,
            system_instruction=self.system_instruction
        )

        history = await redis_service.get_history(user_id, session_id)
        chat_session = model.start_chat(history=history)

        content_payload: List[Any] = []

        if uploaded_files:
            content_payload.extend(uploaded_files)

        if image_bytes:
            try:
                img = Image.open(BytesIO(image_bytes))
                content_payload.append(img)
            except Exception as e:
                logger.error(f"Erro ao processar imagem: {str(e)}")

        if user_message:
            content_payload.append(user_message)

        if not content_payload:
            yield {
                "type": "end",
                "text": "",
                "session_id": session_id
            }
            return

        full_text = ""

        try:
            stream = chat_session.send_message(
                content_payload,
                stream=True
            )

            for chunk in stream:
                if not chunk or not hasattr(chunk, "text"):
                    continue

                if chunk.text:
                    full_text += chunk.text

                    yield {
                        "type": "chunk",
                        "text": chunk.text,
                        "full": full_text,
                        "session_id": session_id
                    }

            # salva histórico no final
            await redis_service.save_interaction(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                model_response=full_text
            )

            yield {
                "type": "end",
                "text": full_text,
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"[STREAM ERROR] {str(e)}")

            yield {
                "type": "error",
                "message": "Erro ao gerar resposta."
            }

gemini_service = GeminiService()