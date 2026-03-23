"""
Controlador de rotas para o WebSocket.
Gerencia a conexão do usuário e o loop infinito de troca de mensagens.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_manager import manager
from app.core.security import verify_ws_token
from app.core.logger import setup_logger
from app.services.gemini_service import gemini_service

logger = setup_logger(__name__)
router = APIRouter(prefix="/ws", tags=["Tempo Real"])

@router.websocket("/assistente")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    user = verify_ws_token(token)
    await manager.connect(websocket, user.id)
    
    try:
        while True:
            data = await websocket.receive_json()
            tipo_mensagem = data.get("type", "unknown")
            conteudo = data.get("content", "")
            
            logger.info(f"Mensagem tipo '{tipo_mensagem}' recebida do usuário {user.id}")
            
            # Lógica de roteamento da mensagem
            if tipo_mensagem == "text":
                # Envia o texto para a IA e aguarda a resposta
                resposta_ia = await gemini_service.generate_response(user_message=conteudo)
                
                # Monta a estrutura de resposta para o frontend
                resposta_final = {
                    "type": "ai_response",
                    "message": resposta_ia
                }
                
                # Devolve para o usuário via WebSocket
                await manager.send_personal_message(resposta_final, user.id)
                
            else:
                logger.warning(f"Tipo de mensagem não suportado ainda: {tipo_mensagem}")
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Formato de dado não compreendido."
                }, user.id)
            
    except WebSocketDisconnect:
        logger.warning(f"Usuário {user.id} encerrou a conexão inesperadamente.")
        manager.disconnect(user.id)
    except Exception as e:
        logger.error(f"Erro crítico no loop do WebSocket para usuário {user.id}: {str(e)}")
        manager.disconnect(user.id)