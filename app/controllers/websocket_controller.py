"""
Controlador de rotas para o WebSocket.
Processa payloads multimodais (Texto + Imagem + Áudio), valida Rate Limit e cobra os Créditos.
Agora com persistência de Histórico de Conversas (PostgreSQL).
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
import base64
import json

from app.services.websocket_manager import manager
from app.core.security import verify_ws_token
from app.core.logger import setup_logger
from app.services.gemini_service import gemini_service 
from app.services.tts_service import tts_service
from app.services.stt_service import stt_service
from app.services.redis_service import redis_service
from app.core.database import SessionLocal
from app.services.billing_service import billing_service
from app.models.subscription_model import Subscription
from app.models.chat_model import ChatSession, ChatMessage  # NOVO: Import das tabelas de histórico

logger = setup_logger(__name__)
router = APIRouter(prefix="/ws", tags=["Tempo Real"])

@router.websocket("/assistente")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """Endpoint WebSocket para o ScreenAI."""
    
    # Validação do utilizador
    try:
        user_data = verify_ws_token(token)
        user_id = user_data["id"] 
        plan_id = user_data["plan_id"]
    except Exception as e:
        logger.error(f"Falha na autenticação do WebSocket: {e}")
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)
    logger.info(f"Usuário {user_id} (Plano: {plan_id}) conectado ao WebSocket.")
    
    # Inicia a ligação ao PostgreSQL que viverá durante toda a sessão WebSocket
    db = SessionLocal()
    
    try:
        # -------------------------------------------------------------------
        # NOVO: Criação da Sessão de Chat ao conectar
        # -------------------------------------------------------------------
        nova_sessao = ChatSession(user_id=user_id, title="Nova Conversa")
        db.add(nova_sessao)
        db.commit()
        db.refresh(nova_sessao)
        session_id = nova_sessao.id
        # -------------------------------------------------------------------

        while True:
            # 1. Recebe o JSON do frontend
            data = await websocket.receive_json()
            
            # 2. Rate Limiting
            is_allowed = await redis_service.check_rate_limit(
                user_id=user_id, max_requests=10, window_seconds=60
            )
            
            if not is_allowed:
                logger.warning(f"Bloqueando mensagem do usuário {user_id} via WebSocket (Rate Limit).")
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Você enviou muitas mensagens rapidamente. Por favor, aguarde um minuto."
                }, user_id)
                continue
                
            # Extrai os dados
            user_text = data.get("text", "")
            image_b64 = data.get("image_base64")
            audio_b64 = data.get("audio_base64")

            # 3. Transcrição de Áudio STT
            if audio_b64:
                texto_transcrito = await stt_service.transcribe_base64(audio_b64)
                if texto_transcrito:
                    user_text = texto_transcrito
                    await manager.send_personal_message({
                        "type": "transcription",
                        "message": f"Você disse: {user_text}"
                    }, user_id)

            # 4. Decodificação da Imagem
            image_bytes = None
            if image_b64:
                try:
                    if "," in image_b64:
                        image_b64 = image_b64.split(",")[1]
                    image_bytes = base64.b64decode(image_b64)
                except Exception as e:
                    logger.error(f"Falha na decodificação Base64 da imagem: {str(e)}")
                    await manager.send_personal_message({"type": "error", "message": "Erro no formato da imagem enviada."}, user_id)
                    continue

            # -------------------------------------------------------------------
            # NOVO: Guarda o balão do Utilizador no Histórico
            # -------------------------------------------------------------------
            if user_text or image_bytes:
                texto_salvar = user_text if user_text else "[Imagem/Áudio Enviado]"
                msg_user = ChatMessage(session_id=session_id, role="user", content=texto_salvar)
                db.add(msg_user)
                
                # Atualiza o título da sessão se for a primeira mensagem
                if nova_sessao.title == "Nova Conversa":
                    nova_sessao.title = (texto_salvar[:30] + "...") if texto_salvar else "Conversa Multimodal"
                
                db.commit()
            # -------------------------------------------------------------------

            # 5. O PEDÁGIO (SISTEMA DE COBRANÇA E CRÉDITOS)
            has_image = bool(image_bytes)
            custo_total = billing_service.calculate_interaction_cost(has_image=has_image, use_premium_voice=True)

            if not billing_service.check_balance(db, user_id, required_credits=custo_total):
                await manager.send_personal_message({
                    "type": "error",
                    "message": f"Créditos insuficientes. Esta ação custa {custo_total} créditos. Faça um upgrade do seu plano."
                }, user_id)
                continue 

            try:
                # 6. Processamento da IA (Texto)
                resposta_ia = await gemini_service.generate_response(
                    user_id=user_id,
                    plan_id=plan_id,
                    user_message=user_text,
                    image_bytes=image_bytes
                )
                
                # -------------------------------------------------------------------
                # NOVO: Guarda o balão da IA no Histórico
                # -------------------------------------------------------------------
                msg_ia = ChatMessage(session_id=session_id, role="assistant", content=resposta_ia)
                db.add(msg_ia)
                db.commit()
                # -------------------------------------------------------------------
                
                # 7. Processamento da IA (Voz)
                audio_b64_response = await tts_service.generate_audio_base64(
                    text=resposta_ia, 
                    plan_id=plan_id
                )
                
                # 8. Cobrança e Saldo
                billing_service.deduct_credits(db, user_id, amount=custo_total)
                assinatura = db.query(Subscription).filter(Subscription.user_id == user_id).first()
                saldo_atualizado = assinatura.remaining_credits
                
                # Retorno
                await manager.send_personal_message({
                    "type": "ai_response",
                    "message": resposta_ia,
                    "audio_base64": audio_b64_response,
                    "remaining_credits": saldo_atualizado
                }, user_id)

            except Exception as e:
                logger.error(f"Erro no processamento da IA para o usuário {user_id}: {str(e)}")
                await manager.send_personal_message({"type": "error", "message": "Erro interno ao processar sua requisição."}, user_id)
                db.rollback() # Em caso de erro grave, desfaz alterações pendentes no banco
            
    except WebSocketDisconnect:
        logger.warning(f"Usuário {user_id} encerrou a conexão inesperadamente.")
        manager.disconnect(websocket, user_id) 
    finally:
        # -------------------------------------------------------------------
        # NOVO: Garante o fechamento da conexão com o banco ao sair da aba
        # -------------------------------------------------------------------
        db.close()