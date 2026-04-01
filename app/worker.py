"""
Trabalhador em Background (Worker).
Consome as filas do Redis e processa as chamadas pesadas da IA de forma assíncrona.
"""
import asyncio
import json
import traceback

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.logger import setup_logger

from app.services.redis_service import redis_service
from app.services.gemini_service import gemini_service
from app.services.tts_service import tts_service
from app.services.websocket_manager import manager
from app.services.billing_service import billing_service

from app.models.subscription_model import Subscription
from app.models.chat_model import ChatSession, ChatMessage
from app.models.usage_model import UsageLog

logger = setup_logger(__name__)

QUEUES = ["queue_plus", "queue_pro", "queue_free"]
MAX_RETRIES = 3

# Limita o número de processamentos simultâneos para não derrubar o servidor
SEMAPHORE = asyncio.Semaphore(10)

async def get_next_job():
    """Busca o próximo trabalho respeitando a prioridade (Plus > Pro > Free)."""
    for queue in QUEUES:
        job = await redis_service.redis.rpop(queue)
        if job:
            return queue, job
    return None, None

async def process_job(payload: dict):
    async with SEMAPHORE:
        user_id = payload["user_id"]
        plan_id = payload["plan_id"]
        user_text = payload.get("text", "")
        session_id = payload.get("session_id")
        image_bytes = payload.get("image_bytes")
        retries = payload.get("retries", 0)

        async with AsyncSessionLocal() as db:
            # 1. Calcula Custo
            custo = billing_service.calculate_interaction_cost(
                has_image=bool(image_bytes),
                use_premium_voice=True
            )

            # 2. Cobra os créditos
            success = await billing_service.deduct_credits(db, user_id, custo)

            if not success:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Créditos insuficientes."
                }, user_id)
                return

            try:
                # 3. Chama a IA (Substituído temporariamente por generate_response normal)
                # Implementaremos o stream real no futuro ao trocar para o pacote google-genai
                resposta_ia = await gemini_service.generate_response(
                    user_id=user_id,
                    plan_id=plan_id,
                    session_id=session_id,
                    user_message=user_text,
                    image_bytes=image_bytes
                )
                
                texto = resposta_ia.get("text", "Erro ao gerar resposta.")
                session_id_final = resposta_ia.get("session_id") or session_id

                # 4. Salva o Histórico de Chat
                if not session_id:
                    nova_sessao = ChatSession(
                        id=session_id_final,
                        user_id=user_id,
                        title=user_text[:30] + "..." if user_text else "Nova conversa"
                    )
                    db.add(nova_sessao)
                    await db.commit()

                db.add(ChatMessage(session_id=session_id_final, role="user", content=user_text))
                db.add(ChatMessage(session_id=session_id_final, role="assistant", content=texto))
                await db.commit()

                # 5. Gera o Áudio TTS
                audio = await tts_service.generate_audio_base64(texto, plan_id)

                # 6. Busca o Saldo Atualizado
                result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
                sub = result.scalars().first()

                # 7. Envia a Resposta Final via WebSocket
                await manager.send_personal_message({
                    "type": "ai_response",
                    "message": texto,
                    "audio_base64": audio,
                    "remaining_credits": sub.remaining_credits if sub else 0,
                    "session_id": session_id_final
                }, user_id)

                # 8. Regista o Analytics
                db.add(UsageLog(user_id=user_id, action="ai_request", cost=custo))
                await db.commit()

            except Exception as e:
                # Ocorreu um erro técnico! Faz rollback, devolve o dinheiro e tenta novamente.
                logger.error(f"[WORKER ERROR] Erro ao processar job: {traceback.format_exc()}")
                
                await billing_service.refund_credits(db, user_id, custo)

                if retries < MAX_RETRIES:
                    payload["retries"] = retries + 1
                    queue_name = QUEUES[min(plan_id - 1, 2)]
                    await redis_service.redis.lpush(queue_name, json.dumps(payload))
                    logger.warning(f"[RETRY] Tentativa {retries+1} para o usuário {user_id}")
                else:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Erro ao processar sua solicitação após várias tentativas. Seus créditos foram devolvidos."
                    }, user_id)

async def worker():
    logger.info("🔥 Worker Enterprise iniciado")
    while True:
        try:
            queue, job = await get_next_job()

            if not job:
                await asyncio.sleep(0.1)
                continue

            payload = json.loads(job)
            asyncio.create_task(process_job(payload))

        except Exception as e:
            logger.error(f"[WORKER LOOP ERROR] {str(e)}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(worker())