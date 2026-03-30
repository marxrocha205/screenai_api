import asyncio
import json
import traceback

from app.services.redis_service import redis_service
from app.services.gemini_service import gemini_service
from app.services.tts_service import tts_service
from app.services.websocket_manager import manager
from app.services.billing_service import billing_service
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.subscription_model import Subscription
from app.models.chat_model import ChatSession, ChatMessage
from app.models.usage_model import UsageLog
from app.core.logger import setup_logger

logger = setup_logger(__name__)

QUEUES = ["queue_plus", "queue_pro", "queue_free"]
MAX_RETRIES = 3

SEMAPHORE = asyncio.Semaphore(10)


async def get_next_job():
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

            custo = billing_service.calculate_interaction_cost(
                has_image=bool(image_bytes),
                use_premium_voice=True
            )

            success = await billing_service.charge_credits(db, user_id, custo)

            if not success:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Créditos insuficientes."
                }, user_id)
                return

            try:
                texto = ""
                session_id_final = session_id

                # 🔥 STREAM REAL
                async for chunk in gemini_service.generate_response_stream(
                    user_id=user_id,
                    plan_id=plan_id,
                    session_id=session_id,
                    user_message=user_text,
                    image_bytes=image_bytes
                ):
                    if session_id and await redis_service.is_stream_cancelled(session_id):
                        logger.info(f"[STOP] usuário {user_id} cancelou stream")

                        await manager.send_personal_message({
                            "type": "stopped",
                            "session_id": session_id
                        }, user_id)

                        await redis_service.clear_stream_cancel(session_id)

                        return

                    if chunk["type"] == "chunk":
                        texto = chunk["full"]

                        await manager.send_personal_message({
                            "type": "stream",
                            "delta": chunk["text"],
                            "full": texto,
                            "session_id": chunk["session_id"]
                        }, user_id)

                    elif chunk["type"] == "end":
                        texto = chunk["text"]
                        session_id_final = chunk["session_id"]

                        await manager.send_personal_message({
                            "type": "stream_end",
                            "message": texto,
                            "session_id": session_id_final
                        }, user_id)

                    elif chunk["type"] == "error":
                        raise Exception(chunk["message"])

                # 💾 histórico
                if not session_id:
                    db.add(ChatSession(
                        id=session_id_final,
                        user_id=user_id,
                        title=user_text[:30] if user_text else "Nova conversa"
                    ))
                    await db.commit()

                db.add(ChatMessage(
                    session_id=session_id_final,
                    role="user",
                    content=user_text
                ))

                db.add(ChatMessage(
                    session_id=session_id_final,
                    role="assistant",
                    content=texto
                ))

                await db.commit()

                # 🔊 TTS
                audio = await tts_service.generate_audio_base64(texto, plan_id)

                # 📊 saldo
                result = await db.execute(
                    select(Subscription).where(Subscription.user_id == user_id)
                )
                sub = result.scalars().first()

                # 📤 resposta final
                await manager.send_personal_message({
                    "type": "ai_response",
                    "message": texto,
                    "audio_base64": audio,
                    "remaining_credits": sub.remaining_credits if sub else 0,
                    "session_id": session_id_final
                }, user_id)

                # 📊 analytics
                db.add(UsageLog(
                    user_id=user_id,
                    action="ai_request",
                    cost=custo
                ))
                await db.commit()

            except Exception:
                logger.error(traceback.format_exc())

                await billing_service.refund_credits(db, user_id, custo)

                if retries < MAX_RETRIES:
                    payload["retries"] = retries + 1
                    queue = QUEUES[min(plan_id - 1, 2)]
                    await redis_service.redis.lpush(queue, json.dumps(payload))

                    logger.warning(f"[RETRY] {retries+1} usuário {user_id}")
                else:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Erro ao processar sua solicitação."
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
            logger.error(f"[WORKER ERROR] {str(e)}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(worker())