"""
Serviço gerenciador de conexões WebSocket.
Implementa a lógica para aceitar conexões, armazenar clientes ativos,
enviar mensagens individuais e desconectar usuários de forma limpa.
"""
from fastapi import WebSocket
from typing import Dict
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class ConnectionManager:
    def __init__(self):
        # Dicionário para mapear o ID do usuário à sua conexão ativa
        # Formato: {user_id: WebSocket}
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """
        Aceita a conexão e a registra no dicionário de conexões ativas.
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"Usuário {user_id} conectado ao WebSocket. Total ativo: {len(self.active_connections)}")

    def disconnect(self, user_id: int):
        """
        Remove o usuário do dicionário de conexões ativas.
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"Usuário {user_id} desconectado. Total ativo: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, user_id: int):
        """
        Envia uma mensagem no formato JSON exclusivamente para um usuário.
        """
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                logger.debug(f"Mensagem enviada para usuário {user_id}: {message}")
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para usuário {user_id}: {str(e)}")
                self.disconnect(user_id)
        else:
            logger.warning(f"Tentativa de envio de mensagem para usuário {user_id} não conectado.")

# Instância global gerenciadora (Singleton)
manager = ConnectionManager()