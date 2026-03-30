"""
Serviço de integração com o Redis.
Responsável por armazenar e recuperar o histórico de conversas (Contexto)
para manter a linha de raciocínio da IA em tempo real.
Agora com suporte a isolamento de contexto por Sessão (session_id).
"""
import json
import redis.asyncio as aioredis
from typing import List, Dict, Any, Optional

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

    def _get_key(self, user_id: int, session_id: Optional[str] = None) -> str:
        """
        Padroniza a chave de armazenamento no Redis.
        Se session_id for fornecido, isola o histórico para aquela conversa específica.
        """
        if session_id:
            return f"chat_history:user:{user_id}:session:{session_id}"
        # Fallback de compatibilidade caso alguma parte do sistema não passe session_id
        return f"chat_history:user:{user_id}"

    async def get_history(self, user_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Recupera o histórico de conversa específico de uma sessão do usuário.
        
        Args:
            user_id (int): ID do usuário.
            session_id (str, optional): ID da conversa para isolar o contexto.
            
        Returns:
            List[Dict]: Lista de mensagens no formato exigido pelo modelo.
        """
        key = self._get_key(user_id, session_id)
        try:
            history_str = await self.redis.get(key)
            if history_str:
                logger.debug(f"Histórico recuperado para usuário {user_id}, sessão {session_id}.")
                return json.loads(history_str)
            return []
        except Exception as e:
            logger.error(f"Erro ao ler histórico do Redis para usuário {user_id}: {str(e)}")
            return []

    async def save_interaction(self, user_id: int, user_message: str, model_response: str, session_id: Optional[str] = None):
        """
        Salva uma nova interação (pergunta do usuário e resposta da IA) no histórico da sessão.
        
        Args:
            user_id (int): ID do usuário.
            user_message (str): O que o usuário enviou.
            model_response (str): A resposta gerada pela IA.
            session_id (str, optional): ID da conversa ativa.
        """
        key = self._get_key(user_id, session_id)
        try:
            # 1. Recupera o histórico atual DESTA sessão
            history = await self.get_history(user_id, session_id)
            
            # 2. Adiciona a nova interação formatada para o Gemini
            if user_message:
                history.append({"role": "user", "parts": [user_message]})
            else:
                history.append({"role": "user", "parts": ["[Usuário enviou uma captura de tela sem texto]"]})
                
            history.append({"role": "model", "parts": [model_response]})
            
            # 3. Limita o tamanho do histórico para não estourar o limite de tokens da IA (ex: ultimas 10 interacoes)
            if len(history) > 20:
                history = history[-20:]
            
            # 4. Salva de volta no Redis com tempo de expiração renovado
            await self.redis.set(key, json.dumps(history), ex=self.ttl_seconds)
            logger.info(f"Interação salva no histórico do usuário {user_id}, sessão {session_id}.")
            
        except Exception as e:
            logger.error(f"Erro ao salvar histórico no Redis para usuário {user_id}: {str(e)}")

    async def clear_history(self, user_id: int, session_id: Optional[str] = None):
        """Limpa o histórico de uma sessão específica."""
        key = self._get_key(user_id, session_id)
        await self.redis.delete(key)
        logger.info(f"Histórico limpo para usuário {user_id}, sessão {session_id}.")

    async def check_rate_limit(self, user_id: int, max_requests: int = 10, window_seconds: int = 60) -> bool:
        """
        Verifica se o utilizador excedeu o limite de pedidos numa janela de tempo.
        Utiliza a operação atómica INCR do Redis para evitar 'race conditions'.
        """
        # IMPORTANTE: O rate limit continua sendo por usuário global, e NÃO por sessão.
        # Um usuário não deve poder contornar o limite criando novas conversas.
        key = f"rate_limit:user:{user_id}"
        
        try:
            current_requests = await self.redis.incr(key)
            
            if current_requests == 1:
                await self.redis.expire(key, window_seconds)
                
            if current_requests > max_requests:
                logger.warning(f"Rate limit excedido para o utilizador {user_id}. Pedidos: {current_requests}/{max_requests}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Erro ao verificar rate limit no Redis: {str(e)}")
            return True
        # -------------------------------
    # 🔴 CONTROLE DE CANCELAMENTO STREAM
    # -------------------------------

    def _get_cancel_key(self, session_id: str) -> str:
        return f"stream_cancel:{session_id}"

    async def cancel_stream(self, session_id: str):
        """
        Marca uma stream como cancelada.
        TTL curto para evitar lixo no Redis.
        """
        try:
            await self.redis.set(self._get_cancel_key(session_id), "1", ex=60)
            logger.info(f"Stream cancelada: sessão {session_id}")
        except Exception as e:
            logger.error(f"Erro ao cancelar stream: {str(e)}")

    async def is_stream_cancelled(self, session_id: str) -> bool:
        """
        Verifica se a stream foi cancelada.
        """
        try:
            exists = await self.redis.exists(self._get_cancel_key(session_id))
            return exists == 1
        except Exception as e:
            logger.error(f"Erro ao verificar cancelamento: {str(e)}")
            return False

    async def clear_stream_cancel(self, session_id: str):
        """
        Remove flag de cancelamento após uso.
        """
        try:
            await self.redis.delete(self._get_cancel_key(session_id))
        except Exception as e:
            logger.error(f"Erro ao limpar cancelamento: {str(e)}")
# Instância global Singleton
redis_service = RedisService()