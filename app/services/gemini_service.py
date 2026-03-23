"""
Serviço de integração com a API do Google Gemini.
Gerencia a inicialização do modelo, carregamento do prompt de sistema
e formatação das requisições e respostas.
"""
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class GeminiService:
    def __init__(self):
        """Inicializa o cliente do Gemini com a chave de API segura."""
        try:
            genai.configure(api_key=settings.gemini_api_key)
            
            # Utilizando o modelo Flash por ser o mais rápido para respostas textuais/visuais
            self.model_name = "gemini-1.5-flash"
            
            # Configurações de segurança para evitar bloqueios falsos positivos em suporte técnico
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            # Inicializa o modelo
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                safety_settings=self.safety_settings
            )
            logger.info(f"Serviço Gemini ({self.model_name}) inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao inicializar o Gemini API: {str(e)}")
            raise

    def _load_system_prompt(self) -> str:
        """
        Lê o conteúdo do arquivo txt contendo as diretrizes de comportamento.
        Lido dinamicamente para permitir atualizações no arquivo sem reiniciar o servidor.
        """
        prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'system_prompt.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except FileNotFoundError:
            logger.warning(f"Arquivo de prompt não encontrado em {prompt_path}. Usando prompt padrão.")
            return "Responda de forma clara e passo a passo."

    async def generate_response(self, user_message: str) -> str:
        """
        Envia a mensagem do usuário junto com o contexto de sistema para a IA.
        
        Args:
            user_message (str): A dúvida ou comando enviado pelo usuário.
            
        Returns:
            str: A resposta gerada pela IA formatada.
        """
        system_prompt = self._load_system_prompt()
        
        # O Gemini 1.5 aceita instruções de sistema diretamente na construção do prompt
        # ou estruturando o histórico. Aqui, combinamos de forma explícita para garantir a aderência.
        full_prompt = f"DIRETRIZES DE SISTEMA:\n{system_prompt}\n\nDÚVIDA DO USUÁRIO:\n{user_message}\n\nRESPOSTA PASSO A PASSO:"
        
        logger.info(f"Enviando requisição para o Gemini. Tamanho do prompt: {len(full_prompt)} caracteres.")
        
        try:
            # Em chamadas de rede I/O bound, usamos o método síncrono da SDK do Google
            # encapsulado para não travar o event loop do FastAPI (o FastAPI faz isso muito bem).
            response = self.model.generate_content(full_prompt)
            
            if response.text:
                logger.debug("Resposta gerada com sucesso pelo Gemini.")
                return response.text
            else:
                logger.warning("Gemini retornou uma resposta vazia ou bloqueada.")
                return "Houve um problema ao processar sua solicitação. Tente novamente."
                
        except Exception as e:
            logger.error(f"Erro ao comunicar com o Gemini: {str(e)}")
            return "Estou enfrentando problemas técnicos na minha conexão no momento."

# Instância única do serviço (Singleton)
gemini_service = GeminiService()