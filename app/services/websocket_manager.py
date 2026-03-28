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
        # Dicionário mapeando: user_id -> instância do WebSocket ativo
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        
        # -------------------------------------------------------------
        # BLOQUEIO DE CONCORRÊNCIA (Card 2.3)
        # -------------------------------------------------------------
        if user_id in self.active_connections:
            logger.warning(f"Usuário {user_id} abriu nova sessão. Derrubando a conexão anterior.")
            old_ws = self.active_connections[user_id]
            try:
                # Envia um aviso claro para a aba/dispositivo antigo antes de cortar a linha
                await old_ws.send_json({
                    "type": "error",
                    "message": "Sessão encerrada. Sua conta foi conectada em outro dispositivo ou aba."
                })
                # 1008 = Policy Violation (Violação de Política do Servidor)
                await old_ws.close(code=1008) 
            except Exception as e:
                logger.error(f"Erro ao fechar conexão antiga do usuário {user_id}: {str(e)}")
        # -------------------------------------------------------------

        # Registra a nova conexão como a oficial
        self.active_connections[user_id] = websocket
        logger.info(f"Usuário {user_id} registrado. Total de conexões ativas: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Remove a conexão do dicionário.
        Dica de Engenharia: Só removemos se o websocket que está pedindo para sair 
        for exatamente o mesmo que está registrado. Isso evita que a morte da conexão 
        antiga apague acidentalmente a nova conexão recém-criada.
        """
        if user_id in self.active_connections and self.active_connections[user_id] == websocket:
            del self.active_connections[user_id]
            logger.info(f"Usuário {user_id} desconectado. Total ativas: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para usuário {user_id}: {str(e)}")
                self.disconnect(websocket, user_id)
                
    def get_active_stats(self):
        """Retorna estatísticas das conexões para o painel de admin."""
        return {
            "total_active": len(self.active_connections),
            "active_users": [user_id for user_id in self.active_connections.keys()]
        }

# Instância Singleton
manager = ConnectionManager()