"""
Serviço de integração com o Redis.
Responsável por armazenar e recuperar o histórico de conversas (Contexto)
para manter a linha de raciocínio da IA em tempo real.
"""
import json
import redis.asyncio as aioredis
from typing import List, Dict, Any

from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class RedisService:
    def __init__(self):
        """Inicializa o pool de conexões assíncronas com o Redis."""
        try:
            self.redis = aioredis.from_url(
                settings.redis_url, 
                encoding="utf-8", 
                decode_responses=True
            )
            # Define o tempo de expiração do histórico (ex: 1 hora de inatividade)
            self.ttl_seconds = 3600
            logger.info("Conexão com Redis estabelecida com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao conectar no Redis: {str(e)}")
            raise

    def _get_key(self, user_id: int) -> str:
        """Padroniza a chave de armazenamento no Redis."""
        return f"chat_history:user:{user_id}"

    async def get_history(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Recupera o histórico de conversa do usuário.
        
        Args:
            user_id (int): ID do usuário.
            
        Returns:
            List[Dict]: Lista de mensagens no formato exigido pelo modelo.
        """
        key = self._get_key(user_id)
        try:
            history_str = await self.redis.get(key)
            if history_str:
                logger.debug(f"Histórico recuperado para usuário {user_id}.")
                return json.loads(history_str)
            return []
        except Exception as e:
            logger.error(f"Erro ao ler histórico do Redis para usuário {user_id}: {str(e)}")
            return []

    async def save_interaction(self, user_id: int, user_message: str, model_response: str):
        """
        Salva uma nova interação (pergunta do usuário e resposta da IA) no histórico.
        
        Args:
            user_id (int): ID do usuário.
            user_message (str): O que o usuário enviou.
            model_response (str): A resposta gerada pela IA.
        """
        key = self._get_key(user_id)
        try:
            # 1. Recupera o histórico atual
            history = await self.get_history(user_id)
            
            # 2. Adiciona a nova interação formatada para o Gemini
            # Nota: Não salvamos imagens no Redis por questões de tamanho e custo de memória.
            # O ScreenAI precisa da imagem atual para reagir, não do histórico de telas passadas.
            if user_message:
                history.append({"role": "user", "parts": [user_message]})
            else:
                history.append({"role": "user", "parts": ["[Usuário enviou uma captura de tela sem texto]"]})
                
            history.append({"role": "model", "parts": [model_response]})
            
            # 3. Limita o tamanho do histórico para não estourar o limite de tokens da IA (ex: ultimas 10 interacoes)
            # Cada interação são 2 itens (user + model), então pegamos os últimos 20 itens.
            if len(history) > 20:
                history = history[-20:]
            
            # 4. Salva de volta no Redis com tempo de expiração renovado
            await self.redis.set(key, json.dumps(history), ex=self.ttl_seconds)
            logger.info(f"Interação salva no histórico do usuário {user_id}.")
            
        except Exception as e:
            logger.error(f"Erro ao salvar histórico no Redis para usuário {user_id}: {str(e)}")

    async def clear_history(self, user_id: int):
        """Limpa o histórico de um usuário (útil quando o objetivo é concluído)."""
        key = self._get_key(user_id)
        await self.redis.delete(key)
        logger.info(f"Histórico limpo para usuário {user_id}.")

# Instância global Singleton
redis_service = RedisService()