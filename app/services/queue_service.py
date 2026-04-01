"""
Serviço de Filas (Filas de Prioridade Baseadas no Plano).
"""
import json
import uuid
from app.services.redis_service import redis_service

# ---------------------------------------------------------
# REGRAS DE NEGÓCIO: ROTEAMENTO DE FILAS
# ---------------------------------------------------------
QUEUE_MAP = {
    1: "queue_free",
    2: "queue_pro",
    3: "queue_plus"
}

class QueueService:

    async def enqueue(self, payload: dict) -> str:
        """Adiciona um trabalho à fila do Redis baseada no plano do utilizador."""
        job_id = str(uuid.uuid4())
        payload["job_id"] = job_id

        plan_id = payload.get("plan_id", 1)
        queue_name = QUEUE_MAP.get(plan_id, "queue_free")

        await redis_service.redis.lpush(
            queue_name,
            json.dumps(payload)
        )

        return job_id

# Instância Singleton
queue_service = QueueService()