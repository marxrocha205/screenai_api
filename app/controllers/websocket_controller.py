"""
Controlador de rotas para o WebSocket.
Processa payloads multimodais (Texto + Imagem + Áudio), valida Rate Limit e cobra os Créditos.
Agora com persistência de Histórico de Conversas e Isolamento por Sessão.
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
from app.services.redis_service import redis_service
from app.core.database import SessionLocal
from app.services.billing_service import billing_service
from app.models.subscription_model import Subscription
from app.models.chat_model import ChatSession, ChatMessage

logger = setup_logger(__name__)
router = APIRouter(prefix="/ws", tags=["Tempo Real"])

@router.websocket("/assistente")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """Endpoint WebSocket para o ScreenAI."""
    
    # Validação do utilizador
    try:
        user_data = verify_ws_token(token)
        # Ajuste dependendo de como o seu token retorna (dict ou objeto)
        user_id = user_data["id"] if isinstance(user_data, dict) else user_data.id
        plan_id = user_data.get("plan_id", 1) if isinstance(user_data, dict) else getattr(user_data, "plan_id", 1)
    except Exception as e:
        logger.error(f"Falha na autenticação do WebSocket: {e}")
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)
    logger.info(f"Usuário {user_id} (Plano: {plan_id}) conectado ao WebSocket.")
    
    # Inicia a ligação ao PostgreSQL que viverá durante toda a sessão WebSocket
    db = SessionLocal()
    
    try:
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
                
            # Extrai os dados (INCLUINDO O SESSION_ID)
            session_id_front = data.get("session_id") # Pode ser nulo
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
                        "message": f"{user_text}"
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
                # 6. Processamento da IA passando o session_id
                resposta_ia = await gemini_service.generate_response(
                    user_id=user_id,
                    plan_id=plan_id,
                    session_id=session_id_front, # A MÁGICA COMEÇA AQUI
                    user_message=user_text,
                    image_bytes=image_bytes
                )
                
                # Trata erros em que o gemini_service retorna apenas uma string, ou quando texto/imagem estão vazios (ex: falha no STT)
                if isinstance(resposta_ia, str):
                    await manager.send_personal_message({
                        "type": "error",
                        "message": resposta_ia
                    }, user_id)
                    continue

                # Extrai os dados retornados pelo Gemini Service atualizado
                id_da_conversa = resposta_ia["session_id"]
                texto_resposta = resposta_ia["text"]
                
                # -------------------------------------------------------------------
                # 7. PERSISTÊNCIA NO POSTGRESQL (A MÁGICA DA BARRA LATERAL)
                # -------------------------------------------------------------------
                try:
                    # Se o front não mandou ID, é uma nova conversa
                    if not session_id_front:
                        titulo = user_text[:30] + "..." if user_text else "Nova conversa multimodal"
                        nova_sessao = ChatSession(id=id_da_conversa, user_id=user_id, title=titulo)
                        db.add(nova_sessao)
                        db.commit() # Cria a sessão mãe primeiro
                    
                    # Guarda a mensagem do usuário
                    if user_text or image_bytes:
                        texto_salvar = user_text if user_text else "[Imagem/Áudio Enviado]"
                        msg_user = ChatMessage(session_id=id_da_conversa, role="user", content=texto_salvar)
                        db.add(msg_user)
                        
                    # Guarda a mensagem da IA
                    msg_ia = ChatMessage(session_id=id_da_conversa, role="assistant", content=texto_resposta)
                    db.add(msg_ia)
                    
                    db.commit()
                except Exception as db_err:
                    logger.error(f"Erro ao salvar histórico do WS no banco: {str(db_err)}")
                    db.rollback()
                # -------------------------------------------------------------------
                
                # 8. Processamento da IA (Voz)
                audio_b64_response = await tts_service.generate_audio_base64(
                    text=texto_resposta, 
                    plan_id=plan_id
                )
                
                # 9. Cobrança e Saldo
                billing_service.deduct_credits(db, user_id, amount=custo_total)
                assinatura = db.query(Subscription).filter(Subscription.user_id == user_id).first()
                saldo_atualizado = assinatura.remaining_credits
                
                # 10. Retorno ao Frontend
                await manager.send_personal_message({
                    "type": "ai_response",
                    "message": texto_resposta,
                    "audio_base64": audio_b64_response,
                    "remaining_credits": saldo_atualizado,
                    "session_id": id_da_conversa # A BARRA LATERAL PRECISA DISSO PARA PISCAR
                }, user_id)

            except Exception as e:
                logger.error(f"Erro no processamento da IA para o usuário {user_id}: {str(e)}")
                await manager.send_personal_message({"type": "error", "message": "Erro interno ao processar sua requisição."}, user_id)
                db.rollback()
            
    except WebSocketDisconnect:
        logger.warning(f"Usuário {user_id} encerrou a conexão inesperadamente.")
        manager.disconnect(websocket, user_id) 
    finally:
        # Garante o fechamento da conexão com o banco ao sair da aba
        db.close()