from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import base64

from app.services.websocket_manager import manager
from app.core.security import verify_ws_token
from app.core.logger import setup_logger
from app.services.stt_service import stt_service
from app.services.redis_service import redis_service
from app.services.queue_service import queue_service

logger = setup_logger(__name__)
router = APIRouter(prefix="/ws", tags=["Tempo Real"])


@router.websocket("/assistente")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):

    try:
        user_data = verify_ws_token(token)
        user_id = user_data["id"] if isinstance(user_data, dict) else user_data.id
        plan_id = user_data.get("plan_id", 1) if isinstance(user_data, dict) else getattr(user_data, "plan_id", 1)
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)

    try:
        while True:
            data = await websocket.receive_json()

            # 🔴 STOP primeiro
            if data.get("type") == "stop":
                session_id = data.get("session_id")

                if session_id:
                    await redis_service.cancel_stream(session_id)

                continue

            # 🚦 Rate limit
            is_allowed = await redis_service.check_rate_limit(
                user_id=user_id, max_requests=10, window_seconds=60
            )

            if not is_allowed:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Muitas mensagens. Aguarde."
                }, user_id)
                continue

            session_id = data.get("session_id")
            user_text = data.get("text", "")
            image_b64 = data.get("image_base64")
            audio_b64 = data.get("audio_base64")

            # 🎤 STT
            if audio_b64:
                texto = await stt_service.transcribe_base64(audio_b64)
                if texto:
                    user_text = texto

            # 🖼️ imagem
            image_bytes = None
            if image_b64:
                try:
                    if "," in image_b64:
                        image_b64 = image_b64.split(",")[1]
                    image_bytes = base64.b64decode(image_b64)
                except Exception:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Erro na imagem."
                    }, user_id)
                    continue

            # 🚀 fila
            await queue_service.enqueue({
                "user_id": user_id,
                "plan_id": plan_id,
                "text": user_text,
                "session_id": session_id,
                "image_bytes": image_bytes
            })

            await manager.send_personal_message({
                "type": "processing",
                "message": "Processando..."
            }, user_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)