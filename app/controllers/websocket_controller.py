"""
Controlador de rotas para o WebSocket.
Gerencia a conexão do usuário e o loop infinito de troca de mensagens.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_manager import manager
from app.core.security import verify_ws_token
from app.core.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/ws", tags=["Tempo Real"])

@router.websocket("/assistente")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    Endpoint principal de comunicação WebSocket bidirecional.
    Exige um token JWT válido na query string (?token=...).
    """
    # 1. Validação do Token antes de aceitar a conexão
    user = verify_ws_token(token)
    
    # 2. Aceita a conexão e registra no manager
    await manager.connect(websocket, user.id)
    
    try:
        # 3. Loop infinito de recebimento de dados
        while True:
            # Aguarda dados enviados pelo frontend (texto ou metadados de imagem/áudio)
            # Utilizamos receive_json pois enviaremos estruturas complexas futuramente
            data = await websocket.receive_json()
            logger.info(f"Dados recebidos do usuário {user.id}: {data}")
            
            # --- ESPAÇO PARA FUTURA INTEGRAÇÃO COM IA ---
            # Aqui no futuro passaremos 'data' para o serviço de IA e áudio.
            # Por enquanto, criamos um eco interativo (Echo Server) para validar a arquitetura.
            
            tipo_mensagem = data.get("type", "unknown")
            conteudo = data.get("content", "")
            
            resposta_simulada = {
                "type": "system_response",
                "message": f"Servidor recebeu sua mensagem do tipo '{tipo_mensagem}': {conteudo}"
            }
            
            # 4. Retorna a resposta ao usuário
            await manager.send_personal_message(resposta_simulada, user.id)
            
    except WebSocketDisconnect:
        # Tratamento nativo quando o cliente fecha a aba ou perde conexão
        logger.warning(f"Usuário {user.id} encerrou a conexão inesperadamente.")
        manager.disconnect(user.id)
    except Exception as e:
        # Captura erros inesperados para evitar queda do servidor
        logger.error(f"Erro crítico no loop do WebSocket para usuário {user.id}: {str(e)}")
        manager.disconnect(user.id)