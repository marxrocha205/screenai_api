"""
Controlador de rotas para o WebSocket.
Atualizado para processar payloads multimodais (Texto + Imagem Base64).
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import base64
import json

from app.services.websocket_manager import manager
from app.core.security import verify_ws_token
from app.core.logger import setup_logger
from app.services.gemini_service import gemini_service 
from app.services.tts_service import tts_service
from app.services.stt_service import stt_service


logger = setup_logger(__name__)
router = APIRouter(prefix="/ws", tags=["Tempo Real"])

@router.websocket("/assistente")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """Endpoint WebSocket para o ScreenAI."""
    user = verify_ws_token(token)
    await manager.connect(websocket, user.id)
    
    try:
        while True:
            # Recebe o JSON do frontend
            data = await websocket.receive_json()
            
            # Extrai os dados do payload multimodal
            # Esperamos formato: { "text": "...", "image_base64": "..." }
            user_text = data.get("text", "")
            image_b64 = data.get("image_base64") # Opcional
            audio_b64 = data.get("audio_base64")
            
            logger.info(f"Dados multimodais recebidos do usuário {user.id}.")
            
            image_bytes = None
            
            if audio_b64:
                texto_transcrito = await stt_service.transcribe_base64(audio_b64)
                if texto_transcrito:
                    # O texto transcrito substitui ou complementa o texto digitado
                    user_text = texto_transcrito
                    
                    # Opcional: Avisar o frontend qual foi o texto reconhecido
                    await manager.send_personal_message({
                        "type": "transcription",
                        "message": f"Você disse: {user_text}"
                    }, user.id)
            # Processa a imagem se enviada
            if image_b64:
                try:
                    # Remove o cabeçalho 'data:image/png;base64,' se existir
                    if "," in image_b64:
                        image_b64 = image_b64.split(",")[1]
                    
                    # Decodifica Base64 para bytes binários
                    image_bytes = base64.b64decode(image_b64)
                    logger.debug(f"Imagem Base64 decodificada para binário. Tamanho: {len(image_bytes)} bytes")
                except Exception as e:
                    logger.error(f"Falha na decodificação Base64 da imagem do usuário {user.id}: {str(e)}")
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Erro no formato da imagem enviada."
                    }, user.id)
                    continue # Pula para a próxima iteração do loop
            
            resposta_ia = await gemini_service.generate_response(
                user_id=user.id,
                user_message=user_text,
                image_bytes=image_bytes
            )        
            # Envia para o serviço da IA processar
            audio_b64 = await tts_service.generate_audio_base64(resposta_ia)
            
            # Monta a estrutura multimodal de resposta
            resposta_final = {
                "type": "ai_response",
                "message": resposta_ia,
                "audio_base64": audio_b64 # Novo campo no JSON
            }
            
            # Devolve para o usuário via WebSocket
            await manager.send_personal_message(resposta_final, user.id)
            
    except WebSocketDisconnect:
        logger.warning(f"Usuário {user.id} encerrou a conexão inesperadamente.")
        manager.disconnect(user.id)
    except Exception as e:
        logger.error(f"Erro crítico no loop do WebSocket para usuário {user.id}: {str(e)}")
        manager.disconnect(user.id)